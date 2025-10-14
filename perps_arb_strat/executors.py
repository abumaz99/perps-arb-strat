"""Trade execution backends for the arbitrage strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .config import TokenConfig


@dataclass
class SpreadPosition:
    """Represents an open long/short spread across two exchanges."""

    token: TokenConfig
    long_exchange: str
    short_exchange: str
    opened_at: datetime
    open_rate_diff_bps: float
    metadata: dict[str, object] = field(default_factory=dict)


class TradeExecutor(Protocol):
    """Defines the interface for carrying out spread trades."""

    def open_spread(
        self,
        position: SpreadPosition,
        hyperliquid_rate: float,
        bybit_rate: float,
    ) -> None:
        """Open a new spread between two exchanges."""

    def close_spread(self, position: SpreadPosition, reason: str) -> None:
        """Close an existing spread."""


class LoggingExecutor:
    """A :class:`TradeExecutor` that only logs the requested operations."""

    def __init__(self, *, logger=None) -> None:
        import logging

        self.logger = logger or logging.getLogger(__name__)

    def open_spread(
        self,
        position: SpreadPosition,
        hyperliquid_rate: float,
        bybit_rate: float,
    ) -> None:
        self.logger.info(
            "Opening spread on %s: long %s / short %s | diff %.2f bps (HL %.6f, Bybit %.6f)",
            position.token.canonical_symbol,
            position.long_exchange,
            position.short_exchange,
            position.open_rate_diff_bps,
            hyperliquid_rate,
            bybit_rate,
        )

    def close_spread(self, position: SpreadPosition, reason: str) -> None:
        self.logger.info(
            "Closing spread on %s: long %s / short %s | reason: %s",
            position.token.canonical_symbol,
            position.long_exchange,
            position.short_exchange,
            reason,
        )
