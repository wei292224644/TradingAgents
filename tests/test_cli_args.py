"""CLI argument overrides for analyze (hybrid mode).

Precedence: CLI args > TRADINGAGENTS_* env > interactive prompts.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest
import typer

import cli.main as m
from cli.models import AnalystType
from cli.utils import (
    parse_analysts_arg,
    validate_analysis_date_arg,
    validate_provider_arg,
    validate_research_depth_arg,
    validate_ticker_arg,
)


@pytest.mark.unit
class TestCliArgParsers:
    def test_validate_ticker_arg_normalizes(self):
        assert validate_ticker_arg("aapl") == "AAPL"

    def test_validate_ticker_arg_rejects_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_ticker_arg("   ")

    def test_validate_analysis_date_arg_accepts_today(self):
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        assert validate_analysis_date_arg(today) == today

    def test_validate_analysis_date_arg_rejects_future(self):
        with pytest.raises(ValueError, match="future"):
            validate_analysis_date_arg("2999-01-01")

    def test_parse_analysts_arg_comma_and_space(self):
        assert parse_analysts_arg("market, news") == [
            AnalystType.MARKET,
            AnalystType.NEWS,
        ]
        assert parse_analysts_arg("market social") == [
            AnalystType.MARKET,
            AnalystType.SOCIAL,
        ]

    def test_parse_analysts_arg_rejects_unknown(self):
        with pytest.raises(ValueError, match="unknown analyst"):
            parse_analysts_arg("market,wizard")

    def test_validate_research_depth_arg(self):
        assert validate_research_depth_arg(5) == 5
        with pytest.raises(ValueError, match="1, 3, 5"):
            validate_research_depth_arg(2)

    def test_validate_provider_arg(self):
        assert validate_provider_arg("DeepSeek") == "deepseek"
        with pytest.raises(ValueError, match="unknown provider"):
            validate_provider_arg("not-a-provider")


@pytest.mark.unit
class TestBuildCliOverrides:
    def test_only_provided_keys_are_included(self):
        overrides = m.build_cli_overrides(ticker="NVDA", provider="deepseek")
        assert set(overrides) == {"ticker", "provider"}
        assert overrides["ticker"] == "NVDA"
        assert overrides["provider"] == "deepseek"

    def test_positional_and_option_ticker_must_agree(self):
        with pytest.raises(typer.BadParameter, match="conflicting tickers"):
            m.build_cli_overrides(ticker_arg="AAPL", ticker="NVDA")

    def test_invalid_analysts_raise_bad_parameter(self):
        with pytest.raises(typer.BadParameter, match="unknown analyst"):
            m.build_cli_overrides(analysts="nope")

    def test_invalid_research_depth_raise_bad_parameter(self):
        with pytest.raises(typer.BadParameter, match="1, 3, 5"):
            m.build_cli_overrides(research_depth=4)

    def test_mandate_empty_string_is_kept(self):
        overrides = m.build_cli_overrides(mandate="")
        assert "mandate" in overrides
        assert overrides["mandate"] == ""

    def test_save_and_display_flags(self):
        overrides = m.build_cli_overrides(
            save_report=False,
            display_report=True,
            report_dir=Path("/tmp/reports"),
        )
        assert overrides["save_report"] is False
        assert overrides["display_report"] is True
        assert overrides["report_dir"] == Path("/tmp/reports")


@pytest.mark.unit
class TestCliArgsSkipPrompts:
    def test_full_cli_overrides_skip_all_selection_prompts(self):
        for key in (
            "TRADINGAGENTS_LLM_PROVIDER",
            "TRADINGAGENTS_DEEP_THINK_LLM",
            "TRADINGAGENTS_QUICK_THINK_LLM",
            "TRADINGAGENTS_OUTPUT_LANGUAGE",
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS",
            "TRADINGAGENTS_MAX_RISK_ROUNDS",
            "TRADINGAGENTS_MANDATE",
        ):
            os.environ.pop(key, None)

        overrides = m.build_cli_overrides(
            ticker="NVDA",
            date="2026-01-15",
            mandate="focus on AI semis",
            language="Chinese",
            analysts="market,social,news,fundamentals",
            research_depth=5,
            provider="deepseek",
            quick_model="deepseek-v4-flash",
            deep_model="deepseek-v4-pro",
        )

        with mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker") as prompt_ticker, \
             mock.patch.object(m, "get_analysis_date") as prompt_date, \
             mock.patch.object(m, "get_trading_mandate") as prompt_mandate, \
             mock.patch.object(m, "select_analysts") as prompt_analysts, \
             mock.patch.object(m, "select_research_depth") as prompt_depth, \
             mock.patch.object(m, "ensure_api_key") as ensure_key, \
             mock.patch.object(m, "select_llm_provider") as prompt_provider, \
             mock.patch.object(m, "ask_output_language") as prompt_lang, \
             mock.patch.object(m, "select_shallow_thinking_agent") as prompt_quick, \
             mock.patch.object(m, "select_deep_thinking_agent") as prompt_deep:
            sel = m.get_user_selections(cli_overrides=overrides)

        prompt_ticker.assert_not_called()
        prompt_date.assert_not_called()
        prompt_mandate.assert_not_called()
        prompt_analysts.assert_not_called()
        prompt_depth.assert_not_called()
        prompt_provider.assert_not_called()
        prompt_lang.assert_not_called()
        prompt_quick.assert_not_called()
        prompt_deep.assert_not_called()
        ensure_key.assert_called_once_with("deepseek")

        assert sel["ticker"] == "NVDA"
        assert sel["analysis_date"] == "2026-01-15"
        assert sel["trading_mandate"] == "focus on AI semis"
        assert sel["output_language"] == "Chinese"
        assert [a.value for a in sel["analysts"]] == [
            "market",
            "social",
            "news",
            "fundamentals",
        ]
        assert sel["research_depth"] == 5
        assert sel["research_depth_from_cli"] is True
        assert sel["llm_provider"] == "deepseek"
        assert sel["shallow_thinker"] == "deepseek-v4-flash"
        assert sel["deep_thinker"] == "deepseek-v4-pro"

    def test_partial_cli_skips_only_provided_steps(self):
        for key in (
            "TRADINGAGENTS_LLM_PROVIDER",
            "TRADINGAGENTS_DEEP_THINK_LLM",
            "TRADINGAGENTS_QUICK_THINK_LLM",
            "TRADINGAGENTS_OUTPUT_LANGUAGE",
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS",
            "TRADINGAGENTS_MAX_RISK_ROUNDS",
            "TRADINGAGENTS_MANDATE",
        ):
            os.environ.pop(key, None)

        overrides = m.build_cli_overrides(ticker="NVDA", provider="deepseek")

        with mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker") as prompt_ticker, \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29") as prompt_date, \
             mock.patch.object(m, "get_trading_mandate", return_value="") as prompt_mandate, \
             mock.patch.object(
                 m, "select_analysts", return_value=[AnalystType.MARKET]
             ) as prompt_analysts, \
             mock.patch.object(m, "select_research_depth", return_value=3) as prompt_depth, \
             mock.patch.object(m, "ensure_api_key"), \
             mock.patch.object(m, "select_llm_provider") as prompt_provider, \
             mock.patch.object(m, "ask_output_language", return_value="English") as prompt_lang, \
             mock.patch.object(
                 m, "select_shallow_thinking_agent", return_value="deepseek-v4-flash"
             ) as prompt_quick, \
             mock.patch.object(
                 m, "select_deep_thinking_agent", return_value="deepseek-v4-pro"
             ) as prompt_deep:
            sel = m.get_user_selections(cli_overrides=overrides)

        prompt_ticker.assert_not_called()
        prompt_provider.assert_not_called()
        # Omitted steps still prompt.
        prompt_date.assert_called_once()
        prompt_mandate.assert_called_once()
        prompt_analysts.assert_called_once()
        prompt_depth.assert_called_once()
        prompt_lang.assert_called_once()
        prompt_quick.assert_called_once()
        prompt_deep.assert_called_once()

        assert sel["ticker"] == "NVDA"
        assert sel["llm_provider"] == "deepseek"
        assert sel["research_depth"] == 3
        assert sel["research_depth_from_cli"] is False

    def test_cli_wins_over_env(self):
        env = {
            "TRADINGAGENTS_LLM_PROVIDER": "openai",
            "TRADINGAGENTS_DEEP_THINK_LLM": "gpt-5.5",
            "TRADINGAGENTS_QUICK_THINK_LLM": "gpt-5.4-mini",
            "TRADINGAGENTS_OUTPUT_LANGUAGE": "Japanese",
        }
        fake_cfg = dict(m.DEFAULT_CONFIG)
        fake_cfg.update(
            {
                "llm_provider": "openai",
                "quick_think_llm": "gpt-5.4-mini",
                "deep_think_llm": "gpt-5.5",
                "output_language": "Japanese",
            }
        )
        overrides = m.build_cli_overrides(
            provider="deepseek",
            language="Chinese",
            quick_model="deepseek-v4-flash",
            deep_model="deepseek-v4-pro",
        )

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(m, "DEFAULT_CONFIG", fake_cfg), \
             mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker", return_value="AAPL"), \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29"), \
             mock.patch.object(m, "get_trading_mandate", return_value=""), \
             mock.patch.object(m, "select_analysts", return_value=[AnalystType.MARKET]), \
             mock.patch.object(m, "select_research_depth", return_value=1), \
             mock.patch.object(m, "ensure_api_key"), \
             mock.patch.object(m, "select_llm_provider") as prompt_provider, \
             mock.patch.object(m, "ask_output_language") as prompt_lang, \
             mock.patch.object(m, "select_shallow_thinking_agent") as prompt_quick, \
             mock.patch.object(m, "select_deep_thinking_agent") as prompt_deep:
            sel = m.get_user_selections(cli_overrides=overrides)

        prompt_provider.assert_not_called()
        prompt_lang.assert_not_called()
        prompt_quick.assert_not_called()
        prompt_deep.assert_not_called()
        assert sel["llm_provider"] == "deepseek"
        assert sel["output_language"] == "Chinese"
        assert sel["shallow_thinker"] == "deepseek-v4-flash"
        assert sel["deep_thinker"] == "deepseek-v4-pro"


@pytest.mark.unit
def test_cli_research_depth_wins_in_build_run_config(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "2")
    monkeypatch.setenv("TRADINGAGENTS_MAX_RISK_ROUNDS", "4")
    patched = dict(m.DEFAULT_CONFIG, max_debate_rounds=2, max_risk_discuss_rounds=4)
    selections = {
        "research_depth": 5,
        "research_depth_from_cli": True,
        "shallow_thinker": "deepseek-v4-flash",
        "deep_thinker": "deepseek-v4-pro",
        "backend_url": None,
        "llm_provider": "deepseek",
        "google_thinking_level": None,
        "openai_reasoning_effort": None,
        "anthropic_effort": None,
        "output_language": "Chinese",
        "asset_type": "stock",
    }
    with mock.patch.object(m, "DEFAULT_CONFIG", patched):
        cfg = m._build_run_config(selections, checkpoint=None)
    assert cfg["max_debate_rounds"] == 5
    assert cfg["max_risk_discuss_rounds"] == 5


@pytest.mark.unit
def test_analyze_rejects_invalid_analysts_via_typer():
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        m.app,
        ["analyze", "--analysts", "nope", "--ticker", "NVDA"],
    )
    assert result.exit_code != 0
    assert "unknown analyst" in result.output.lower() or "Invalid value" in result.output


@pytest.mark.unit
def test_analyze_rejects_invalid_research_depth_via_typer():
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        m.app,
        ["analyze", "--research-depth", "4", "--ticker", "NVDA"],
    )
    assert result.exit_code != 0
