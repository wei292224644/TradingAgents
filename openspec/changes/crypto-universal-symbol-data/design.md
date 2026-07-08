## Context

The framework currently treats crypto as a second-class asset type: symbol normalization hard-codes only 11 bases (`tradingagents/dataflows/symbol_utils.py:45-47`), market data only goes through Yahoo Finance, and sentiment/news sources assume equity-style symbols. The result is that any token not on the whitelist—meme coins, new listings, smaller L1/L2 tokens—fails silently or produces fabricated data. This design keeps the existing stock/forex paths untouched while broadening the crypto path end-to-end.

## Goals / Non-Goals

**Goals:**
- Accept any dashed crypto pair (`BASE-QUOTE`) regardless of base whitelist.
- Fetch prices for any OKX-listed crypto token.
- Make indicators and verified snapshots work for those tokens.
- Fix social-sentiment symbol mapping so StockTwits and Reddit search correctly.
- Provide a free, zero-API-key news fallback for crypto via Google News RSS.
- Preserve existing behavior for stocks, forex, and the 11 compact-form large caps.

**Non-Goals:**
- Real-time WebSocket data or order-book analysis.
- Futures, perps, or leverage tokens beyond spot-style `BASE-USD/T/C`.
- Paid news APIs (CryptoPanic, etc.).
- On-chain metrics (wallet flows, exchange reserves).
- Changing the output format of existing reports.

## Decisions

1. **Dash as the crypto discriminator**
   - Any `BASE-QUOTE` with a dash is crypto; compact forms stay whitelist-only.
   - Rationale: avoids collision with forex (`EURUSD`) and matches OKX/TradingView conventions.

2. **Internal canonical form remains `BASE-USD`**
   - OKX adapter tries `BASE-USDT` then `BASE-USDC`; StockTwits maps to `BASE.X`; Reddit searches `BASE`.
   - Rationale: existing cache keys, indicator code, CLI suffix detection (`cli/utils.py:23`) already assume this form. Minimizes blast radius.

3. **Vendor chain `okx,yfinance` for crypto**
   - OKX primary, Yahoo fallback.
   - Rationale: OKX lists far more tokens than Yahoo; Yahoo still has better coverage for legacy large caps and avoids total failure if OKX rate-limits.

4. **`load_ohlcv` becomes vendor-aware**
   - Reads `get_vendor("core_stock_apis")` to decide whether to call OKX or Yahoo.
   - Rationale: indicators and verified snapshots both call `load_ohlcv`; one branch fixes both.

5. **Google News RSS instead of a paid crypto-news API**
   - No authentication, no quota management, consistent with existing RSS fetcher style.
   - Rationale: CryptoPanic free tier was discontinued in April 2026; meme-coin news is sparse anyway, so a lightweight RSS fallback is sufficient.

6. **No change to report schema or agent prompts**
   - Same analysts, same output format.
   - Rationale: data-source change only; prompt-level changes belong to the separate "user intent" change.

## Risks / Trade-offs

- **[Risk]** OKX public API may rate-limit or require authentication in the future.
  - **Mitigation**: keep yfinance fallback; document that heavy use may need API key or proxy later.
- **[Risk]** Meme coins on OKX may have very short trading history, producing thin indicators.
  - **Mitigation**: `load_ohlcv` and `build_verified_market_snapshot` already handle empty/short frames via `NoMarketDataError`; analysts receive explicit "insufficient data" signals.
- **[Risk]** Google News RSS query by token ticker (`SPCXB crypto`) may return irrelevant results.
  - **Mitigation**: search includes the literal token plus "crypto", and the analyst prompt already instructs analysts to weigh source quality/sample size.
- **[Risk]** Removing the whitelist changes behavior for some compact symbols.
  - **Mitigation**: compact path keeps the whitelist; only dashed inputs broaden.
- **[Risk]** Existing cache files for crypto may be keyed on Yahoo-normalized symbols.
  - **Mitigation**: crypto now uses its own OKX cache path keyed on canonical `BASE-USD`; old Yahoo cache files remain valid but are not reused, preventing stale/ mismatched data.

## Migration Plan

No database or remote state migration. Steps:
1. Deploy code changes.
2. Re-run any existing crypto analysis; old Yahoo cache is ignored and OKX cache is created alongside.
3. Monitor first few meme-coin runs for OKX rate-limit warnings.

## Open Questions

- None beyond the documented assumption that OKX public API remains unauthenticated.
