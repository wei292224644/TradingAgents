"""Tests for optional trading_mandate threading and prompt injection."""

import functools
import unittest
from unittest.mock import MagicMock

from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph


class TestCreateInitialStateMandate(unittest.TestCase):
    def test_create_initial_state_includes_trading_mandate(self):
        mandate = "Spot long-only; evaluate entry opportunity and entry zone"
        state = Propagator().create_initial_state(
            "BTC-USD",
            "2026-07-10",
            asset_type="crypto",
            trading_mandate=mandate,
        )
        self.assertEqual(state["trading_mandate"], mandate)

    def test_create_initial_state_defaults_mandate_to_empty(self):
        state = Propagator().create_initial_state("NVDA", "2026-07-10")
        self.assertEqual(state["trading_mandate"], "")


class TestPropagateThreadsMandate(unittest.TestCase):
    def _mock_graph(self, tmp_path):
        fake_state = {
            "final_trade_decision": "Rating: Hold",
            "company_of_interest": "BTC-USD",
            "trade_date": "2026-07-10",
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "investment_debate_state": {
                "bull_history": "",
                "bear_history": "",
                "history": "",
                "current_response": "",
                "judge_decision": "",
            },
            "investment_plan": "",
            "trader_investment_plan": "",
            "risk_debate_state": {
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "history": "",
                "judge_decision": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "",
                "count": 1,
                "latest_speaker": "",
            },
        }
        mock_graph = MagicMock()
        mock_graph.memory_log = MagicMock()
        mock_graph.memory_log.get_past_context.return_value = ""
        mock_graph.log_states_dict = {}
        mock_graph.debug = False
        mock_graph.config = {"results_dir": str(tmp_path)}
        mock_graph.graph.invoke.return_value = fake_state
        mock_graph.propagator.create_initial_state.return_value = fake_state
        mock_graph.propagator.get_graph_args.return_value = {}
        mock_graph.signal_processor.process_signal.return_value = "Hold"
        mock_graph.resolve_instrument_context.return_value = "ctx"
        mock_graph._run_graph = functools.partial(
            TradingAgentsGraph._run_graph, mock_graph
        )
        mock_graph._log_state = MagicMock()
        mock_graph.process_signal.return_value = "Hold"
        return mock_graph, fake_state

    def test_propagate_passes_mandate_into_initial_state(self, tmp_path=None):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            mock_graph, _ = self._mock_graph(Path(td))
            mandate = "Spot long-only; evaluate entry opportunity and entry zone"
            TradingAgentsGraph.propagate(
                mock_graph,
                "BTC-USD",
                "2026-07-10",
                asset_type="crypto",
                trading_mandate=mandate,
            )
            kwargs = mock_graph.propagator.create_initial_state.call_args.kwargs
            self.assertEqual(kwargs.get("trading_mandate"), mandate)

    def test_propagate_defaults_mandate_to_empty(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            mock_graph, _ = self._mock_graph(Path(td))
            TradingAgentsGraph.propagate(mock_graph, "NVDA", "2026-07-10")
            kwargs = mock_graph.propagator.create_initial_state.call_args.kwargs
            self.assertEqual(kwargs.get("trading_mandate"), "")


class TestRunSignatureIncludesMandate(unittest.TestCase):
    def _bare_graph(self):
        g = object.__new__(TradingAgentsGraph)
        g.selected_analysts = ("market", "news")
        g.config = {"max_debate_rounds": 1, "max_risk_discuss_rounds": 1}
        return g

    def test_empty_mandate_leaves_signature_unchanged(self):
        g = self._bare_graph()
        base = g._run_signature("stock")
        self.assertEqual(base, g._run_signature("stock", trading_mandate=""))
        self.assertEqual(base, g._run_signature("stock", trading_mandate="   "))

    def test_different_mandate_changes_signature(self):
        g = self._bare_graph()
        base = g._run_signature("stock")
        with_a = g._run_signature("stock", trading_mandate="mandate A")
        with_b = g._run_signature("stock", trading_mandate="mandate B")
        self.assertNotEqual(base, with_a)
        self.assertNotEqual(with_a, with_b)

    def test_mandate_is_strip_normalized(self):
        g = self._bare_graph()
        a = g._run_signature("stock", trading_mandate="  same mandate  ")
        b = g._run_signature("stock", trading_mandate="same mandate")
        self.assertEqual(a, b)


class TestGetMandateFromState(unittest.TestCase):
    def test_empty_state_returns_empty_string(self):
        from tradingagents.agents.utils.agent_utils import get_mandate_from_state

        self.assertEqual(get_mandate_from_state({}), "")
        self.assertEqual(get_mandate_from_state({"trading_mandate": ""}), "")
        self.assertEqual(get_mandate_from_state({"trading_mandate": "   "}), "")

    def test_formatted_block_contains_mandate_and_constraint(self):
        from tradingagents.agents.utils.agent_utils import get_mandate_from_state

        mandate = "Spot long-only; no derivatives"
        block = get_mandate_from_state({"trading_mandate": mandate})
        self.assertIn(mandate, block)
        self.assertIn("User mandate (binding constraints for recommendations)", block)
        self.assertIn("constrains recommendations, not evidence", block)
        self.assertTrue(block.startswith("\n\n"))

    def test_create_msg_delete_placeholder_includes_mandate(self):
        from langchain_core.messages import AIMessage

        from tradingagents.agents.utils.agent_utils import create_msg_delete

        mandate = "Spot long-only; no derivatives"
        state = {
            "messages": [AIMessage(content="prior", id="m1")],
            "company_of_interest": "BTC-USD",
            "asset_type": "crypto",
            "instrument_context": "The instrument to analyze is `BTC-USD`.",
            "trade_date": "2026-07-10",
            "trading_mandate": mandate,
        }
        result = create_msg_delete()(state)
        placeholder = result["messages"][-1]
        self.assertIn(mandate, placeholder.content)
        self.assertIn("User mandate (binding constraints for recommendations)", placeholder.content)


class TestAnalystMandateInjection(unittest.TestCase):
    def test_market_analyst_prompt_includes_mandate(self):
        from unittest.mock import MagicMock

        from langchain_core.runnables import RunnableLambda

        from tradingagents.agents.analysts.market_analyst import create_market_analyst

        mandate = "Spot long-only; no derivatives"
        captured = {}

        def capture(messages):
            captured["messages"] = messages
            result = MagicMock()
            result.tool_calls = []
            result.content = "report"
            return result

        llm = MagicMock()
        llm.bind_tools.return_value = RunnableLambda(capture)
        node = create_market_analyst(llm)
        node(
            {
                "messages": [],
                "trade_date": "2026-07-10",
                "company_of_interest": "BTC-USD",
                "asset_type": "crypto",
                "instrument_context": "The instrument to analyze is `BTC-USD`.",
                "trading_mandate": mandate,
            }
        )
        system_text = captured["messages"].to_messages()[0].content
        self.assertIn(mandate, system_text)
        self.assertIn("User mandate (binding constraints for recommendations)", system_text)


class TestTraderAndResearcherMandate(unittest.TestCase):
    def test_trader_user_message_includes_mandate(self):
        from unittest.mock import MagicMock, patch

        from tradingagents.agents.trader.trader import create_trader

        mandate = "Spot long-only; no derivatives"
        captured = {}

        def fake_invoke(structured_llm, llm, messages, render_fn, label):
            captured["messages"] = messages
            return "Rating: Hold"

        llm = MagicMock()
        with patch(
            "tradingagents.agents.trader.trader.bind_structured",
            return_value=MagicMock(),
        ), patch(
            "tradingagents.agents.trader.trader.invoke_structured_or_freetext",
            side_effect=fake_invoke,
        ):
            node = create_trader(llm)
            node(
                {
                    "company_of_interest": "BTC-USD",
                    "instrument_context": "The instrument to analyze is `BTC-USD`.",
                    "investment_plan": "plan",
                    "trading_mandate": mandate,
                }
            )
        user_text = captured["messages"][1]["content"]
        self.assertIn(mandate, user_text)
        self.assertIn("User mandate (binding constraints for recommendations)", user_text)

    def test_bear_reframe_present_only_when_mandate_set(self):
        from unittest.mock import MagicMock

        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="bearish")
        node = create_bear_researcher(llm)
        base_state = {
            "investment_debate_state": {
                "history": "",
                "bear_history": "",
                "bull_history": "",
                "current_response": "",
                "count": 0,
            },
            "market_report": "",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "company_of_interest": "BTC-USD",
            "asset_type": "crypto",
            "instrument_context": "The instrument to analyze is `BTC-USD`.",
        }
        node({**base_state, "trading_mandate": ""})
        empty_prompt = llm.invoke.call_args.args[0]
        self.assertNotIn("argue against entry timing", empty_prompt)

        node({**base_state, "trading_mandate": "Spot long-only"})
        mandate_prompt = llm.invoke.call_args.args[0]
        self.assertIn("argue against entry timing", mandate_prompt)
        self.assertIn("Spot long-only", mandate_prompt)


class TestEmptyMandatePromptIdentity(unittest.TestCase):
    def test_trader_empty_mandate_matches_absent_mandate(self):
        from unittest.mock import MagicMock, patch

        from tradingagents.agents.trader.trader import create_trader

        captured = []

        def fake_invoke(structured_llm, llm, messages, render_fn, label):
            captured.append(messages[1]["content"])
            return "Rating: Hold"

        llm = MagicMock()
        with patch(
            "tradingagents.agents.trader.trader.bind_structured",
            return_value=MagicMock(),
        ), patch(
            "tradingagents.agents.trader.trader.invoke_structured_or_freetext",
            side_effect=fake_invoke,
        ):
            node = create_trader(llm)
            base = {
                "company_of_interest": "NVDA",
                "instrument_context": "The instrument to analyze is `NVDA`.",
                "investment_plan": "plan",
            }
            node(base)
            node({**base, "trading_mandate": ""})
        self.assertEqual(captured[0], captured[1])
        self.assertNotIn("User mandate", captured[0])


class TestMemoryLogMandate(unittest.TestCase):
    def test_store_and_parse_mandate_round_trip(self):
        import tempfile
        from pathlib import Path

        from tradingagents.agents.utils.memory import TradingMemoryLog

        with tempfile.TemporaryDirectory() as td:
            log = TradingMemoryLog({"memory_log_path": str(Path(td) / "mem.md")})
            mandate = "spot long-only entry evaluation"
            log.store_decision(
                "BTC-USD",
                "2026-07-10",
                "Rating: Sell\nStay out.",
                trading_mandate=mandate,
            )
            entries = log.load_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["trading_mandate"], mandate)
            raw = Path(td, "mem.md").read_text(encoding="utf-8")
            self.assertIn("MANDATE:\n", raw)
            self.assertLess(raw.index("MANDATE:"), raw.index("DECISION:"))

    def test_store_without_mandate_has_no_section(self):
        import tempfile
        from pathlib import Path

        from tradingagents.agents.utils.memory import TradingMemoryLog

        with tempfile.TemporaryDirectory() as td:
            log = TradingMemoryLog({"memory_log_path": str(Path(td) / "mem.md")})
            log.store_decision("NVDA", "2026-07-10", "Rating: Buy")
            entries = log.load_entries()
            self.assertEqual(entries[0].get("trading_mandate"), "")
            raw = Path(td, "mem.md").read_text(encoding="utf-8")
            self.assertNotIn("MANDATE:", raw)

    def test_past_context_renders_mandate_annotation(self):
        import tempfile
        from pathlib import Path

        from tradingagents.agents.utils.memory import TradingMemoryLog

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mem.md"
            # Resolved entry with mandate (not pending)
            path.write_text(
                "[2026-06-01 | BTC-USD | Sell | +1.0% | -2.0% | 5d]\n\n"
                "MANDATE:\nspot long-only entry evaluation\n\n"
                "DECISION:\nRating: Sell\nStay out.\n\n"
                "REFLECTION:\nMissed nothing; stay-out was correct.\n\n"
                "<!-- ENTRY_END -->\n\n",
                encoding="utf-8",
            )
            log = TradingMemoryLog({"memory_log_path": str(path)})
            ctx = log.get_past_context("BTC-USD")
            self.assertIn("[mandate: spot long-only entry evaluation]", ctx)

    def test_legacy_entry_without_mandate_renders_unchanged(self):
        import tempfile
        from pathlib import Path

        from tradingagents.agents.utils.memory import TradingMemoryLog

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mem.md"
            path.write_text(
                "[2026-06-01 | NVDA | Buy | +1.0% | +0.5% | 5d]\n\n"
                "DECISION:\nRating: Buy\nGo long.\n\n"
                "REFLECTION:\nThesis held.\n\n"
                "<!-- ENTRY_END -->\n\n",
                encoding="utf-8",
            )
            log = TradingMemoryLog({"memory_log_path": str(path)})
            entry = log.load_entries()[0]
            self.assertEqual(entry.get("trading_mandate"), "")
            formatted = log._format_full(entry)
            self.assertNotIn("[mandate:", formatted)
            self.assertIn("DECISION:\nRating: Buy", formatted)

    def test_reflection_prompt_includes_mandate(self):
        from unittest.mock import MagicMock

        from tradingagents.graph.reflection import Reflector

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="lesson")
        Reflector(llm).reflect_on_final_decision(
            final_decision="Rating: Sell",
            raw_return=0.1,
            alpha_return=0.05,
            trading_mandate="spot long-only entry evaluation",
        )
        human = llm.invoke.call_args.args[0][1][1]
        self.assertIn("spot long-only entry evaluation", human)
        self.assertIn("made under the following trading mandate", human)


if __name__ == "__main__":
    unittest.main()
