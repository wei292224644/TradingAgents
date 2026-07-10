"""Tests for optional trading_mandate threading and prompt injection."""

import unittest

from tradingagents.graph.propagation import Propagator


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


if __name__ == "__main__":
    unittest.main()
