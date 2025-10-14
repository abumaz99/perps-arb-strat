"""Core funding rate arbitrage strategy implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Iterable, List, Optional

from .config import StrategyConfig, TokenConfig
from .executors import SpreadPosition, TradeExecutor
from .exchanges import FundingRate

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    OPEN = "open"
    CLOSE = "close"


@dataclass
class Action:
    """Represents a trading action recommended by the strategy."""

    type: ActionType
    position: SpreadPosition
    reason: str
    hyperliquid_rate: float
    bybit_rate: float
    rate_diff_bps: float


class FundingArbStrategy:
    """Compares Hyperliquid and Bybit funding rates and opens spread trades."""

    def __init__(
        self,
        *,
        config: StrategyConfig,
        hyperliquid_rates: "HyperliquidClientProtocol",
        bybit_rates: "BybitClientProtocol",
        executor: TradeExecutor,
    ) -> None:
        self.config = config
        self.hyperliquid_rates = hyperliquid_rates
        self.bybit_rates = bybit_rates
        self.executor = executor
        self.positions: Dict[str, SpreadPosition] = {}

    def evaluate_once(self) -> List[Action]:
        """Fetch latest funding rates and determine trading actions."""

        hyper_rates = self.hyperliquid_rates.fetch_funding_rates(self.config.tokens)
        bybit_rates = self.bybit_rates.fetch_funding_rates(self.config.tokens)

        actions: List[Action] = []
        for token in self.config.tokens:
            hyper_rate = hyper_rates.get(token.hyperliquid_symbol.upper())
            bybit_rate = bybit_rates.get(token.bybit_symbol)
            if hyper_rate is None or bybit_rate is None:
                logger.debug("Missing data for token %s", token.canonical_symbol)
                continue

            rate_diff = hyper_rate.rate - bybit_rate.rate
            rate_diff_bps = rate_diff * 10_000
            logger.debug(
                "Token %s | Hyperliquid %.6f | Bybit %.6f | diff %.2f bps",
                token.canonical_symbol,
                hyper_rate.rate,
                bybit_rate.rate,
                rate_diff_bps,
            )

            position = self.positions.get(token.canonical_symbol)
            if position is None:
                maybe_action = self._maybe_open_position(
                    token=token,
                    hyper_rate=hyper_rate,
                    bybit_rate=bybit_rate,
                    rate_diff=rate_diff,
                    rate_diff_bps=rate_diff_bps,
                )
                if maybe_action:
                    actions.append(maybe_action)
            else:
                maybe_action = self._maybe_close_position(
                    token=token,
                    position=position,
                    hyper_rate=hyper_rate,
                    bybit_rate=bybit_rate,
                    rate_diff=rate_diff,
                    rate_diff_bps=rate_diff_bps,
                )
                if maybe_action:
                    actions.append(maybe_action)
        return actions

    def _maybe_open_position(
        self,
        *,
        token: TokenConfig,
        hyper_rate: FundingRate,
        bybit_rate: FundingRate,
        rate_diff: float,
        rate_diff_bps: float,
    ) -> Optional[Action]:
        if self.config.max_positions is not None and len(self.positions) >= self.config.max_positions:
            logger.debug("Max positions reached; skipping new entries")
            return None

        if abs(rate_diff_bps) < self.config.entry_threshold_bps:
            return None

        long_exchange, short_exchange = self._determine_spread_sides(rate_diff)
        position = SpreadPosition(
            token=token,
            long_exchange=long_exchange,
            short_exchange=short_exchange,
            opened_at=datetime.now(tz=timezone.utc),
            open_rate_diff_bps=rate_diff_bps,
            metadata={
                "hyperliquid_rate": hyper_rate.rate,
                "bybit_rate": bybit_rate.rate,
            },
        )
        self.positions[token.canonical_symbol] = position

        action = Action(
            type=ActionType.OPEN,
            position=position,
            reason=f"Funding diff {rate_diff_bps:.2f} bps crossed entry threshold",
            hyperliquid_rate=hyper_rate.rate,
            bybit_rate=bybit_rate.rate,
            rate_diff_bps=rate_diff_bps,
        )
        self.executor.open_spread(position, hyper_rate.rate, bybit_rate.rate)
        return action

    def _maybe_close_position(
        self,
        *,
        token: TokenConfig,
        position: SpreadPosition,
        hyper_rate: FundingRate,
        bybit_rate: FundingRate,
        rate_diff: float,
        rate_diff_bps: float,
    ) -> Optional[Action]:
        should_close = False
        reason = ""
        if rate_diff_bps == 0 or (rate_diff_bps > 0) != (position.open_rate_diff_bps > 0):
            should_close = True
            reason = "Funding differential flipped sign"
        elif abs(rate_diff_bps) <= self.config.exit_threshold_bps:
            should_close = True
            reason = "Funding differential reverted below exit threshold"
        elif position.opened_at + timedelta(hours=12) < datetime.now(tz=timezone.utc):
            should_close = True
            reason = "Position aged beyond 12 hours"

        if not should_close:
            return None

        del self.positions[token.canonical_symbol]
        action = Action(
            type=ActionType.CLOSE,
            position=position,
            reason=reason,
            hyperliquid_rate=hyper_rate.rate,
            bybit_rate=bybit_rate.rate,
            rate_diff_bps=rate_diff_bps,
        )
        self.executor.close_spread(position, reason)
        return action

    @staticmethod
    def _determine_spread_sides(rate_diff: float) -> tuple[str, str]:
        if rate_diff > 0:
            # Hyperliquid funding > Bybit funding -> short Hyperliquid, long Bybit
            return ("Bybit", "Hyperliquid")
        return ("Hyperliquid", "Bybit")

    def run_forever(self) -> None:
        """Continuously evaluate the strategy at the configured interval."""

        delay = self.config.poll_interval.total_seconds()
        if delay <= 0:
            raise ValueError("Poll interval must be positive")
        while True:  # pragma: no cover - infinite loop excluded from tests
            try:
                actions = self.evaluate_once()
                for action in actions:
                    logger.info("Action %s for %s: %s", action.type, action.position.token.canonical_symbol, action.reason)
            except Exception:  # pragma: no cover - log unexpected failures
                logger.exception("Unexpected error during evaluation")
            finally:
                from time import sleep

                sleep(delay)


class HyperliquidClientProtocol:
    def fetch_funding_rates(self, tokens: Iterable[TokenConfig]) -> Dict[str, FundingRate]:
        ...


class BybitClientProtocol:
    def fetch_funding_rates(self, tokens: Iterable[TokenConfig]) -> Dict[str, FundingRate]:
        ...
