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
    return {
        "ticker": ticker_dir.name.replace("_", "."),
        "date": date_dir.name,
        "decision": files.get("decision", "").strip(),
        "files": files,
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
            print(f"  {r['ticker']:14} {r['date']}  {r['decision'] or '—':12} ({len(r['files'])} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
