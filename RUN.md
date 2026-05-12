# TradingAgents 本地运行手册

## 环境
- Python 3.13.13 (uv 自动装的,不污染系统)
- venv 路径: `./.venv`(uv 默认)
- 依赖通过 `uv.lock` 锁定,版本固定
- 安装方式: `uv sync --python 3.13`

## 跑之前
1. 编辑 `.env`,填入 `DEEPSEEK_API_KEY=sk-xxx`
2. 默认配置已改成 DeepSeek + 中文输出 + 1 轮辩论(省钱)

## 运行

### 交互式 CLI(推荐)
```bash
cd /Users/minimax/Documents/MyGithub/TradingAgents
uv run tradingagents
```
会让你选 ticker(如 NVDA)、日期、provider、研究深度。

### Python 脚本
```bash
uv run python main.py
```
或自己写:
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "deepseek"
config["deep_think_llm"] = "deepseek-v4-pro"
config["quick_think_llm"] = "deepseek-v4-flash"
config["max_debate_rounds"] = 1

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

### 断点续跑(长 run 防中断)
```bash
uv run tradingagents --checkpoint
# 崩了再跑会自动从断点恢复
```

## 成本估算
- 1 个 ticker × 1 轮辩论 ≈ 几毛钱(DeepSeek V4)
- 加分析师轮数 / risk rounds 会线性放大
- Claude / GPT-5.x 大概贵 10-20 倍

## 模型切换
改 `.env` 里的 `TRADINGAGENTS_*` 三个变量即可,不用改代码:
| 用途 | 便宜 | 平衡 | 烧钱 |
|------|------|------|------|
| quick | `deepseek-v4-flash` | `deepseek-chat` | `gpt-5.4-mini` |
| deep  | `deepseek-v4-pro` | `deepseek-reasoner` | `claude-4-6-opus` / `gpt-5.4` |

切 provider 时记得换 `TRADINGAGENTS_LLM_PROVIDER` + 对应的 `*_API_KEY`。

## ⚠️ 注意
- 这是研究框架,**不是投资建议**(官方 disclaimer)
- 股票数据走 yfinance(免费),回测日期不要超过当天
- DeepSeek 国内直连,Claude/OpenAI 需代理
