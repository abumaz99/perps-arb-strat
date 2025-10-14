# Perpetual Funding Rate Arbitrage Strategy

This repository contains a reference implementation of a funding rate arbitrage
strategy that compares perpetual swaps listed on Hyperliquid and Bybit. The
strategy continuously monitors the funding rate differential between the two
exchanges and opens or closes market-neutral spreads when the difference crosses
configurable thresholds.

## Project layout

```
perps_arb_strat/
  config.py        # Dataclasses for configuring the strategy
  exchanges.py     # Lightweight REST clients for Hyperliquid and Bybit
  executors.py     # Trade execution interfaces (logging backend by default)
  strategy.py      # Core signal generation logic
  main.py          # CLI entry point to run the strategy loop
```

Unit tests that exercise the signal generation logic live under `tests/`.

## Running the strategy

1. Install Python 3.11+.
2. Install any optional dependencies you might need (no third-party packages
   are required by default).
3. Execute the strategy:

   ```bash
   python -m perps_arb_strat.main --tokens BTC:BTCUSDT:BTC,ETH:ETHUSDT:ETH \
       --entry-bps 12 --exit-bps 4 --poll-interval 60
   ```

   The command above will run in a continuous loop, logging any spread trades
   that the signal engine wants to execute. The `TOKENS`,
   `ENTRY_THRESHOLD_BPS`, `EXIT_THRESHOLD_BPS`, and `POLL_INTERVAL`
   environment variables can also be used instead of CLI flags.

The REST clients rely on the public funding rate endpoints exposed by both
exchanges. Network requests are wrapped in basic error handling to keep the loop
alive in case of transient connectivity issues. When integrating with actual
trading infrastructure you can provide your own `TradeExecutor` implementation
that places orders, updates hedge positions, and manages risk.

## Running the tests

Execute the unit tests with:

```bash
python -m unittest
```

The tests mock out exchange connectivity and verify the logic that decides when
spread trades should be opened or closed.
