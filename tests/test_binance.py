"""Tests for the Binance spot market-data vendor."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tradingagents.dataflows import binance


def _day_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _kline(open_ms: int, o=1.0, h=2.0, l=0.5, c=1.5, vol=1000.0):
    """One Binance kline row (ascending endpoint order)."""
    return [
        open_ms, str(o), str(h), str(l), str(c), str(vol),
        open_ms + 86_399_999, "0", 100, "0", "0", "0",
    ]


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _one_page_then_empty(klines):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _FakeResponse(klines if calls["n"] == 1 else [])

    return fake_urlopen


@pytest.fixture(autouse=True)
def _tmp_cache_dir(tmp_path):
    from tradingagents.dataflows.config import set_config

    set_config({"data_cache_dir": str(tmp_path / "cache")})
    yield


@pytest.mark.unit
class TestLoadBinanceOhlcv:
    def test_parses_klines_into_ohlcv_frame(self):
        klines = [
            _kline(_day_ms("2026-07-06"), o=0.72, h=0.75, l=0.70, c=0.719, vol=7e6),
            _kline(_day_ms("2026-07-07"), o=0.719, h=0.733, l=0.702, c=0.709, vol=6.9e6),
        ]
        with patch.object(binance, "urlopen", _one_page_then_empty(klines)):
            df = binance.load_binance_ohlcv("币安人生-USD", "2026-07-08")

        assert list(df.columns[:6]) == ["Date", "Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 2
        assert float(df.iloc[-1]["Close"]) == 0.709

    def test_paginates_past_page_limit(self):
        # 1200 daily klines: Binance caps a page at 1000, so 2 requests needed.
        first_day = datetime(2023, 1, 1, tzinfo=timezone.utc)
        klines = [
            _kline(int((first_day + timedelta(days=i)).timestamp() * 1000), c=1.0 + i * 0.001)
            for i in range(1200)
        ]
        pages = [klines[:1000], klines[1000:], []]
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            page = pages[min(calls["n"], len(pages) - 1)]
            calls["n"] += 1
            return _FakeResponse(page)

        with patch.object(binance, "urlopen", fake_urlopen):
            df = binance.load_binance_ohlcv("币安人生-USD", "2026-07-08")

        assert len(df) == 1200
        assert calls["n"] >= 2


@pytest.mark.unit
class TestGetBinanceStockData:
    def test_unicode_symbol_resolves_and_labels_source(self):
        seen = {"urls": []}
        klines = [_kline(_day_ms("2026-07-07"), c=0.709)]

        def fake_urlopen(req, timeout=None):
            seen["urls"].append(req.full_url)
            return _FakeResponse(klines if len(seen["urls"]) == 1 else [])

        with patch.object(binance, "urlopen", fake_urlopen):
            out = binance.get_binance_stock_data("币安人生-USDT", "2026-07-01", "2026-07-08")

        from urllib.parse import quote
        assert quote("币安人生USDT") in seen["urls"][0]  # URL-encoded Unicode symbol
        assert "Binance spot symbol 币安人生USDT" in out
        assert "Date,Open,High,Low,Close,Volume" in out
        assert "0.709" in out

    def test_no_data_raises_typed_error(self):
        from tradingagents.dataflows.errors import NoMarketDataError

        def empty_urlopen(req, timeout=None):
            return _FakeResponse([])

        with patch.object(binance, "urlopen", empty_urlopen):
            with pytest.raises(NoMarketDataError):
                binance.get_binance_stock_data("币安人生-USDT", "2026-07-01", "2026-07-08")


@pytest.mark.unit
class TestBinanceRateLimit:
    def test_throttle_then_success_retries(self):
        from urllib.error import HTTPError

        klines = [_kline(_day_ms("2026-07-07"))]
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
            return _FakeResponse(klines if calls["n"] == 2 else [])

        with patch.object(binance, "urlopen", fake_urlopen), \
             patch.object(binance.time, "sleep") as fake_sleep:
            df = binance.load_binance_ohlcv("币安人生-USD", "2026-07-08")

        assert len(df) == 1
        assert fake_sleep.called

    def test_unknown_symbol_400_falls_through_to_no_data(self):
        from urllib.error import HTTPError

        from tradingagents.dataflows.errors import NoMarketDataError

        def fake_urlopen(req, timeout=None):
            raise HTTPError(req.full_url, 400, "Bad Request", {}, None)

        with patch.object(binance, "urlopen", fake_urlopen):
            with pytest.raises(NoMarketDataError):
                binance.load_binance_ohlcv("币安人生-USD", "2026-07-08")


@pytest.mark.unit
class TestBinanceVendorIntegration:
    def test_binance_registered_for_get_stock_data(self):
        from tradingagents.dataflows import interface

        assert "binance" in interface.VENDOR_METHODS["get_stock_data"]
        assert "binance" in interface.VENDOR_LIST

    def test_load_ohlcv_falls_back_okx_to_binance(self):
        from tradingagents.dataflows import okx
        from tradingagents.dataflows.config import set_config
        from tradingagents.dataflows.stockstats_utils import load_ohlcv

        set_config({"data_vendors": {"core_stock_apis": "okx,binance,yfinance"}})
        klines = [_kline(_day_ms("2026-07-07"), c=0.709)]

        def okx_empty(req, timeout=None):
            return _FakeResponse({"code": "51001", "msg": "no instrument", "data": []})

        with patch.object(okx, "urlopen", okx_empty), \
             patch.object(binance, "urlopen", _one_page_then_empty(klines)):
            df = load_ohlcv("币安人生-USD", "2026-07-08")

        assert len(df) == 1
        assert float(df.iloc[0]["Close"]) == 0.709

    def test_cli_crypto_chain_includes_binance(self):
        import cli.main as m

        selections = {
            "research_depth": 1,
            "shallow_thinker": "gpt-5.4-mini",
            "deep_thinker": "gpt-5.5",
            "backend_url": None,
            "llm_provider": "openai",
            "asset_type": "crypto",
        }
        cfg = m._build_run_config(selections, checkpoint=None)
        assert cfg["data_vendors"]["core_stock_apis"] == "okx,binance,yfinance"
