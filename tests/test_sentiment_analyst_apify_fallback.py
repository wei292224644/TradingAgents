"""Sentiment analyst falls back to the Apify StockTwits scraper only when
the direct StockTwits path is unavailable (Cloudflare now blocks it for
every symbol) — and never calls the paid fallback when direct data works,
since Apify is pay-per-event unlike every other vendor here.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tradingagents.agents.analysts.sentiment_analyst import create_sentiment_analyst
from tradingagents.agents.schemas import SentimentBand, SentimentReport


def _make_state():
    return {
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "asset_type": "stock",
        "messages": [],
    }


def _structured_llm(captured: dict):
    report = SentimentReport(
        overall_band=SentimentBand.NEUTRAL, overall_score=5.0,
        confidence="low", narrative="n/a",
    )
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or report
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.unit
class TestSentimentAnalystApifyFallback:
    def test_falls_back_to_apify_when_stocktwits_unavailable(self):
        captured = {}
        with (
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_stocktwits_messages",
                return_value="<stocktwits unavailable: HTTPError>",
            ),
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_apify_stocktwits_messages",
                return_value="APIFY-FALLBACK-CONTENT",
            ) as mock_apify,
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_reddit_posts",
                return_value="<no Reddit posts>",
            ),
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.get_news"
            ) as mock_get_news,
        ):
            mock_get_news.func.return_value = "<no news>"
            create_sentiment_analyst(_structured_llm(captured))(_make_state())

        mock_apify.assert_called_once()
        assert any("APIFY-FALLBACK-CONTENT" in str(m) for m in captured["prompt"])

    def test_does_not_call_apify_when_stocktwits_available(self):
        captured = {}
        with (
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_stocktwits_messages",
                return_value="Bullish: 5 (100%) · Bearish: 0 (0%) · Unlabeled: 0 · Total: 5 most-recent messages\n\nreal data",
            ),
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_apify_stocktwits_messages"
            ) as mock_apify,
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.fetch_reddit_posts",
                return_value="<no Reddit posts>",
            ),
            patch(
                "tradingagents.agents.analysts.sentiment_analyst.get_news"
            ) as mock_get_news,
        ):
            mock_get_news.func.return_value = "<no news>"
            create_sentiment_analyst(_structured_llm(captured))(_make_state())

        mock_apify.assert_not_called()
