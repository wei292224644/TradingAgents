## ADDED Requirements

### Requirement: Provide Google News RSS fallback for crypto-specific news
The system SHALL provide a fetcher that queries Google News RSS for crypto-token headlines using a query such as `"<BASE> crypto"` and returns a formatted plaintext block suitable for prompt injection.

#### Scenario: Fetch news for meme coin
- **WHEN** the news fetcher is called for `SPCXB-USDT`
- **THEN** it searches Google News RSS for `"SPCXB crypto"` and returns headlines from the past week, capped at the configured article limit

#### Scenario: Fetch news for large-cap crypto
- **WHEN** the news fetcher is called for `BTC-USD`
- **THEN** it searches Google News RSS for `"BTC crypto"` and returns recent headlines

### Requirement: Crypto news integrates with existing news analyst
The system SHALL register the Google News RSS fetcher as a vendor for `get_news` so that the news analyst can use it when the asset is crypto and Yahoo Finance has no coverage.

#### Scenario: Vendor dispatch to Google News for crypto
- **WHEN** `route_to_vendor("get_news", "SPCXB-USDT", ...)` is called
- **THEN** it falls back to or directly invokes the Google News RSS implementation

### Requirement: Google News RSS fetcher degrades gracefully
The system SHALL return a clear "no news found" message when the RSS query yields no results, and SHALL handle HTTP/network failures without raising unhandled exceptions.

#### Scenario: Empty news result
- **WHEN** Google News RSS returns no items for the token
- **THEN** the fetcher returns a string stating that no news was found

#### Scenario: Network failure
- **WHEN** the RSS endpoint is unreachable
- **THEN** the fetcher returns a placeholder string and logs a warning, allowing the analysis to continue

### Requirement: News fetcher respects look-ahead safety
The system SHALL filter RSS items by publication date so that articles published after the requested analysis `end_date` are excluded.

#### Scenario: Backtest safety
- **WHEN** the analysis date is `2026-06-01` and the RSS contains an article dated `2026-06-05`
- **THEN** that article is excluded from the returned news block
