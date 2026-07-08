## ADDED Requirements

### Requirement: Recognize dashed crypto pairs for any base token
The system SHALL accept a ticker in the form `BASE-QUOTE` as a crypto symbol when `QUOTE` is one of `USD`, `USDT`, `USDC`, `BTC`, or `ETH`, regardless of whether `BASE` is in a hard-coded whitelist.

#### Scenario: Meme coin with USDT quote is parsed
- **WHEN** the user provides `SPCXB-USDT`
- **THEN** the system resolves it to the canonical `SPCXB-USD`

#### Scenario: Meme coin with USD quote is parsed
- **WHEN** the user provides `PEPE-USD`
- **THEN** the system resolves it to the canonical `PEPE-USD`

#### Scenario: Crypto pair with USDC quote is parsed
- **WHEN** the user provides `SHIB-USDC`
- **THEN** the system resolves it to the canonical `SHIB-USD`

### Requirement: Preserve whitelist for compact (no-dash) crypto symbols
The system SHALL continue to use the existing 11-token whitelist (`BTC`, `ETH`, `SOL`, `XRP`, `ADA`, `DOGE`, `LTC`, `BCH`, `DOT`, `AVAX`, `LINK`) only when the input has no dash separator.

#### Scenario: Whitelisted compact symbol is recognized
- **WHEN** the user provides `BTCUSD`
- **THEN** the system resolves it to the canonical `BTC-USD`

#### Scenario: Non-whitelisted compact symbol is treated as non-crypto
- **WHEN** the user provides `PEPEUSD`
- **THEN** the system does NOT resolve it as a crypto pair (falls through to existing forex/equity rules)

#### Scenario: Forex pair is not mistaken for crypto
- **WHEN** the user provides `EURUSD`
- **THEN** the system resolves it to `EURUSD=X` using the forex rule, not to a crypto pair

### Requirement: Extract crypto base from any recognized crypto symbol
The system SHALL provide a helper that returns the base token for any recognized crypto symbol, regardless of whether the base is in the old whitelist.

#### Scenario: Extract base from dashed meme coin
- **WHEN** `crypto_base("SPCXB-USDT")` is called
- **THEN** it returns `"SPCXB"`

#### Scenario: Extract base from compact whitelisted coin
- **WHEN** `crypto_base("BTCUSD")` is called
- **THEN** it returns `"BTC"`

#### Scenario: Non-crypto returns no base
- **WHEN** `crypto_base("EURUSD")` is called
- **THEN** it returns `None`
