# Probe Report: add-trading-mandate

> Generated: 2026-07-10
> Summary: 6 questions, 6 decisions, 1 open assumption

## Confirmed decisions

### Scope & intent
- **Question**: 是否限定为「prompt 级约束注入」——自由文本 mandate 穿线到 12 个 agent prompt + 占位消息，不做机械输出校验、不改图结构、不改 PM 评级标尺？
- **AI recommendation**: 是。评级标尺本就无 Short，泄漏源在自由文本环节；机械校验需要可判定的「违规」标准，自由文本 mandate 给不出；图结构不动则空 mandate 零回归。泄漏严重再立输出校验的后续 change。
- **User confirmation**: 是

### Mandate 语义 — 辩论角色
- **Question**: Long-only mandate 下 bear/conservative 是否重定义为「反对当前入场」（时机不对、下方更优），而非被压成好话或继续输出做空/永续？极端利空映射为「不入场/观望」（Hold/Sell）？
- **AI recommendation**: 是。mandate 约束「能推荐什么」，不约束「证据是什么」；bear 停止找利空则辩论失去纠错价值。实现为 bear/conservative 两处条件性 reframing，其余 agent 只收通用约束块。"Sell" 的 long-only 语义随 mandate 存入 memory log。
- **User confirmation**: 是

### 输入面
- **Question**: 输入是否只有 CLI 可选一步（Enter 跳过）、`TRADINGAGENTS_MANDATE` 环境变量、`propagate(trading_mandate=...)` 参数三条路，不做按 ticker 记忆持久化？
- **AI recommendation**: 是，v1 不持久化。重复使用 env var 已覆盖；per-ticker 默认值引入新状态文件和 stale mandate 静默复用的风险——静默继承旧意图比重输一遍更危险。
- **User confirmation**: 是

### Memory log 持久化
- **Question**: mandate 是否随决策原文存入（`store_decision()` 可选字段），`get_past_context()` 渲染加 `[mandate: ...]` 标注，旧条目逐字节不变，不做截断/摘要？
- **AI recommendation**: 是。mandate 一两句话，摘要引入失真；标注是 Q2 语义闭环的另一半，缺了它历史 mandate-scoped 决策会被 reflection 系统性误读。
- **User confirmation**: 是

### Checkpoint 一致性
- **Question**: `_run_signature()`（`tradingagents/graph/trading_graph.py:348`）是否加入 mandate hash，换 mandate 重开跑而非续跑？hash 前仅 `strip()` 归一化。
- **AI recommendation**: 是。续跑会产出前半无 mandate、后半有 mandate 的杂交结论，错误结论比重跑贵。逐字符敏感可接受，恢复场景 env var/命令历史天然一致。
- **User confirmation**: 是

### 验收标准
- **Question**: 验收四条：① BTC-USD + long-only 入场 mandate 全流程无做空/永续且给出入场时机/区间；② 空 mandate prompt 逐字节等于改动前（单测）+ 输出形态同基线；③ memory log 带/不带 mandate 往返正确、旧条目不变（单测）；④ mandate 变更改变 checkpoint 签名、strip 归一化生效（单测）？
- **AI recommendation**: 是。①对应原始痛点，人工验收；②③④机械化零回归保证。①是 LLM 行为，接受 prompt 级约束的残余泄漏率，不设 100% 拦截硬标准。
- **User confirmation**: 是

## Open assumptions [NEEDS CLARIFICATION]

- [ ] `[ASSUMED]` 单条自由文本 mandate 足够表达用户意图，v1 无需结构化字段（方向枚举、工具白名单）。穿线机制与结构无关，后续可无破坏地叠加结构。—— affects: `get_mandate_from_state()` 格式块设计。

## Suggested next step

- [ ] Artifacts (proposal/design/spec/tasks) already generated during explore and are consistent with all 6 confirmations — no `/opsx:propose` needed. Proceed to implementation per `tasks.md`.
