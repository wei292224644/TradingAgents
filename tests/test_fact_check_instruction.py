"""News and sentiment analyst prompts must tell the LLM to sanity-check
verifiable factual claims (e.g. "SpaceX joins Nasdaq 100") before treating
them as catalysts.

Regression for a live run where a Bitget promotional article claimed a
private, never-IPO'd company had joined a stock index — the news and
sentiment analysts took it at face value and built a bullish thesis on it;
only the downstream bear/research-manager debate caught the impossibility.
"""

import inspect

import pytest

import tradingagents.agents.analysts.news_analyst as na
import tradingagents.agents.analysts.sentiment_analyst as sa


@pytest.mark.unit
def test_news_prompt_instructs_fact_check_of_verifiable_claims():
    src = inspect.getsource(na)
    assert "fact-check" in src.lower() or "sanity-check" in src.lower()


@pytest.mark.unit
def test_sentiment_prompt_instructs_fact_check_of_verifiable_claims():
    src = inspect.getsource(sa)
    assert "fact-check" in src.lower() or "sanity-check" in src.lower()
