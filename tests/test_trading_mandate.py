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


if __name__ == "__main__":
    unittest.main()
