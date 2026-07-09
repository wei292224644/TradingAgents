"""Apify StockTwits-scraper fallback: used when StockTwits' own API 403s
(Cloudflare bot-challenge, verified live — every symbol, not just crypto).

Reuses the pipeline's `BASE.X` / plain-ticker symbol convention and renders
messages in the same Bullish/Bearish/Unlabeled format as the direct
StockTwits path, so the sentiment-analyst prompt needs no rewording.
"""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import patch

import pytest

from tradingagents.dataflows import apify_stocktwits


def _fake_message(sentiment=None, body="test message", symbol="AAPL"):
    return {
        "messageId": 1,
        "body": body,
        "sentiment": sentiment,
        "symbols": [symbol],
        "username": "trader1",
        "createdAt": "2026-07-09T04:00:00Z",
        "url": "https://stocktwits.com/trader1/message/1",
    }


@pytest.mark.unit
class TestApifyStockTwitsConfig:
    def test_missing_token_returns_placeholder_without_request(self, monkeypatch):
        monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
        with patch.object(apify_stocktwits, "urlopen") as mock_urlopen:
            out = apify_stocktwits.fetch_apify_stocktwits_messages("AAPL")
        mock_urlopen.assert_not_called()
        assert "unavailable" in out.lower()
        assert "not configured" in out.lower()


@pytest.mark.unit
class TestApifyStockTwitsSymbolMapping:
    def test_crypto_symbol_maps_to_dot_x(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["body"] = json.loads(req.data)
            raise TimeoutError("stop after capturing request")

        with patch.object(apify_stocktwits, "urlopen", side_effect=fake_urlopen):
            apify_stocktwits.fetch_apify_stocktwits_messages("BTC-USD")
        assert seen["body"]["symbols"] == ["BTC.X"]

    def test_stock_symbol_passes_through_upper(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["body"] = json.loads(req.data)
            raise TimeoutError("stop after capturing request")

        with patch.object(apify_stocktwits, "urlopen", side_effect=fake_urlopen):
            apify_stocktwits.fetch_apify_stocktwits_messages("aapl")
        assert seen["body"]["symbols"] == ["AAPL"]


@pytest.mark.unit
class TestApifyStockTwitsFormatting:
    def test_renders_same_format_as_direct_stocktwits(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        items = [
            _fake_message(sentiment="Bullish", body="to the moon"),
            _fake_message(sentiment="Bearish", body="selling now"),
            _fake_message(sentiment=None, body="just watching"),
        ]

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return json.dumps(items).encode()

        with patch.object(apify_stocktwits, "urlopen", return_value=_Resp()):
            out = apify_stocktwits.fetch_apify_stocktwits_messages("AAPL", limit=30)

        assert "Bullish: 1" in out
        assert "Bearish: 1" in out
        assert "Unlabeled: 1" in out
        assert "to the moon" in out
        assert "selling now" in out

    def test_unescapes_html_entities_in_body(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        items = [_fake_message(body="that&#39;s a big move &amp; then some")]

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return json.dumps(items).encode()

        with patch.object(apify_stocktwits, "urlopen", return_value=_Resp()):
            out = apify_stocktwits.fetch_apify_stocktwits_messages("AAPL")
        assert "that's a big move & then some" in out
        assert "&#39;" not in out

    def test_empty_dataset_returns_no_messages_placeholder(self, monkeypatch):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return b"[]"

        with patch.object(apify_stocktwits, "urlopen", return_value=_Resp()):
            out = apify_stocktwits.fetch_apify_stocktwits_messages("ZZZZ")
        assert "no" in out.lower()
        assert "zzzz" in out.lower()


@pytest.mark.unit
class TestApifyStockTwitsResilience:
    @pytest.mark.parametrize(
        "exc",
        [
            urllib.error.HTTPError("url", 401, "unauthorized", {}, None),
            urllib.error.URLError("connection refused"),
            TimeoutError("slow"),
        ],
    )
    def test_transport_errors_return_placeholder(self, monkeypatch, exc):
        monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
        with patch.object(apify_stocktwits, "urlopen", side_effect=exc):
            out = apify_stocktwits.fetch_apify_stocktwits_messages("AAPL")
        assert "unavailable" in out.lower()
