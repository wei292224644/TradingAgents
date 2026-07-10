## 1. State and threading

- [x] 1.1 Add `trading_mandate` field to `AgentState` in `tradingagents/agents/utils/agent_states.py`.
- [ ] 1.2 Add optional `trading_mandate: str = ""` parameter to `Propagator.create_initial_state()` (`tradingagents/graph/propagation.py`) and include it in the returned state.
- [ ] 1.3 Add optional `trading_mandate: str = ""` parameter to `TradingAgentsGraph.propagate()` and `_run_graph()` (`tradingagents/graph/trading_graph.py`), passing it into `create_initial_state()`.
- [ ] 1.4 Include mandate (`strip()`-normalized, hashed) in `_run_signature()` so a changed mandate invalidates a resumable checkpoint; unchanged signature when mandate is empty.

## 2. Mandate helper

- [ ] 2.1 Add `get_mandate_from_state(state)` to `tradingagents/agents/utils/agent_utils.py`: empty string when unset; otherwise formatted block with the constraint text (binds recommendations, not evidence). Export in `__all__`.
- [ ] 2.2 Append the mandate block to the `create_msg_delete` placeholder message.
- [ ] 2.3 Unit tests: empty-state no-op, formatted block content, placeholder inclusion.

## 3. Prompt injection (12 agent sites)

- [ ] 3.1 Analysts: `market_analyst.py`, `fundamentals_analyst.py`, `news_analyst.py`, `sentiment_analyst.py` — inject mandate block next to `instrument_context`.
- [ ] 3.2 Researchers: `bull_researcher.py`, `bear_researcher.py` — inject block; bear gets conditional reframing sentence (argue entry timing under mandate, not against mandate).
- [ ] 3.3 Trader: `trader.py` — inject block into user message.
- [ ] 3.4 Risk debators: `aggressive_debator.py`, `conservative_debator.py`, `neutral_debator.py` — inject block; conservative gets the same conditional reframing as bear.
- [ ] 3.5 Managers: `research_manager.py`, `portfolio_manager.py` — inject block.
- [ ] 3.6 Test: with empty mandate, rendered prompts are byte-identical to pre-change output (snapshot or string-equality test on a representative agent).

## 4. Memory log

- [ ] 4.1 Extend `TradingMemoryLog.store_decision()` (`tradingagents/agents/utils/memory.py`) with optional `trading_mandate`; persist verbatim as a `MANDATE:` section placed BEFORE `DECISION:` (placing it after would be swallowed by `_DECISION_RE` at `memory.py:15`, which captures everything up to `REFLECTION:`/end). Add a `_MANDATE_RE` and parse it in `_parse_entry()`; absent section ⇒ no mandate (legacy).
- [ ] 4.2 Render mandate in `get_past_context()` entries via `_format_full()` and `_format_reflection_only()` (e.g. `[mandate: ...]` line); legacy entries without mandate render unchanged. Idempotency scan (`memory.py:43`) and `update_with_outcome()` tag rewrite are tag-based and unaffected.
- [ ] 4.3 Pass mandate at the `store_decision()` call site in `_run_graph()` (`trading_graph.py:469`).
- [ ] 4.4 Unit tests: store/render with and without mandate; legacy-entry compatibility; round-trip through `_parse_entry()`.
- [ ] 4.5 Pass mandate into Phase B reflection: `reflect_on_final_decision()` (`tradingagents/graph/reflection.py:31`) gets optional `trading_mandate` from the parsed entry at the `_resolve_pending_entries()` call site (`trading_graph.py:318`), and the reflection prompt states decisions were made under it — otherwise outcome lessons can contradict the mandate (e.g. "should have shorted" after a mandate-scoped stay-out "Sell") and poison future cross-ticker context.

## 5. CLI

- [ ] 5.1 Add `get_trading_mandate()` to `cli/utils.py`: optional `questionary.text`, Enter skips; `TRADINGAGENTS_MANDATE` env var bypasses the prompt (existing env-precedence pattern).
- [ ] 5.2 Wire into `get_user_selections()` (after ticker/date) and pass through the CLI graph invocation path in `cli/main.py`.
- [ ] 5.3 Show the mandate in the run header messages (alongside ticker/date) when set.

## 6. Reports and regression

- [ ] 6.1 Include mandate in `_log_state()` output and report tree header when set.
- [ ] 6.2 Run full test suite; fix regressions.
- [ ] 6.3 Manual check: BTC-USD crypto run with mandate "现货 long-only，评估是否有入场机会及理想入场区间，不要建议做空或衍生品" — confirm no short/perp recommendations and the decision addresses entry timing/zone.
- [ ] 6.4 Manual check: same ticker without mandate — output shape matches pre-change baseline.
