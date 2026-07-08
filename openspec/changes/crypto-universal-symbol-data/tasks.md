## 1. Symbol parsing

- [x] 1.1 Replace `_CRYPTO_BASES` whitelist logic in `tradingagents/dataflows/symbol_utils.py` with dash-first parsing; keep whitelist only for compact no-dash inputs.
- [x] 1.2 Update `crypto_base()` to return the base for any dashed crypto pair and any whitelisted compact pair.
- [x] 1.3 Add unit tests covering: dashed meme coin, dashed large cap, compact whitelisted, compact non-whitelisted, forex pair.

## 2. OKX market-data vendor

- [x] 2.1 Create `tradingagents/dataflows/okx.py` with public API client for `/api/v5/market/history-candles`.
- [x] 2.2 Implement `get_okx_stock_data(symbol, start_date, end_date)` returning CSV string in Yahoo-compatible format.
- [x] 2.3 Implement `load_okx_ohlcv(symbol, curr_date)` returning `Date,Open,High,Low,Close,Volume` DataFrame.
- [x] 2.4 Add retry/backoff for OKX rate-limit responses.
- [x] 2.5 Add unit tests for OKX response parsing and pagination handling.

## 3. Vendor routing integration

- [x] 3.1 Register `okx` in `VENDOR_METHODS["get_stock_data"]` in `tradingagents/dataflows/interface.py`.
- [x] 3.2 Make `load_ohlcv` in `tradingagents/dataflows/stockstats_utils.py` branch by configured vendor (`okx` vs `yfinance`).
- [x] 3.3 Add `okx` to `VENDOR_LIST` in `tradingagents/dataflows/interface.py`.
- [x] 3.4 Verify `get_indicators` and `build_verified_market_snapshot` work through OKX path for `SPCXB-USDT`.

## 4. CLI vendor-chain selection

- [x] 4.1 Update `_build_run_config` in `cli/main.py` to set `data_vendors.core_stock_apis` to `"okx,yfinance"` when `asset_type` is `crypto` and no explicit vendor override is present.
- [x] 4.2 Verify that BTC-USD and SPCXB-USDT analyses both pick the OKX-primary chain.

## 5. Sentiment source mapping

- [ ] 5.1 Update `stocktwits.py` `_stocktwits_symbol()` so meme-coin bases produce `BASE.X` cashtags.
- [ ] 5.2 Update `reddit.py` to switch `DEFAULT_SUBREDDITS` to crypto subreddits when the ticker is a recognized crypto symbol.
- [ ] 5.3 Verify `fetch_reddit_posts` extracts base correctly for dashed meme coins.

## 6. Crypto news fallback

- [ ] 6.1 Create `tradingagents/dataflows/news_rss.py` with Google News RSS fetcher for token-specific crypto headlines.
- [ ] 6.2 Register the RSS news fetcher as a fallback vendor for `get_news`.
- [ ] 6.3 Add date-window filtering and graceful degradation for empty results or network failures.
- [ ] 6.4 Add unit tests for RSS parsing and date filtering.

## 7. Integration and regression

- [ ] 7.1 Run a full analysis for `SPCXB-USDT` and confirm market/sentiment/news reports contain real or explicitly unavailable data.
- [ ] 7.2 Run a full analysis for `BTC-USD` and confirm behavior is consistent with pre-change baseline.
- [ ] 7.3 Run a full analysis for `AAPL` and `EURUSD` to verify stock/forex paths are unchanged.
- [ ] 7.4 Run the test suite and fix regressions.
