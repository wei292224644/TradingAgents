## Why

The pipeline's only inputs are `ticker + trade_date + asset_type` (`tradingagents/graph/trading_graph.py:362`). Nothing expresses what the user actually wants answered. For a question like "is there a good spot entry for BTC-USD, and at what level?", the trader and risk debators free-associate into shorting, perpetual futures, and leverage — instruments and directions the user never asked about. The final decision answers a question the user didn't pose.

This change adds an optional **trading mandate** (主基调): a user-supplied statement of intent and constraints that frames the entire multi-agent discussion, e.g. "Spot long-only. Evaluate whether BTC-USD has an entry opportunity and identify the ideal entry zone. Do not recommend shorting or derivatives."

## What Changes

- **New state field `trading_mandate`**: added to `AgentState`, threaded through `Propagator.create_initial_state()` and `TradingAgentsGraph.propagate()` as an optional parameter (default empty string — existing callers unchanged).
- **New helper `get_mandate_from_state(state)`** in `agent_utils.py`, mirroring `get_instrument_context_from_state`: returns a formatted mandate block, or empty string when no mandate is set so agents are byte-identical to today's prompts.
- **Prompt injection at all 12 agent sites** that already read `instrument_context`: 4 analysts, bull/bear researchers, trader, 3 risk debators, research manager, portfolio manager. Also the `create_msg_delete` placeholder message.
- **Bear researcher reframing under a mandate**: when a mandate is present, the bear argues "this is not a good entry now / better entry exists lower", not "never own this asset" — keeping the debate useful instead of fighting the user's premise.
- **CLI step**: optional free-text question ("Trading mandate / analysis focus, Enter to skip") in `get_user_selections()`, passed through the CLI graph path.
- **Memory log consistency**: `store_decision()` records the mandate alongside the decision so future reflection reads "Sell under long-only mandate = don't enter", not "go short".

## Capabilities

### New Capabilities
- `trading-mandate`: Accept an optional user mandate at run start and inject it into every agent prompt so recommendations stay inside the user's stated intent, direction, and instrument constraints.

### Modified Capabilities
- None. With no mandate supplied, every prompt is unchanged.

## Impact

- `tradingagents/agents/utils/agent_states.py`: new `trading_mandate` field.
- `tradingagents/agents/utils/agent_utils.py`: new `get_mandate_from_state()` helper; `create_msg_delete` placeholder includes mandate.
- `tradingagents/graph/propagation.py`: `create_initial_state()` optional param.
- `tradingagents/graph/trading_graph.py`: `propagate()` optional param; `store_decision()` call includes mandate.
- 12 agent files under `tradingagents/agents/` (analysts ×4, researchers ×2, risk_mgmt ×3, trader, managers ×2): one injection line each.
- `tradingagents/agents/utils/memory.py` (TradingMemoryLog): store mandate with decision entries.
- `cli/utils.py` + `cli/main.py`: optional mandate question and pass-through.
- `tests/`: unit tests for helper formatting, empty-mandate no-op, state threading.

## Open Assumptions

- None remaining — all assumptions confirmed at probe (2026-07-10) or propose (2026-07-10).

## Confirmed by probe (2026-07-10)

- Mandate is written into report outputs when set: `trading_mandate` field in `_log_state()` JSON and a mandate line in the `save_reports()` markdown header. Absent when unset — legacy report shape unchanged. (confirmed at propose, 2026-07-10)

- Single free-text mandate string for v1; no structured fields (direction enum, instrument whitelist). Threading is structure-agnostic, so structure can be layered later without rework. (confirmed at propose, 2026-07-10)

- Prompt-level constraint only: no output validation, no graph-topology change, no rating-scale change.
- Mandate constrains recommendations, not evidence; bear/conservative reframe to "argue against entry timing under the mandate"; extreme bearish ⇒ Hold/Sell = stay out.
- Input surface: CLI optional step + `TRADINGAGENTS_MANDATE` env var + `propagate()` param only; no per-ticker persistence.
- Memory log stores mandate verbatim; `[mandate: ...]` annotation in past context; legacy entries byte-identical.
- `_run_signature()` includes mandate hash, `strip()`-normalized only.
- Acceptance: BTC-USD mandate run without short/perp output + byte-identical empty-mandate prompts + memory-log round-trip + signature invalidation (see probe-report.md).
