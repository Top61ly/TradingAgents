#!/usr/bin/env python3
"""扫描 runs/ 目录,把 TradingAgents 分析报告打包进单个 HTML viewer。

用法:
    uv run python tools/build_viewer.py
    open viewer/index.html
"""
from __future__ import annotations
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
TEMPLATE = ROOT / "tools" / "viewer_template.html"
OUTPUT = ROOT / "viewer" / "index.html"

# Hand-curated mapping for tickers we know — Chinese name + sector tag.
# yfinance's longName is English ("Yuexiu Property Company Limited"), so we
# pin the Chinese name here. Falls through to yfinance if ticker not listed.
KNOWN_COMPANIES: dict[str, dict[str, str]] = {
    "001979.SZ": {"cn_name": "招商蛇口", "industry": "房地产开发(央企)"},
    "0123.HK":   {"cn_name": "越秀地产", "industry": "房地产开发(国企)"},
    "600030.SS": {"cn_name": "中信证券", "industry": "证券业"},
    "600048.SS": {"cn_name": "保利发展", "industry": "房地产开发(央企)"},
    "600791.SS": {"cn_name": "京能置业", "industry": "房地产开发"},
}


def detect_exchange(ticker: str) -> str:
    """Map ticker suffix + numeric prefix to a Chinese exchange label."""
    t = ticker.upper()
    if t.endswith(".SS") or t.endswith(".SH"):
        prefix = t[:3]
        if prefix in ("600", "601", "603", "605"): return "上交所主板"
        if prefix == "688": return "上交所科创板"
        if prefix == "900": return "上交所B股"
        return "上交所"
    if t.endswith(".SZ"):
        prefix = t[:3]
        if prefix in ("000", "001", "002", "003"): return "深交所主板"
        if prefix in ("300", "301"): return "深交所创业板"
        if prefix == "200": return "深交所B股"
        return "深交所"
    if t.endswith(".HK"): return "港交所"
    if t.endswith(".T"):  return "东京证交所"
    if t.endswith(".KS"): return "韩国证交所"
    if t.endswith(".L"):  return "伦敦证交所"
    if t.endswith(".TO"): return "多伦多证交所"
    if t.endswith(".AX"): return "澳大利亚证交所"
    if "." not in t: return "美股"
    return t.split(".")[-1]


_meta_cache: dict[str, dict[str, str]] = {}


def get_company_meta(ticker: str, ticker_dir: Path) -> dict[str, str]:
    """Resolve display metadata for a ticker. Order: in-memory cache → known-list
    → on-disk cache (runs/<ticker>/_meta.json) → yfinance live → ticker fallback.
    """
    if ticker in _meta_cache:
        return _meta_cache[ticker]

    base = {"cn_name": ticker, "exchange": detect_exchange(ticker), "industry": ""}
    if ticker in KNOWN_COMPANIES:
        base.update(KNOWN_COMPANIES[ticker])
        _meta_cache[ticker] = base
        return base

    cache_file = ticker_dir / "_meta.json"
    if cache_file.exists():
        try:
            saved = json.loads(cache_file.read_text(encoding="utf-8"))
            base.update({k: v for k, v in saved.items() if v})
            _meta_cache[ticker] = base
            return base
        except Exception:
            pass

    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        live = {
            "cn_name": info.get("longName") or info.get("shortName") or ticker,
            "industry": info.get("industry") or info.get("sector") or "",
            "market_cap": info.get("marketCap") or 0,
        }
        base.update({k: v for k, v in live.items() if v})
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    except Exception as e:
        print(f"  yfinance failed for {ticker}: {e}", file=sys.stderr)

    _meta_cache[ticker] = base
    return base


# Pretty section labels for debate-state dict keys (LangGraph TradingAgents shape).
DEBATE_SECTIONS_INVESTMENT = [
    ("judge_decision", "🧑‍⚖️ 研究经理评判"),
    ("bull_history", "🟢 多头研究员"),
    ("bear_history", "🔴 空头研究员"),
    ("history", "📜 完整辩论记录"),
    ("current_response", "💬 最新发言"),
    ("count", "🔢 辩论轮数"),
]
DEBATE_SECTIONS_RISK = [
    ("judge_decision", "🧑‍⚖️ 投委会评判"),
    ("risky_history", "🔥 激进派分析师"),
    ("safe_history", "🛡️ 保守派分析师"),
    ("neutral_history", "⚖️ 中立派分析师"),
    ("history", "📜 完整辩论记录"),
    ("latest_speaker", "🎤 最近发言者"),
    ("current_risky_response", "💬 激进派最新"),
    ("current_safe_response", "💬 保守派最新"),
    ("current_neutral_response", "💬 中立派最新"),
    ("count", "🔢 辩论轮数"),
]


def _format_value(v) -> str:
    """Format a debate field value into clean markdown."""
    if v is None or v == "":
        return "_(空)_"
    if isinstance(v, (int, float, bool)):
        return f"`{v}`"
    if isinstance(v, str):
        return v.strip()
    return f"```\n{v!r}\n```"


def render_debate_dict(d: dict, sections: list[tuple[str, str]]) -> str:
    """Render a Python dict (debate state) as readable markdown."""
    parts: list[str] = []
    seen = set()
    for key, label in sections:
        if key not in d:
            continue
        val = d[key]
        if val in (None, "", 0) and key in ("count", "current_response"):
            continue  # skip empty meta fields
        parts.append(f"## {label}\n\n{_format_value(val)}")
        seen.add(key)
    # Append any extra keys not in our preset list
    for key, val in d.items():
        if key in seen:
            continue
        parts.append(f"## 📎 {key}\n\n{_format_value(val)}")
    return "\n\n---\n\n".join(parts)


def maybe_parse_dict_file(stem: str, content: str) -> str:
    """If content is a Python dict literal or JSON (debate state), reformat as markdown."""
    stripped = content.strip()
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return content
    parsed = None
    # Try JSON first (new runs), then Python literal (legacy runs with single quotes)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            return content
    if not isinstance(parsed, dict):
        return content
    if "risk" in stem:
        sections = DEBATE_SECTIONS_RISK
    elif "investment" in stem or "debate" in stem:
        sections = DEBATE_SECTIONS_INVESTMENT
    else:
        # Generic dict: dump every key as a section
        sections = [(k, f"📎 {k}") for k in parsed.keys()]
    return render_debate_dict(parsed, sections)


def load_run(ticker_dir: Path, date_dir: Path) -> dict | None:
    files: dict[str, str] = {}
    for f in date_dir.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  skip {f.name}: {e}", file=sys.stderr)
            continue
        files[f.stem] = maybe_parse_dict_file(f.stem, content)
    if not files:
        return None
    ticker = ticker_dir.name.replace("_", ".")
    meta = get_company_meta(ticker, ticker_dir)
    return {
        "ticker": ticker,
        "date": date_dir.name,
        "decision": files.get("decision", "").strip(),
        "files": files,
        "meta": meta,
    }


def collect_runs() -> list[dict]:
    runs: list[dict] = []
    if not RUNS_DIR.exists():
        print(f"warning: {RUNS_DIR} not found, viewer will be empty", file=sys.stderr)
        return runs
    for ticker_dir in sorted(RUNS_DIR.iterdir()):
        if not ticker_dir.is_dir():
            continue
        for date_dir in sorted(ticker_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            run = load_run(ticker_dir, date_dir)
            if run:
                runs.append(run)
    return runs


def main() -> int:
    runs = collect_runs()
    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "runs": runs,
    }
    # Escape </script> to avoid breaking the embedded JSON script tag
    json_str = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__DATA__" not in template:
        print("ERROR: template missing __DATA__ placeholder", file=sys.stderr)
        return 1
    html = template.replace("__DATA__", json_str)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT.relative_to(ROOT)}  ({size_kb:.1f} KB, {len(runs)} runs)")
    if runs:
        for r in runs:
            m = r.get("meta", {})
            label = f"{m.get('cn_name', r['ticker'])} ({r['ticker']}) · {m.get('exchange', '?')}"
            print(f"  {label:<55} {r['date']}  {r['decision'] or '—':12} ({len(r['files'])} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
