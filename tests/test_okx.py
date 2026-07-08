"""Tests for the OKX public market-data vendor."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tradingagents.dataflows import okx


def _candle(ts_ms: int, o=1.0, h=2.0, l=0.5, c=1.5, vol=1000.0):
    """One OKX candle row: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]."""
    return [str(ts_ms), str(o), str(h), str(l), str(c), str(vol), "0", "0", "1"]


def _day_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _one_page_then_empty(candles):
    """urlopen stub: first call returns candles, later calls return no data."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse({"code": "0", "msg": "", "data": candles})
        return _FakeResponse({"code": "0", "msg": "", "data": []})

    return fake_urlopen


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path):
    """Keep OKX cache files out of the real user cache directory."""
    from tradingagents.dataflows.config import set_config

    set_config({"data_cache_dir": str(tmp_path / "cache")})
    yield


@pytest.mark.unit
class TestLoadOkxOhlcv:
    def test_parses_candles_into_ohlcv_frame(self):
        candles = [
            _candle(_day_ms("2026-07-07"), o=1.10, h=1.30, l=1.00, c=1.25, vol=5000),
            _candle(_day_ms("2026-07-06"), o=1.00, h=1.15, l=0.95, c=1.10, vol=4000),
        ]
        with patch.object(okx, "urlopen", _one_page_then_empty(candles)):
            df = okx.load_okx_ohlcv("SPCXB-USD", "2026-07-08")

        assert list(df.columns[:6]) == ["Date", "Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 2
        # Oldest row first, like the Yahoo path.
        assert df.iloc[0]["Close"] == 1.10
        assert df.iloc[-1]["Close"] == 1.25

    def test_paginates_past_single_page_limit(self):
        # 150 daily candles: OKX caps a page at 100, so this needs 2 requests.
        base_day = datetime(2026, 7, 7, tzinfo=timezone.utc)
        candles = [
            _candle(int((base_day - timedelta(days=i)).timestamp() * 1000), c=float(i + 1))
            for i in range(150)
        ]
        pages = [candles[:100], candles[100:], []]
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            page = pages[min(calls["n"], len(pages) - 1)]
            calls["n"] += 1
            return _FakeResponse({"code": "0", "msg": "", "data": page})

        with patch.object(okx, "urlopen", fake_urlopen):
            df = okx.load_okx_ohlcv("SPCXB-USD", "2026-07-08")

        assert len(df) == 150
        assert calls["n"] >= 2


@pytest.mark.unit
class TestGetOkxStockData:
    def test_returns_yahoo_compatible_csv(self):
        candles = [
            _candle(_day_ms("2026-07-07"), o=0.0041, h=0.0043, l=0.0040, c=0.0042, vol=9e9),
            _candle(_day_ms("2026-07-06"), o=0.0040, h=0.0042, l=0.0039, c=0.0041, vol=8e9),
        ]
        with patch.object(okx, "urlopen", _one_page_then_empty(candles)):
            out = okx.get_okx_stock_data("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "Date,Open,High,Low,Close,Volume" in out
        assert "# Stock data for SPCXB-USD" in out
        # Sub-cent meme prices must not be rounded away to 0.00.
        assert "0.0042" in out
        # Report names the OKX instrument that actually served the data.
        assert "SPCXB-USDT" in out

    def test_no_data_raises_typed_error(self):
        from tradingagents.dataflows.errors import NoMarketDataError

        def empty_urlopen(req, timeout=None):
            return _FakeResponse({"code": "0", "msg": "", "data": []})

        with patch.object(okx, "urlopen", empty_urlopen):
            with pytest.raises(NoMarketDataError):
                okx.get_okx_stock_data("SPCXB-USDT", "2026-07-01", "2026-07-08")


@pytest.mark.unit
class TestOkxRateLimit:
    def test_throttle_then_success_retries(self):
        candles = [_candle(_day_ms("2026-07-07"))]
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return _FakeResponse({"code": "50011", "msg": "Requests too frequent."})
            if calls["n"] == 2:
                return _FakeResponse({"code": "0", "msg": "", "data": candles})
            return _FakeResponse({"code": "0", "msg": "", "data": []})

        with patch.object(okx, "urlopen", fake_urlopen), \
             patch.object(okx.time, "sleep") as fake_sleep:
            df = okx.load_okx_ohlcv("SPCXB-USD", "2026-07-08")

        assert len(df) == 1
        assert fake_sleep.called

    def test_persistent_throttle_raises_rate_limit_error(self):
        from tradingagents.dataflows.errors import VendorRateLimitError

        def throttled_urlopen(req, timeout=None):
            return _FakeResponse({"code": "50011", "msg": "Requests too frequent."})

        with patch.object(okx, "urlopen", throttled_urlopen), \
             patch.object(okx.time, "sleep"):
            with pytest.raises(VendorRateLimitError):
                okx.load_okx_ohlcv("SPCXB-USD", "2026-07-08")


@pytest.mark.unit
class TestOkxInstrumentFallback:
    def test_falls_back_to_usdc_when_usdt_missing(self):
        candles = [_candle(_day_ms("2026-07-07"))]

        def fake_urlopen(req, timeout=None):
            if "USDT" in req.full_url:
                return _FakeResponse({"code": "51001", "msg": "Instrument ID does not exist"})
            if "USDC" in req.full_url and "after" in req.full_url:
                # First USDC page has data; further pages empty.
                fake_urlopen.usdc_calls = getattr(fake_urlopen, "usdc_calls", 0) + 1
                if fake_urlopen.usdc_calls == 1:
                    return _FakeResponse({"code": "0", "msg": "", "data": candles})
            return _FakeResponse({"code": "0", "msg": "", "data": []})

        with patch.object(okx, "urlopen", fake_urlopen):
            out = okx.get_okx_stock_data("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "SPCXB-USDC" in out  # header names the instrument actually used
