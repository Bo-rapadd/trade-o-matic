# trade-o-matic

A research-first quantitative trading platform.

The project is designed around a strict separation between research, portfolio/risk decisions, and execution. Strategies generate signals; they never talk directly to a broker. This allows the same research code to be used for historical backtests, paper trading, and eventually live trading through interchangeable broker adapters.

## Initial goals

- reproducible quantitative research from the command line
- explicit transaction costs and execution assumptions
- no-look-ahead strategy interfaces
- deterministic backtesting and accounting
- portfolio-level risk controls
- vendor-neutral market-data and broker interfaces
- paper/live execution without rewriting strategies
- support for equities first, with futures, crypto, and prediction markets later

## Status

Milestone 1: quantitative research core and backtester.
