from __future__ import annotations

import unittest
from datetime import datetime, timezone

from perps_arb_strat.config import StrategyConfig, TokenConfig
from perps_arb_strat.executors import LoggingExecutor, SpreadPosition
from perps_arb_strat.strategy import ActionType, FundingArbStrategy


class FakeFundingRate:
    def __init__(self, rate: float) -> None:
        self.rate = rate
        self.timestamp = datetime.now(tz=timezone.utc)


class FakeExchange:
    def __init__(self, mapping: dict[str, float]) -> None:
        self.mapping = mapping

    def fetch_funding_rates(self, tokens):
        result = {}
        for token in tokens:
            if token.hyperliquid_symbol in self.mapping:
                result[token.hyperliquid_symbol] = FakeFundingRate(self.mapping[token.hyperliquid_symbol])
            if getattr(token, "bybit_symbol", None) in self.mapping:
                result[token.bybit_symbol] = FakeFundingRate(self.mapping[token.bybit_symbol])
        return result


class RecordingExecutor(LoggingExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.opened: list[SpreadPosition] = []
        self.closed: list[SpreadPosition] = []
        self.reasons: list[str] = []

    def open_spread(self, position: SpreadPosition, hyperliquid_rate: float, bybit_rate: float) -> None:
        self.opened.append(position)

    def close_spread(self, position: SpreadPosition, reason: str) -> None:
        self.closed.append(position)
        self.reasons.append(reason)


class FundingArbStrategyTest(unittest.TestCase):
    def setUp(self) -> None:
        token = TokenConfig(name="BTC", bybit_symbol="BTCUSDT", hyperliquid_symbol="BTC")
        config = StrategyConfig(tokens=[token], entry_threshold_bps=10.0, exit_threshold_bps=5.0)
        self.executor = RecordingExecutor()
        self.strategy = FundingArbStrategy(
            config=config,
            hyperliquid_rates=FakeExchange({"BTC": 0.0015}),
            bybit_rates=FakeExchange({"BTCUSDT": 0.0001}),
            executor=self.executor,
        )

    def test_open_position_when_threshold_exceeded(self) -> None:
        actions = self.strategy.evaluate_once()
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.type, ActionType.OPEN)
        self.assertEqual(action.position.long_exchange, "Bybit")
        self.assertEqual(action.position.short_exchange, "Hyperliquid")
        self.assertAlmostEqual(action.rate_diff_bps, (0.0015 - 0.0001) * 10000)
        self.assertEqual(len(self.executor.opened), 1)

    def test_close_position_when_diff_reverts(self) -> None:
        self.strategy.evaluate_once()
        # Update exchanges to reduce differential
        self.strategy.hyperliquid_rates = FakeExchange({"BTC": 0.0002})
        self.strategy.bybit_rates = FakeExchange({"BTCUSDT": 0.00015})
        actions = self.strategy.evaluate_once()
        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.type, ActionType.CLOSE)
        self.assertIn("exit threshold", action.reason)
        self.assertEqual(len(self.executor.closed), 1)


if __name__ == "__main__":
    unittest.main()
