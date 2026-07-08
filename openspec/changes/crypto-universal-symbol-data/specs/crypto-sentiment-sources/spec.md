## ADDED Requirements

### Requirement: StockTwits cashtag uses crypto base for any recognized crypto
The system SHALL map any recognized crypto symbol to a StockTwits cashtag of the form `BASE.X`, using the generalized `crypto_base()` helper.

#### Scenario: Meme coin cashtag
- **WHEN** the StockTwits fetcher receives `SPCXB-USDT`
- **THEN** it queries `api.stocktwits.com/api/2/streams/symbol/SPCXB.X.json`

#### Scenario: Whitelisted large-cap unchanged
- **WHEN** the StockTwits fetcher receives `BTC-USD`
- **THEN** it queries `api.stocktwits.com/api/2/streams/symbol/BTC.X.json`

### Requirement: Reddit search uses crypto base and crypto subreddits for any recognized crypto
The system SHALL extract the crypto base for any recognized crypto symbol and search the crypto-oriented subreddits `CryptoCurrency`, `SatoshiStreetBets`, and `CryptoMoonShots` instead of the equity subreddits.

#### Scenario: Meme coin Reddit search
- **WHEN** the Reddit fetcher receives `SPCXB-USDT`
- **THEN** it searches for `"SPCXB"` in the crypto subreddits

#### Scenario: Large-cap crypto Reddit search
- **WHEN** the Reddit fetcher receives `BTC-USD`
- **THEN** it searches for `"BTC"` in the crypto subreddits

#### Scenario: Equity symbol still uses equity subreddits
- **WHEN** the Reddit fetcher receives `AAPL`
- **THEN** it searches in `wallstreetbets`, `stocks`, and `investing`

### Requirement: Sentiment analyst degrades gracefully on missing social data
The system SHALL ensure the sentiment analyst reports a clear placeholder when a crypto token has no StockTwits messages or Reddit posts, rather than fabricating content.

#### Scenario: No social data for meme coin
- **WHEN** both StockTwits and Reddit return empty for `SPCXB-USDT`
- **THEN** the sentiment report states that social sources are silent and lowers confidence accordingly
