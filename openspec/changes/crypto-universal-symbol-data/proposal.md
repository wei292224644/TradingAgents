## Why

Right now the pipeline only recognizes 11 hard-coded crypto bases (`tradingagents/dataflows/symbol_utils.py:45-47`). Any token outside that whitelist—especially meme coins such as `SPCXB-USDT`—fails at every data layer: prices cannot be fetched (Yahoo does not list them), sentiment modules receive the wrong search symbols, and no crypto-specific news exists. This change generalizes crypto symbol parsing and wires OKX as the primary market-data source so the framework works for any listed crypto token, not just BTC/ETH and a few large caps.

## What Changes

- **Generalize crypto symbol parsing**: remove the 11-coin whitelist; accept any `BASE-USD/USDT/USDC/BTC/ETH` token when a dash separator is present, while keeping the whitelist only for the compact (no-dash) form to avoid confusing `EURUSD` forex with crypto.
- **Add OKX vendor**: new `tradingagents/dataflows/okx.py` module implementing OHLCV and indicator-compatible data retrieval via OKX public market API (`/api/v5/market/candles`).
- **Wire OKX into vendor routing**: register OKX in `VENDOR_METHODS` for `get_stock_data` and make `load_ohlcv` aware of the configured vendor so indicators and verified snapshots also use OKX for crypto.
- **Auto-configure crypto vendor chain**: CLI sets `data_vendors.core_stock_apis` to `"okx,yfinance"` when the detected asset type is crypto.
- **Fix sentiment symbol mapping**: update `crypto_base()` consumers (`stocktwits.py`, `reddit.py`) so meme-coin base symbols produce valid StockTwits cashtags and Reddit search terms.
- **Add crypto-friendly news fallback**: introduce Google News RSS fetcher for crypto-specific headlines, used as a lightweight news source when Yahoo Finance has no coverage.
- **Add regression tests** for symbol parsing boundaries and OKX response normalization.

## Capabilities

### New Capabilities
- `universal-crypto-symbol-parsing`: Recognize any dashed crypto pair (`BASE-USDT`, `BASE-USD`, etc.) and resolve it to an internal `BASE-USD` canonical form.
- `okx-market-data`: Fetch OHLCV for any OKX-listed crypto token and expose it through the existing vendor routing and indicator pipeline.
- `crypto-sentiment-sources`: Map arbitrary crypto bases to StockTwits cashtags and Reddit search terms.
- `crypto-news-rss`: Provide a zero-API-key Google News RSS fallback for crypto news.

### Modified Capabilities
- None. Existing stock/forex flows keep their current behavior; only crypto flows broaden.

## Impact

- `tradingagents/dataflows/symbol_utils.py`: symbol normalization rules.
- `tradingagents/dataflows/interface.py`: vendor registration and routing.
- `tradingagents/dataflows/stockstats_utils.py`: `load_ohlcv` vendor-aware branch.
- `tradingagents/dataflows/okx.py`: new file.
- `tradingagents/dataflows/yfinance_news.py` or new `tradingagents/dataflows/news_rss.py`: Google News RSS path.
- `tradingagents/dataflows/stocktwits.py` and `reddit.py`: symbol mapping.
- `cli/utils.py` and `cli/main.py`: auto vendor-chain selection for crypto.
- `tests/`: new unit tests for symbol parsing.
- No new paid API dependencies; OKX public API and Google News RSS are free.

## Open Assumptions

- `[ASSUMED]` OKX public market API (`/api/v5/market/candles`) remains unauthenticated for historical K-line data and its rate limits are acceptable for single-user/local analysis. If OKX policy changes, authentication or heavier rate-limiting will need to be added. (carried from `probe-report.md`)
