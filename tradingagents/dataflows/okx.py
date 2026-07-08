"""OKX public market-data vendor.

OKX lists thousands of spot pairs — including the meme coins Yahoo Finance
does not cover — and serves daily candles from its public, unauthenticated
market API (``/api/v5/market/history-candles``). This module fetches those
candles and normalizes them to the same DataFrame/CSV shape the yfinance
path produces (``Date,Open,High,Low,Close,Volume``) so the indicator and
verification pipelines need no vendor-specific handling.

Symbols arrive in the pipeline's canonical ``BASE-USD`` form; OKX quotes
spot almost exclusively against stablecoins, so the adapter tries
``BASE-USDT`` then ``BASE-USDC`` and reports which instrument actually
served the data.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import get_config
from .errors import NoMarketDataError, VendorRateLimitError
from .symbol_utils import crypto_base, normalize_symbol
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

_API = "https://www.okx.com/api/v5/market/history-candles?{qs}"
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"

# Candles per request. OKX caps history-candles at 100 rows per call.
_PAGE_LIMIT = 100

# Quote currencies to try, in order, when resolving the OKX instrument for a
# canonical BASE-USD symbol. OKX spot is quoted against stablecoins.
_QUOTE_PREFERENCE = ("USDT", "USDC")

# OKX error code for "requests too frequent".
_RATE_LIMIT_CODES = {"50011"}

# ``1Dutc`` gives daily candles aligned to UTC midnight (plain ``1D`` is UTC+8),
# matching the day boundaries the rest of the pipeline assumes.
_BAR = "1Dutc"


def okx_inst_ids(symbol: str) -> list[str]:
    """OKX instrument candidates for a pipeline symbol, in preference order."""
    base = crypto_base(symbol)
    if base is None:
        return []
    return [f"{base}-{quote}" for quote in _QUOTE_PREFERENCE]


def _okx_get(params: dict, timeout: float = 10.0) -> list[list[str]]:
    """One GET against the history-candles endpoint. Returns the candle rows.

    Raises VendorRateLimitError on OKX throttle responses so the retry wrapper
    (and ultimately the vendor router) can react; other non-zero OKX codes
    return an empty list, which callers treat as "no data for this instrument".
    """
    url = _API.format(qs=urlencode(params))
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())

    code = payload.get("code")
    if code in _RATE_LIMIT_CODES:
        raise VendorRateLimitError(f"OKX rate limit: {payload.get('msg', '')}")
    if code != "0":
        logger.warning("OKX returned code %s for %s: %s", code, params.get("instId"), payload.get("msg"))
        return []
    return payload.get("data") or []


def _okx_get_with_retry(params: dict, max_retries: int = 3, base_delay: float = 1.0) -> list[list[str]]:
    """Retry OKX throttle responses with exponential backoff before giving up."""
    for attempt in range(max_retries):
        try:
            return _okx_get(params)
        except VendorRateLimitError:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("OKX rate-limited; retrying in %.1fs", delay)
            time.sleep(delay)
    return []  # unreachable; keeps type checkers happy


def _fetch_candles(inst_id: str, start_ms: int, end_ms: int) -> list[list[str]]:
    """All daily candles for ``inst_id`` in [start_ms, end_ms], newest-first.

    OKX pages backwards in time: each response's oldest timestamp becomes the
    ``after`` cursor for the next request. Stops when a page is empty or the
    window start has been passed.
    """
    rows: list[list[str]] = []
    after = end_ms + 1  # 'after' is exclusive: returns rows with ts < after
    while True:
        page = _okx_get_with_retry({
            "instId": inst_id,
            "bar": _BAR,
            "limit": _PAGE_LIMIT,
            "after": after,
        })
        if not page:
            break
        rows.extend(page)
        oldest = int(page[-1][0])
        if oldest <= start_ms or len(page) < _PAGE_LIMIT:
            break
        after = oldest
    return [r for r in rows if start_ms <= int(r[0]) <= end_ms]


def _candles_to_frame(rows: list[list[str]]) -> pd.DataFrame:
    """OKX candle rows -> DataFrame(Date,Open,High,Low,Close,Volume), oldest first."""
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


def _fetch_okx_frame(symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str]:
    """Fetch OHLCV for a pipeline symbol, trying each OKX instrument candidate.

    Returns (frame, inst_id) for the first instrument with data; raises
    NoMarketDataError when no candidate has any rows.
    """
    canonical = normalize_symbol(symbol)
    candidates = okx_inst_ids(canonical)
    if not candidates:
        raise NoMarketDataError(symbol, canonical, "not a crypto symbol; OKX serves crypto only")

    start_ms = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    end_ms = int(end_dt.timestamp() * 1000) - 1

    for inst_id in candidates:
        rows = _fetch_candles(inst_id, start_ms, end_ms)
        if rows:
            return _candles_to_frame(rows), inst_id
        logger.info("OKX has no %s candles for %s; trying next quote", _BAR, inst_id)

    raise NoMarketDataError(
        symbol, canonical,
        f"no OKX candles for any of {candidates} between {start_date} and {end_date}",
    )


def load_okx_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """OHLCV history from OKX with per-symbol caching and look-ahead filtering.

    Mirrors the contract of ``stockstats_utils.load_ohlcv``: fetch a fixed
    window (5y to today) once per symbol per day, cache it, and filter out
    rows after ``curr_date`` so backtests never see future prices.
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
        f"{safe_symbol}-OKX-data-{start_str}-{end_str}.csv",
    )

    data = None
    if os.path.exists(data_file):
        cached = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
        if not cached.empty and "Close" in cached.columns:
            data = cached

    if data is None:
        data, _ = _fetch_okx_frame(canonical, start_str, end_str)
        data.to_csv(data_file, index=False)

    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])
    data = data[data["Date"] <= pd.to_datetime(curr_date)].sort_values("Date").reset_index(drop=True)
    return data


def get_okx_stock_data(
    symbol: Annotated[str, "ticker symbol of the asset"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """OHLCV between two dates as a CSV string, Yahoo-path compatible."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    canonical = normalize_symbol(symbol)
    frame, inst_id = _fetch_okx_frame(canonical, start_date, end_date)

    if frame.empty:
        raise NoMarketDataError(
            symbol, canonical, f"no rows between {start_date} and {end_date}"
        )

    # No decimal rounding: micro-price tokens (PEPE trades near $0.000003)
    # collapse to identical OHLC values under any fixed decimal count. %.12g
    # keeps 12 significant digits for prices of any magnitude instead.
    csv_string = frame.to_csv(index=False, float_format="%.12g")

    label = canonical if canonical == symbol.upper() else f"{canonical} (from {symbol})"
    header = f"# Stock data for {label} from {start_date} to {end_date}\n"
    header += f"# Source: OKX spot instrument {inst_id} (USDT/USDC quoted; 1 USDT ≈ 1 USD)\n"
    header += f"# Total records: {len(frame)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + csv_string
