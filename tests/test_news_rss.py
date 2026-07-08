"""Tests for the Google News RSS crypto-news fallback."""

from unittest.mock import patch

import pytest

from tradingagents.dataflows import news_rss


def _rss(items: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>"SPCXB crypto" - Google News</title>
{items}
</channel></rss>""".encode()


def _item(title: str, pub_date: str, source: str = "CoinDesk") -> str:
    return (
        "<item>"
        f"<title>{title}</title>"
        "<link>https://news.example/article</link>"
        f"<pubDate>{pub_date}</pubDate>"
        f"<source url=\"https://news.example\">{source}</source>"
        "</item>"
    )


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.mark.unit
class TestGoogleNewsRss:
    def test_parses_headlines_into_block(self):
        body = _rss(
            _item("SPCXB lists on major exchange", "Mon, 06 Jul 2026 12:00:00 GMT")
            + _item("SPCXB rallies 40%", "Tue, 07 Jul 2026 09:00:00 GMT")
        )
        with patch.object(news_rss, "urlopen", lambda req, timeout=None: _FakeResponse(body)):
            out = news_rss.get_news_google_rss("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "SPCXB lists on major exchange" in out
        assert "SPCXB rallies 40%" in out
        assert "CoinDesk" in out

    def test_excludes_articles_after_end_date(self):
        body = _rss(
            _item("Old enough", "Mon, 06 Jul 2026 12:00:00 GMT")
            + _item("Future leak", "Fri, 10 Jul 2026 12:00:00 GMT")
        )
        with patch.object(news_rss, "urlopen", lambda req, timeout=None: _FakeResponse(body)):
            out = news_rss.get_news_google_rss("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "Old enough" in out
        assert "Future leak" not in out

    def test_empty_result_returns_no_news_message(self):
        with patch.object(news_rss, "urlopen", lambda req, timeout=None: _FakeResponse(_rss(""))):
            out = news_rss.get_news_google_rss("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "No news found" in out
        assert "SPCXB" in out

    def test_network_failure_returns_placeholder(self):
        def broken_urlopen(req, timeout=None):
            raise TimeoutError("connection timed out")

        with patch.object(news_rss, "urlopen", broken_urlopen):
            out = news_rss.get_news_google_rss("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert out.startswith("<news unavailable")

    def test_crypto_query_uses_base_plus_crypto(self):
        seen = {}

        def capture_urlopen(req, timeout=None):
            seen["url"] = req.full_url
            return _FakeResponse(_rss(""))

        with patch.object(news_rss, "urlopen", capture_urlopen):
            news_rss.get_news_google_rss("SPCXB-USDT", "2026-07-01", "2026-07-08")

        assert "SPCXB+crypto" in seen["url"]


@pytest.mark.unit
class TestGoogleRssVendorRegistration:
    def test_google_rss_registered_for_get_news(self):
        from tradingagents.dataflows import interface

        assert "google_rss" in interface.VENDOR_METHODS["get_news"]
        assert "google_rss" in interface.VENDOR_LIST

    def test_route_to_vendor_dispatches_to_google_rss(self):
        from tradingagents.dataflows import interface
        from tradingagents.dataflows.config import set_config

        set_config({"tool_vendors": {"get_news": "google_rss"}})
        body = _rss(_item("SPCXB lists on major exchange", "Mon, 06 Jul 2026 12:00:00 GMT"))
        with patch.object(news_rss, "urlopen", lambda req, timeout=None: _FakeResponse(body)):
            out = interface.route_to_vendor(
                "get_news", "SPCXB-USDT", "2026-07-01", "2026-07-08"
            )

        assert "SPCXB lists on major exchange" in out

    def test_cli_crypto_selects_google_rss_news_tool(self):
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
        assert cfg["tool_vendors"]["get_news"] == "google_rss,yfinance"
        # Global/macro news keeps the category default (google_rss is not
        # registered for get_global_news).
        assert cfg["data_vendors"]["news_data"] == "yfinance"
