"""Entry point for running the funding rate arbitrage strategy."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import timedelta
from typing import Iterable, Sequence

from .config import StrategyConfig, TokenConfig
from .executors import LoggingExecutor
from .exchanges import BybitClient, HyperliquidClient
from .strategy import FundingArbStrategy


def parse_tokens(value: str) -> Sequence[TokenConfig]:
    tokens: list[TokenConfig] = []
    for part in value.split(","):
        if not part:
            continue
        components = part.split(":")
        if len(components) == 3:
            name, bybit_symbol, hyper_symbol = components
        elif len(components) == 2:
            name, bybit_symbol = components
            hyper_symbol = name
        else:
            name = part
            bybit_symbol = f"{name}USDT"
            hyper_symbol = name
        tokens.append(TokenConfig(name=name.upper(), bybit_symbol=bybit_symbol.upper(), hyperliquid_symbol=hyper_symbol.upper()))
    if not tokens:
        raise argparse.ArgumentTypeError("At least one token must be provided")
    return tokens


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tokens",
        type=parse_tokens,
        default=parse_tokens(os.environ.get("TOKENS", "BTC:BTCUSDT:BTC,ETH:ETHUSDT:ETH")),
        help="Comma separated tokens in NAME:BYBIT:HL format. Defaults to TOKENS env or BTC/ETH.",
    )
    parser.add_argument(
        "--entry-bps",
        type=float,
        default=float(os.environ.get("ENTRY_THRESHOLD_BPS", 12)),
        help="Entry threshold in basis points.",
    )
    parser.add_argument(
        "--exit-bps",
        type=float,
        default=float(os.environ.get("EXIT_THRESHOLD_BPS", 4)),
        help="Exit threshold in basis points.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.environ.get("POLL_INTERVAL", 60)),
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--config-json",
        type=str,
        default=os.environ.get("STRATEGY_CONFIG_JSON"),
        help="Optional JSON blob to override configuration (tokens, entry/exit thresholds).",
    )
    return parser


def load_config(args: argparse.Namespace) -> StrategyConfig:
    if args.config_json:
        override = json.loads(args.config_json)
        tokens = [
            TokenConfig(
                name=item["name"],
                bybit_symbol=item.get("bybit_symbol", f"{item['name']}USDT"),
                hyperliquid_symbol=item.get("hyperliquid_symbol", item["name"]),
                quote=item.get("quote", "USDC"),
            )
            for item in override.get("tokens", [])
        ]
        entry_bps = override.get("entry_threshold_bps", args.entry_bps)
        exit_bps = override.get("exit_threshold_bps", args.exit_bps)
        interval_seconds = override.get("poll_interval", args.poll_interval)
    else:
        tokens = args.tokens
        entry_bps = args.entry_bps
        exit_bps = args.exit_bps
        interval_seconds = args.poll_interval

    config = StrategyConfig(
        tokens=tokens,
        entry_threshold_bps=entry_bps,
        exit_threshold_bps=exit_bps,
        poll_interval=timedelta(seconds=interval_seconds),
        max_positions=None,
    )
    return config


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config(args)
    strategy = FundingArbStrategy(
        config=config,
        hyperliquid_rates=HyperliquidClient(),
        bybit_rates=BybitClient(),
        executor=LoggingExecutor(),
    )
    strategy.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
