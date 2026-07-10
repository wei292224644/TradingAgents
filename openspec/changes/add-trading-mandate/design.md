## Context

Every agent prompt already receives one run-scoped framing string: `instrument_context`, resolved once at run start and read via `get_instrument_context_from_state(state)` in 12 agent files plus the `create_msg_delete` placeholder (`tradingagents/agents/utils/agent_utils.py:190`). That is exactly the propagation path a user mandate needs. The mandate is a second, independent framing string carried the same way.

Chosen approach is Option A from exploration: a **separate state field**, not appending to `instrument_context`. `instrument_context` is deterministic instrument identity (yfinance-resolved, cacheable); the mandate is user intent (per-run, free-text, optional). Mixing them would make the identity string non-deterministic and complicate storing/displaying the mandate on its own.

## Goals / Non-Goals

**Goals:**
- Optional free-text mandate reaches every agent prompt in the run.
- Zero behavior change when no mandate is supplied (empty-string default everywhere).
- Bear/risk debate stays adversarial *within* the mandate rather than against it.
- Mandate persisted with the decision in the memory log so reflection interprets past decisions correctly.

**Non-Goals:**
- Structured mandate schema (direction enums, instrument whitelists) — v1 is one string.
- Enforcing the mandate mechanically (output validation / rejection). Prompt-level constraint only.
- Changing graph topology, debate rounds, or the `PortfolioDecision` rating scale.
- Multi-mandate or per-agent mandates.

## Decisions

1. **Separate `trading_mandate` state field (Option A), not appended to `instrument_context` (Option B)**
   - Rationale: identity vs intent are different lifecycles — identity is resolved/cached deterministically, intent is per-run user input. A separate field lets memory log, reports, and CLI display the mandate independently. Cost is ~12 one-line prompt edits, mitigated by a shared helper.

2. **Helper returns a fully formatted block or empty string**
   - `get_mandate_from_state(state)` returns `""` when unset, else a delimited block:
     `"\n\n**User mandate (binding constraints for recommendations):** <text>\nAll recommendations must stay within this mandate. Do not propose instruments, directions, or strategies it excludes. The mandate constrains recommendations, not evidence — still report adverse findings honestly.\n"`
   - Agent files inject `{mandate_block}` unconditionally; formatting logic lives in one place. Empty mandate ⇒ prompts byte-identical to today.

3. **Mandate constrains the action space, not the analysis**
   - The helper text explicitly says adverse evidence must still be reported. A long-only mandate must not turn the bear researcher into a yes-man; it turns "short this" into "don't enter yet / wait for lower".
   - Bear researcher and conservative debator get one extra conditional sentence when a mandate exists: argue against *the entry/timing under the mandate*, not against the mandate itself.

4. **Placeholder message carries the mandate**
   - `create_msg_delete` already re-anchors instrument context after message wipes between analysts (`agent_utils.py:204`); the mandate is appended there too, otherwise later analysts on some providers lose the framing.

5. **Memory log stores mandate verbatim with the decision**
   - `store_decision(..., trading_mandate=...)`. `get_past_context()` renders it as a suffix on past entries (e.g. `"[mandate: spot long-only] Decision: Sell"`) so reflection on a later run doesn't misread a mandate-scoped "Sell" as a directional short call. Entries without a mandate render unchanged.
   - Storage layout (analyze finding): the log is a plain-text format — tag line `[date | ticker | rating | status]` + `DECISION:` section, parsed by regex (`memory.py:15`). The mandate is a new optional `MANDATE:` section placed *before* `DECISION:`; after it, `_DECISION_RE` would swallow it into the decision text. Tag format is untouched, so the idempotency scan and `update_with_outcome()` rewrite are unaffected.
   - Phase B reflection also receives the mandate: `reflect_on_final_decision()` formats only the decision text today (`reflection.py:53`); without the mandate, an outcome lesson for a mandate-scoped "Sell" that preceded a rally reads "should have stayed long / shorted", which then leaks into cross-ticker context. The reflection prompt gets one line stating the mandate the decision was made under.

6. **CLI asks after ticker/date, skippable with Enter**
   - One `questionary.text` step, default empty. Env override `TRADINGAGENTS_MANDATE` skips the prompt, consistent with the existing env-precedence pattern in `get_user_selections()` (`cli/main.py:521`).

## Risks / Trade-offs

- **Prompt-level enforcement can leak**: an LLM may still mention perps in passing. Accepted for v1; mechanical output validation is a non-goal. Mitigation: the helper's constraint sentence is imperative and repeated at every agent, including the PM who writes the final decision.
- **Mandate vs evidence tension**: if evidence screams "crash imminent" under a long-only entry mandate, correct output is "do not enter" (Hold/Sell = stay out), which the existing rating scale already expresses. Decision 3's wording keeps this path open.
- **Checkpoint resume**: mandate is part of run inputs; a resumed run with a *different* mandate must not continue the old graph. Add mandate (`strip()`-normalized, then hashed) to `_run_signature()` (`trading_graph.py:348`) so a changed mandate invalidates the checkpoint. No deeper normalization — character-exact matching is acceptable since recovery reruns come from env var or shell history (probe Q5).

## Open Questions

- None. Report inclusion confirmed (propose, 2026-07-10): `trading_mandate` field in `_log_state()` JSON, mandate line in `save_reports()` markdown header; both absent when unset so legacy shape is unchanged.
