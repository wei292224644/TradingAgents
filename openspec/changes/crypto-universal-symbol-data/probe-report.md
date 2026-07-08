# Probe Report: crypto-universal-symbol-data

> Generated: 2026-07-08
> Summary: 6 questions, 6 decisions, 1 open assumption

## Confirmed decisions

### Scope & intent
- **Question**: 这个 change 是否只覆盖"任意加密币的数据链路"，把"分析要有出发点（何时入场/出场）"单独作为一个 change？
- **AI recommendation**: 是，只覆盖数据链路四块：symbol 解析泛化、OKX 价格/K线、StockTwits+Reddit 情绪适配、Google News RSS 新闻兜底。"用户提问驱动分析"与数据层正交，单独立 change 更干净。
- **User confirmation**: 可以

### Data sources
- **Question**: 新闻源是否不接付费 CryptoPanic，改用 Google News RSS 兜底？
- **AI recommendation**: 不接付费源。CryptoPanic 免费 Developer API 已于 2026-04-01 下线（证据：WebSearch "CryptoPanic API pricing free tier developer plan 2026"）。Google News RSS 零 key 零依赖，与现有 `reddit.py:93` RSS/Atom 解析路径一致，查不到则返回明确占位，pipeline 已有降级处理。meme 币由社交情绪主导，新闻权重低。
- **User confirmation**: 可以

### Price-data routing
- **Question**: crypto 资产是否走 OKX 优先 + yfinance 兜底的 vendor 链，由 CLI 自动配置？
- **AI recommendation**: 是。`asset_type == crypto` 时 CLI 把 `core_stock_apis` vendor 链设为 `"okx,yfinance"`。链式 fallback 在 `tradingagents/dataflows/interface.py:179-183` 已明确支持，不违反"不做静默 vendor 切换"原则，因为链是配置里明写的。
- **User confirmation**: 可以

### Symbol recognition boundary
- **Question**: 是否把 `crypto_base()` 从白名单改成"带 `-` 的写法无条件当 crypto"，不带 `-` 的紧凑写法维持 11 币白名单？
- **AI recommendation**: 是。带 `-` 的格式（如 `SPCXB-USDT`）不会与外汇冲突，任何 base 都认；不带 `-` 的 `PEPEUSD` 和 `EURUSD` 句法无法区分，必须保留白名单。OKX 官方格式本就带 `-`，复制粘贴即可。这也与 `cli/utils.py:85` 的 `CRYPTO_SUFFIXES` 行为一致。
- **User confirmation**: 可以

### Internal canonical form
- **Question**: 内部是否仍统一用 `BASE-USD` 作为 canonical 格式，由各数据源适配器自行转回 source-specific 形式？
- **AI recommendation**: 是。保持现有 `BASE-USD` 约定可最小化下游改动：缓存文件名、情绪模块、资产检测都已按它编码。OKX 取价时自动试 `BASE-USDT` 再试 `BASE-USDC`；StockTwits 转 `BASE.X`；Reddit 搜 `BASE`；报告会标注实际源为 OKX USDT 对。
- **User confirmation**: 可以

### Success criteria
- **Question**: 验收是否定为：① SPCXB-USDT 全流程分析使用 OKX 真实价格/指标；② 情绪报告 StockTwits/Reddit 真实或明确标注 unavailable；③ BTC-USD/AAPL/EURUSD 回归不变；④ symbol 解析单元测试覆盖边界。
- **AI recommendation**: 是。这样验收直接对应用户痛点（查不到数据、编造价格），并防止回归。
- **User confirmation**: 可以

## Open assumptions [NEEDS CLARIFICATION]

- [ ] `[ASSUMED]` OKX 公开行情 API (`/api/v5/market/candles`) 当前不需要认证即可访问 1H/1D K 线，且请求频率限制在个人宽带/IP 下可接受。若 OKX 开放 API 策略改变，需增加认证或限流逻辑。—— affects: `tradingagents/dataflows/okx.py` vendor 实现。

## Suggested next step

- [ ] Run `/opsx:propose crypto-universal-symbol-data` to generate artifacts (it will read this report).
