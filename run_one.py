#!/usr/bin/env python3
"""跑 TradingAgents 分析单个 ticker 并落盘。"""
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

TICKER = sys.argv[1] if len(sys.argv) > 1 else "600030.SS"
DATE = sys.argv[2] if len(sys.argv) > 2 else "2026-05-11"

print(f"=== TradingAgents run ===", flush=True)
print(f"Ticker: {TICKER}", flush=True)
print(f"Date:   {DATE}", flush=True)
print(f"Provider: {DEFAULT_CONFIG['llm_provider']}", flush=True)
print(f"Deep:   {DEFAULT_CONFIG['deep_think_llm']}", flush=True)
print(f"Quick:  {DEFAULT_CONFIG['quick_think_llm']}", flush=True)
print(f"Debate rounds: {DEFAULT_CONFIG['max_debate_rounds']}", flush=True)
print(f"Risk rounds:   {DEFAULT_CONFIG['max_risk_discuss_rounds']}", flush=True)
print("", flush=True)

t0 = time.time()
try:
    ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
    state, decision = ta.propagate(TICKER, DATE)
    elapsed = time.time() - t0
    print(f"\n=== 完成 (耗时 {elapsed:.1f}s) ===", flush=True)
    print(f"\n=== 最终决策 ===", flush=True)
    print(decision, flush=True)

    # 落盘
    out_dir = Path("runs") / TICKER.replace(".", "_") / DATE
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "decision.txt").write_text(str(decision), encoding="utf-8")
    if isinstance(state, dict):
        keys = list(state.keys())
        print(f"\n=== State keys: {keys} ===", flush=True)
        for k, v in state.items():
            try:
                p = out_dir / f"{k}.txt"
                if isinstance(v, str):
                    p.write_text(v, encoding="utf-8")
                elif isinstance(v, (dict, list)):
                    # JSON keeps the file human-readable AND machine-parseable
                    p.write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                else:
                    p.write_text(str(v), encoding="utf-8")
            except Exception as e:
                print(f"skip {k}: {e}", flush=True)
    print(f"\n=== 报告落盘: {out_dir} ===", flush=True)
except Exception as e:
    elapsed = time.time() - t0
    print(f"\n=== ERROR ({elapsed:.1f}s) ===", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
