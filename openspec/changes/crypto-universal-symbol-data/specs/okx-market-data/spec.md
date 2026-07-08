## ADDED Requirements

### Requirement: OKX OHLCV fetcher accepts canonical crypto symbols
The system SHALL expose a function that, given a canonical `BASE-USD` symbol and a date range, fetches daily candlestick data from the OKX public `/api/v5/market/history-candles` endpoint and returns it as a DataFrame with columns `Date`, `Open`, `High`, `Low`, `Close`, `Volume`.

#### Scenario: Fetch SPCXB data
- **WHEN** the OKX fetcher is called for `SPCXB-USD` between `2026-06-01` and `2026-07-08`
- **THEN** it calls OKX with `instId=SPCXB-USDT` (or `SPCXB-USDC` as fallback), parses the response, and returns a non-empty DataFrame in the standard column format

#### Scenario: Handle OKX API pagination
- **WHEN** the requested date range spans more than the maximum candles per OKX request
- **THEN** the fetcher paginates transparently and combines results into a single DataFrame

### Requirement: OKX data integrates with existing vendor routing
The system SHALL register the OKX fetcher under `VENDOR_METHODS["get_stock_data"]["okx"]` so that `route_to_vendor("get_stock_data", ...)` can dispatch to OKX.

#### Scenario: Vendor dispatch to OKX
- **WHEN** `route_to_vendor("get_stock_data", "SPCXB-USD", start, end)` is invoked and the configured vendor chain includes `okx`
- **THEN** it invokes the OKX implementation

### Requirement: Indicator pipeline can use OKX OHLCV
The system SHALL make `load_ohlcv` aware of the configured `core_stock_apis` vendor. When the active vendor is `okx`, `load_ohlcv` fetches from OKX instead of Yahoo Finance, so that `get_indicators` and `build_verified_market_snapshot` work for OKX-listed meme coins.

#### Scenario: Indicators from OKX data
- **WHEN** `get_indicators("SPCXB-USD", ...)` is called with OKX configured
- **THEN** the system reads OKX OHLCV data and computes the requested indicator values

#### Scenario: Verified snapshot from OKX data
- **WHEN** `build_verified_market_snapshot("SPCXB-USD", ...)` is called with OKX configured
- **THEN** the snapshot reflects the latest OKX OHLCV row and derived indicators

### Requirement: Crypto asset auto-selects OKX-first vendor chain
The system SHALL configure the vendor chain `data_vendors.core_stock_apis = "okx,binance,yfinance"` when the detected asset type is crypto (OKX primary, Binance second — it lists tokens OKX doesn't, e.g. Chinese-named meme coins — Yahoo last).

#### Scenario: CLI analysis for a meme coin
- **WHEN** the user selects `币安人生-USDT` in the CLI
- **THEN** the run config sets `core_stock_apis` to `"okx,binance,yfinance"`

#### Scenario: CLI analysis for BTC-USD
- **WHEN** the user selects `BTC-USD` in the CLI
- **THEN** the run config also sets `core_stock_apis` to `"okx,binance,yfinance"` (OKX serves it; later vendors unused)

### Requirement: Binance spot vendor covers tokens OKX lacks
The system SHALL provide a Binance spot vendor (`/api/v3/klines`, no API key) registered as `binance` for `get_stock_data` and in the `load_ohlcv` vendor branch, resolving canonical `BASE-USD` symbols to `<BASE>USDT` then `<BASE>USDC` — including Unicode bases such as `币安人生`.

#### Scenario: Chain falls back OKX -> Binance
- **WHEN** `load_ohlcv("币安人生-USD", ...)` runs with the crypto chain and OKX has no such instrument
- **THEN** the data is served from Binance klines and the report names the Binance spot symbol

#### Scenario: Unicode cache safety
- **WHEN** a Unicode-based canonical symbol reaches the OHLCV cache layer
- **THEN** the cache filename check accepts Unicode letters while still rejecting path separators and traversal sequences

### Requirement: OKX responses are normalized to Yahoo-equivalent shape
The system SHALL ensure OKX OHLCV output matches the column names and CSV format produced by the Yahoo Finance path, so downstream indicator code requires no special-casing.

#### Scenario: CSV header compatibility
- **WHEN** the OKX stock-data function returns a CSV string
- **THEN** its header row contains `Date,Open,High,Low,Close,Volume` and numeric values are rounded consistently with the Yahoo path
