"""Binance spot market-data vendor.

Complements the OKX vendor: Binance lists tokens OKX doesn't — including
Chinese-named meme coins whose spot symbol is literally the Unicode name
(``币安人生USDT``). The public ``/api/v3/klines`` endpoint needs no API key
and returns ascending daily candles.

Same contract as ``okx.py``: pipeline symbols arrive as canonical
``BASE-USD``; the adapter tries ``<BASE>USDT`` then ``<BASE>USDC`` and
reports which instrument served the data. Output matches the yfinance
DataFrame/CSV shape (``Date,Open,High,Low,Close,Volume``).

Note: Binance blocks some regions (HTTP 451). That surfaces as a vendor
failure the router logs and skips, so a configured fallback still serves
the call.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import get_config
from .errors import NoMarketDataError, VendorRateLimitError
from .symbol_utils import crypto_base, normalize_symbol
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

_API = "https://api.binance.com/api/v3/klines?{qs}"
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"

# Binance allows up to 1000 klines per request; 5y of dailies needs 2 pages.
_PAGE_LIMIT = 1000

# Quote assets to try, in order, for a canonical BASE-USD symbol.
_QUOTE_PREFERENCE = ("USDT", "USDC")


def binance_symbols(symbol: str) -> list[str]:
    """Binance spot symbol candidates for a pipeline symbol, in order."""
    base = crypto_base(symbol)
    if base is None:
        return []
    return [f"{base}{quote}" for quote in _QUOTE_PREFERENCE]


def _binance_get(params: dict, timeout: float = 10.0) -> list[list]:
    """One GET against the klines endpoint. Returns kline rows.

    HTTP 429/418 (throttle/ban) raise VendorRateLimitError for the retry
    wrapper; HTTP 400 (unknown symbol, code -1121) returns an empty list so
    callers move to the next quote candidate. Other HTTP errors propagate to
    the router, which logs and tries the next vendor (e.g. 451 geo-block).
    """
    url = _API.format(qs=urlencode(params))
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()) or []
    except HTTPError as exc:
        if exc.code in (429, 418):
            raise VendorRateLimitError(f"Binance rate limit (HTTP {exc.code})") from exc
        if exc.code == 400:
            logger.info("Binance has no symbol %s (HTTP 400)", params.get("symbol"))
            return []
        raise


def _binance_get_with_retry(params: dict, max_retries: int = 3, base_delay: float = 1.0) -> list[list]:
    """Retry throttle responses with exponential backoff before giving up."""
    for attempt in range(max_retries):
        try:
            return _binance_get(params)
        except VendorRateLimitError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("Binance rate-limited; retrying in %.1fs", delay)
            time.sleep(delay)
    return []  # unreachable; keeps type checkers happy


def _fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    """All daily klines for ``symbol`` in [start_ms, end_ms], ascending.

    Binance pages forward in time: the next request starts one millisecond
    after the last open time. Stops on an empty page or once past the window.
    """
    rows: list[list] = []
    cursor = start_ms
    while cursor <= end_ms:
        page = _binance_get_with_retry({
            "symbol": symbol,
            "interval": "1d",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": _PAGE_LIMIT,
        })
        if not page:
            break
        rows.extend(page)
        if len(page) < _PAGE_LIMIT:
            break
        cursor = int(page[-1][0]) + 1
    return rows


def _klines_to_frame(rows: list[list]) -> pd.DataFrame:
    """Binance kline rows -> DataFrame(Date,Open,High,Low,Close,Volume)."""
    records = []
    for r in rows:
        ts = datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc)
        records.append({
            "Date": ts.strftime("%Y-%m-%d"),
            "Open": float(r[1]),
            "High": float(r[2]),
            "Low": float(r[3]),
            "Close": float(r[4]),
            "Volume": float(r[5]),
        })
    df = pd.DataFrame.from_records(records, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    if not df.empty:
        df = df.drop_duplicates(subset="Date").sort_values("Date").reset_index(drop=True)
    return df


def _fetch_binance_frame(symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str]:
    """OHLCV for a pipeline symbol, trying each Binance symbol candidate."""
    canonical = normalize_symbol(symbol)
    candidates = binance_symbols(canonical)
    if not candidates:
        raise NoMarketDataError(symbol, canonical, "not a crypto symbol; Binance vendor serves crypto only")

    start_ms = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    end_ms = int(end_dt.timestamp() * 1000) - 1

    for candidate in candidates:
        rows = _fetch_klines(candidate, start_ms, end_ms)
        if rows:
            return _klines_to_frame(rows), candidate
        logger.info("Binance has no 1d klines for %s; trying next quote", candidate)

    raise NoMarketDataError(
        symbol, canonical,
        f"no Binance klines for any of {candidates} between {start_date} and {end_date}",
    )


def load_binance_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """OHLCV history from Binance with per-symbol caching and look-ahead filter.

    Mirrors ``load_okx_ohlcv``: fixed 5y-to-today window cached per symbol,
    rows after ``curr_date`` filtered out.
    """
    canonical = normalize_symbol(symbol)
    safe_symbol = safe_ticker_component(canonical)
    config = get_config()

    today = pd.Timestamp.today()
    start_str = (today - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(
        config["data_cache_dir"],
        f"{safe_symbol}-Binance-data-{start_str}-{end_str}.csv",
    )

    data = None
    if os.path.exists(data_file):
        cached = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
        if not cached.empty and "Close" in cached.columns:
            data = cached

    if data is None:
        data, _ = _fetch_binance_frame(canonical, start_str, end_str)
        data.to_csv(data_file, index=False, encoding="utf-8")

    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])
    data = data[data["Date"] <= pd.to_datetime(curr_date)].sort_values("Date").reset_index(drop=True)
    return data


def get_binance_stock_data(
    symbol: Annotated[str, "ticker symbol of the asset"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """OHLCV between two dates as a CSV string, Yahoo-path compatible."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    canonical = normalize_symbol(symbol)
    frame, instrument = _fetch_binance_frame(canonical, start_date, end_date)

    if frame.empty:
        raise NoMarketDataError(
            symbol, canonical, f"no rows between {start_date} and {end_date}"
        )

    # No decimal rounding — micro-price tokens collapse under fixed decimals;
    # 12 significant digits handle any price magnitude (same as the OKX path).
    csv_string = frame.to_csv(index=False, float_format="%.12g")

    label = canonical if canonical == symbol.upper() else f"{canonical} (from {symbol})"
    header = f"# Stock data for {label} from {start_date} to {end_date}\n"
    header += f"# Source: Binance spot symbol {instrument} (USDT/USDC quoted; 1 USDT ≈ 1 USD)\n"
    header += f"# Total records: {len(frame)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string
