"""Core package for the perpetual funding rate arbitrage strategy."""

from .config import TokenConfig, StrategyConfig
from .exchanges import BybitClient, HyperliquidClient
from .strategy import FundingArbStrategy, Action, ActionType
from .executors import LoggingExecutor, TradeExecutor, SpreadPosition

__all__ = [
    "TokenConfig",
    "StrategyConfig",
    "BybitClient",
    "HyperliquidClient",
    "FundingArbStrategy",
    "Action",
    "ActionType",
    "LoggingExecutor",
    "TradeExecutor",
    "SpreadPosition",
]
