"""Configuration dataclasses for the funding rate arbitrage strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class TokenConfig:
    """Represents a perpetual contract that trades on both exchanges."""

    name: str
    bybit_symbol: str
    hyperliquid_symbol: str
    quote: str = "USDC"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Token name must be provided")
        if not self.bybit_symbol:
            raise ValueError("Bybit symbol must be provided")
        if not self.hyperliquid_symbol:
            raise ValueError("Hyperliquid symbol must be provided")

    @property
    def canonical_symbol(self) -> str:
        """Returns a shared name for logging and position bookkeeping."""

        return f"{self.name}-{self.quote}"


@dataclass
class StrategyConfig:
    """Holds runtime configuration for :class:`FundingArbStrategy`."""

    tokens: Sequence[TokenConfig]
    entry_threshold_bps: float = 10.0
    exit_threshold_bps: float = 3.0
    poll_interval: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    max_positions: int | None = None

    def __post_init__(self) -> None:
        if self.entry_threshold_bps <= 0:
            raise ValueError("Entry threshold must be positive")
        if self.exit_threshold_bps < 0:
            raise ValueError("Exit threshold cannot be negative")
        if self.exit_threshold_bps > self.entry_threshold_bps:
            raise ValueError("Exit threshold should be less than or equal to entry threshold")
        if not isinstance(self.tokens, Iterable) or not self.tokens:
            raise ValueError("At least one token configuration must be supplied")
        for token in self.tokens:
            if not isinstance(token, TokenConfig):
                raise TypeError("tokens must be a sequence of TokenConfig instances")

    def as_list(self) -> List[TokenConfig]:
        """Return the configured tokens as a mutable list."""

        return list(self.tokens)
