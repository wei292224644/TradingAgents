# TradingAgents CLI 参数说明

命令入口：

```bash
tradingagents analyze [TICKER] [OPTIONS]
# 或
python -m cli.main analyze [TICKER] [OPTIONS]
```

## 行为约定（混合模式）

每个步骤的取值优先级：

1. **命令行参数**（本次显式传入）
2. **环境变量** `TRADINGAGENTS_*`（以及对应 API Key）
3. **交互提问**（终端里一步步选）

因此：

- 传了某个 flag → 该步不再提问
- 没传 → 若有对应 env 则用 env，否则弹出交互
- 什么都不传 → 与原先纯交互 CLI 行为一致

脚本 / Agent 调用时，建议一次传齐所需参数，并加上：

```bash
--no-save-report --no-display-report
```

避免跑完后仍停在「是否保存 / 是否全屏显示」的提问上。

---

## 完整示例

```bash
tradingagents analyze NVDA \
  --date 2026-07-16 \
  --mandate "关注 AI 与数据中心需求" \
  --language Chinese \
  --analysts market,social,news,fundamentals \
  --research-depth 5 \
  --provider deepseek \
  --quick-model deepseek-v4-flash \
  --deep-model deepseek-v4-pro \
  --no-save-report \
  --no-display-report
```

只覆盖部分步骤也可以，其余仍会提问，例如：

```bash
tradingagents analyze --ticker NVDA --provider deepseek
```

---

## 参数一览

### 标的与分析上下文

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `TICKER`（位置参数） | string | 否 | 股票 / 加密货币等标的代码，与 `--ticker` 等价。例：`NVDA`、`0700.HK`、`BTC-USD`。 |
| `--ticker` | string | 否 | 同上。若与位置参数同时给出且不一致，会报错退出。 |
| `--date` | `YYYY-MM-DD` | 否 | 分析基准日，不能是未来日期。未传时交互输入（默认今天）。 |
| `--mandate` | string | 否 | 可选的交易约束 / 分析侧重点，会注入后续 agent 上下文。传空字符串表示明确「无 mandate」。对应 env：`TRADINGAGENTS_MANDATE`。 |
| `--language` | string | 否 | 报告与最终决策的输出语言。常用：`Chinese`、`English`、`Japanese` 等。内部辩论仍为英文。对应 env：`TRADINGAGENTS_OUTPUT_LANGUAGE`。 |

**Ticker 写法提示**

- 美股：`AAPL`、`SPY`
- 港股：`0700.HK`；日股：`7203.T`；伦股：`AZN.L`
- A 股：上交所 `.SS`，深交所 `.SZ`（如 `600519.SS`）
- 加密：`BTC-USD`、`ETH-USD`（crypto 会自动去掉 fundamentals 分析师）

### 分析师与研究深度

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--analysts` | string | 否 | 逗号或空格分隔的分析师列表。合法值见下表。至少选一个。 |
| `--research-depth` | int | 否 | 研究深度，只能是 `1` / `3` / `5`。会同时设置辩论轮数与风险讨论轮数。 |

**`--analysts` 可选值**

| 值 | 含义 |
|----|------|
| `market` | 技术 / 行情分析师（Market Analyst） |
| `social` | 情绪分析师（Sentiment Analyst；历史线名 social） |
| `news` | 新闻 / 宏观分析师（News Analyst） |
| `fundamentals` | 基本面分析师（Fundamentals Analyst；crypto 标的会被自动剔除） |

示例：

```bash
--analysts market,social,news,fundamentals
--analysts market news
```

**`--research-depth` 含义**

| 值 | 档位 | 效果 |
|----|------|------|
| `1` | Shallow | 辩论 / 风险讨论轮数少，更快、更便宜 |
| `3` | Medium | 中等深度 |
| `5` | Deep | 最深；耗时与 token 最高 |

对应 env（可分别设置辩论与风险轮数）：

- `TRADINGAGENTS_MAX_DEBATE_ROUNDS`
- `TRADINGAGENTS_MAX_RISK_ROUNDS`

若使用 `--research-depth`，则 **两个轮数都按该值设置，并覆盖上述 env**。

### LLM 提供商与模型

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--provider` | string | 否 | LLM 提供商 key。见下方支持列表。对应 env：`TRADINGAGENTS_LLM_PROVIDER`。 |
| `--backend-url` | URL | 否 | 自定义 API Base URL（`http://` 或 `https://`）。不传则用该 provider 默认端点，或 env `TRADINGAGENTS_LLM_BACKEND_URL`。 |
| `--quick-model` | string | 否 | 快速思考模型 ID（工具调用、轻量步骤）。对应 env：`TRADINGAGENTS_QUICK_THINK_LLM`。 |
| `--deep-model` | string | 否 | 深度思考模型 ID（复杂推理、终局决策等）。对应 env：`TRADINGAGENTS_DEEP_THINK_LLM`。 |

**`--provider` 支持的值**

| Provider key | 说明 | 默认 endpoint（可被 `--backend-url` 覆盖） |
|--------------|------|---------------------------------------------|
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `google` | Google Gemini | SDK 默认 |
| `anthropic` | Anthropic Claude | `https://api.anthropic.com/` |
| `xai` | xAI Grok | `https://api.x.ai/v1` |
| `deepseek` | DeepSeek | `https://api.deepseek.com` |
| `qwen` | 通义千问（国际 DashScope） | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `glm` | 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4/` |
| `minimax` | MiniMax | `https://api.minimax.io/v1` |
| `openrouter` | OpenRouter | `https://openrouter.ai/api/v1` |
| `mistral` | Mistral | `https://api.mistral.ai/v1` |
| `kimi` | Kimi / Moonshot | `https://api.moonshot.ai/v1` |
| `groq` | Groq | `https://api.groq.com/openai/v1` |
| `nvidia` | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` |
| `azure` | Azure OpenAI | 需自行配置 |
| `bedrock` | Amazon Bedrock | 需 AWS 凭证；可选安装 `.[bedrock]` |
| `ollama` | 本地 / 远程 Ollama | `http://localhost:11434/v1`（可用 `OLLAMA_BASE_URL`） |
| `openai_compatible` | 任意 OpenAI 兼容端点（vLLM、LM Studio 等） | **必须**再给 `--backend-url`（或 env） |

当前仓库内置默认（未传参且未设 env 时，走代码默认；CLI 交互里也会优先高亮这些选项）：

- provider：`deepseek`
- quick：`deepseek-v4-flash`
- deep：`deepseek-v4-pro`
- language：`Chinese`
- research depth：`5`

**API Key**

CLI **没有** `--api-key`（避免密钥进 shell history）。请事先写入环境或 `.env`，例如：

```bash
export DEEPSEEK_API_KEY=...
# 或其他提供商：OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY ...
```

若运行时仍缺失，会交互提示粘贴并写入项目 `.env`。

### Provider 专属推理档位（可选）

仅在对应提供商下有意义；未传且 provider 已由 CLI/env 固定时，使用配置默认（常为 `None` = 提供商自身默认）。

| 参数 | 适用 provider | 说明 | 对应 env |
|------|---------------|------|----------|
| `--openai-reasoning-effort` | `openai` | 如 `low` / `medium` / `high` | `TRADINGAGENTS_OPENAI_REASONING_EFFORT` |
| `--google-thinking-level` | `google` | 如 `minimal` / `high` | `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` |
| `--anthropic-effort` | `anthropic` | 如 `low` / `medium` / `high` | `TRADINGAGENTS_ANTHROPIC_EFFORT` |

### 跑完后的报告处理

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--save-report` / `--no-save-report` | flag | 否 | 是否把完整报告落到磁盘。未传则跑完后提问（默认 Y）。 |
| `--report-dir` | path | 否 | 与保存配合使用的目录。未传且选择了保存时，默认 `./reports/<TICKER>_<timestamp>`。 |
| `--display-report` / `--no-display-report` | flag | 否 | 是否在终端打印完整报告。未传则跑完后提问（默认 Y）。 |

Agent / CI 建议固定：

```bash
--no-save-report --no-display-report
```

若既要落盘又不要提问：

```bash
--save-report --report-dir ./reports/NVDA_run --no-display-report
```

### 断点续跑

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--checkpoint` / `--no-checkpoint` | flag | 否 | 是否启用 LangGraph checkpoint。启用后中断可从上一成功节点恢复。未传则遵循 `TRADINGAGENTS_CHECKPOINT_ENABLED` / 默认 `false`。 |
| `--clear-checkpoints` | flag | 否 | 运行前清空已保存的 checkpoint（强制全新开始）。 |

Checkpoint 文件默认在 `~/.tradingagents/cache/checkpoints/`（可用 `TRADINGAGENTS_CACHE_DIR` 改根目录）。

---

## 与环境变量的对应关系

| CLI 参数 | 环境变量 |
|----------|----------|
| `--provider` | `TRADINGAGENTS_LLM_PROVIDER` |
| `--backend-url` | `TRADINGAGENTS_LLM_BACKEND_URL` |
| `--quick-model` | `TRADINGAGENTS_QUICK_THINK_LLM` |
| `--deep-model` | `TRADINGAGENTS_DEEP_THINK_LLM` |
| `--language` | `TRADINGAGENTS_OUTPUT_LANGUAGE` |
| `--mandate` | `TRADINGAGENTS_MANDATE` |
| `--research-depth` | 同时覆盖 `TRADINGAGENTS_MAX_DEBATE_ROUNDS` 与 `TRADINGAGENTS_MAX_RISK_ROUNDS`（仅当使用该 CLI 参数时） |
| `--openai-reasoning-effort` | `TRADINGAGENTS_OPENAI_REASONING_EFFORT` |
| `--google-thinking-level` | `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` |
| `--anthropic-effort` | `TRADINGAGENTS_ANTHROPIC_EFFORT` |
| `--checkpoint` | `TRADINGAGENTS_CHECKPOINT_ENABLED` |

更多可选项见项目根目录 [`.env.example`](../.env.example)。

---

## 输出与结果位置

一次成功分析后，常见产物：

| 位置 | 内容 |
|------|------|
| 终端 Live UI | 各 agent 进度、工具调用、中间结论 |
| `~/.tradingagents/logs/<TICKER>/<DATE>/` | 运行日志与分节报告（可用 `TRADINGAGENTS_RESULTS_DIR` 改根） |
| `./reports/...` | 仅在选择 `--save-report`（或交互选 Y）时写入的完整报告树 |
| `~/.tradingagents/memory/trading_memory.md` | 决策记忆日志（可用 `TRADINGAGENTS_MEMORY_LOG_PATH` 改路径） |

---

## 校验与常见错误

| 情况 | 行为 |
|------|------|
| 非法 ticker / 空 `--ticker` | 启动前报错退出 |
| `--date` 格式错或未来日 | 启动前报错退出 |
| `--analysts` 含未知名或为空 | 启动前报错退出 |
| `--research-depth` 不是 1/3/5 | 启动前报错退出 |
| `--provider` 不在支持列表 | 启动前报错退出 |
| 位置参数与 `--ticker` 冲突 | 启动前报错退出 |
| crypto 只选了 `fundamentals` | 过滤后列表为空，退出 |
| 缺少 API Key | 可能交互要求粘贴；无人值守场景请先配好 `.env` |

查看内置帮助：

```bash
tradingagents analyze --help
```

---

## 给 Agent / 脚本的推荐模板

```bash
# 前置：.env 中已有 DEEPSEEK_API_KEY（或所选 provider 的 key）
tradingagents analyze "$TICKER" \
  --date "$DATE" \
  --language Chinese \
  --analysts market,social,news,fundamentals \
  --research-depth 5 \
  --provider deepseek \
  --quick-model deepseek-v4-flash \
  --deep-model deepseek-v4-pro \
  --no-save-report \
  --no-display-report
```

硬性建议：

1. 不要裸跑 `tradingagents` / `tradingagents analyze` 而不带参数（会进入交互）。
2. 无人值守必须带 `--no-save-report --no-display-report`（或明确的 `--save-report --report-dir ...`）。
3. 密钥只放环境变量 / `.env`，不要做 CLI 传 key。
