## ADDED Requirements

### Requirement: Accept an optional trading mandate at run start
The system SHALL accept an optional free-text trading mandate when a run is initiated, via `TradingAgentsGraph.propagate()` parameter, CLI prompt, or `TRADINGAGENTS_MANDATE` environment variable, defaulting to empty.

#### Scenario: Programmatic caller supplies a mandate
- **WHEN** `propagate("BTC-USD", "2026-07-10", asset_type="crypto", trading_mandate="Spot long-only; evaluate entry opportunity and entry zone")` is called
- **THEN** the initial agent state contains that mandate string in `trading_mandate`

#### Scenario: No mandate supplied
- **WHEN** `propagate("NVDA", "2026-07-10")` is called without a mandate
- **THEN** `trading_mandate` is an empty string and the run proceeds exactly as before

#### Scenario: CLI user skips the mandate question
- **WHEN** the CLI mandate step is answered with Enter (empty input)
- **THEN** the run proceeds with no mandate and no mandate text appears in any prompt

### Requirement: Inject the mandate into every agent prompt
The system SHALL inject the mandate, when non-empty, into the prompts of all agents that receive `instrument_context` (analysts, researchers, trader, risk debators, research manager, portfolio manager) and into the `create_msg_delete` placeholder message.

#### Scenario: Mandate reaches the trader
- **WHEN** a run executes with mandate "Spot long-only; no derivatives"
- **THEN** the trader's prompt contains the mandate block including the constraint that recommendations must stay within it

#### Scenario: Empty mandate leaves prompts unchanged
- **WHEN** a run executes with an empty mandate
- **THEN** every agent prompt is byte-identical to the prompt produced before this change

### Requirement: Mandate constrains recommendations, not evidence
The mandate injection text SHALL instruct agents that the mandate bounds what may be recommended (direction, instruments, strategies) while adverse evidence must still be reported, and the bear/conservative agents SHALL argue against entry timing under the mandate rather than against the mandate itself.

#### Scenario: Bearish evidence under a long-only entry mandate
- **WHEN** the mandate is "spot long-only entry evaluation" and analysis is bearish
- **THEN** the final decision expresses "do not enter / wait" (Hold/Sell on the existing scale) rather than recommending a short or perpetual-futures position

### Requirement: Persist the mandate with the logged decision
The system SHALL store the mandate verbatim alongside the decision in the trading memory log, and `get_past_context()` SHALL render it with past entries so later reflection interprets mandate-scoped decisions correctly.

#### Scenario: Past mandate-scoped decision is contextualized
- **WHEN** a prior BTC-USD run stored decision "Sell" under mandate "spot long-only entry evaluation" and a new BTC-USD run starts
- **THEN** the past context shown to agents identifies that "Sell" as made under that mandate

#### Scenario: Legacy entries without mandate render unchanged
- **WHEN** past context includes entries stored before this change
- **THEN** those entries render exactly as they do today

#### Scenario: Outcome reflection sees the mandate
- **WHEN** Phase B deferred reflection runs on a pending entry that was stored with a mandate
- **THEN** the reflection prompt includes the mandate, so the generated lesson evaluates the decision within it (e.g. "missed entry" rather than "should have shorted")

### Requirement: Changed mandate invalidates a resumable checkpoint
The system SHALL include the mandate in the run signature used for checkpoint thread identity, so resuming the same ticker+date with a different mandate starts a fresh run.

#### Scenario: Resume with a different mandate
- **WHEN** a checkpointed BTC-USD run made with mandate A crashes, and the user reruns the same ticker+date with mandate B
- **THEN** the graph starts fresh instead of resuming mandate A's partial state
