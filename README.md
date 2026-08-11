# trade-o-matic

A research-first quantitative trading platform with a command-line strategy test bench.

## What is runnable now

The daily research path is:

`CSV/Parquet -> Strategy -> Signal -> target weights -> risk -> NEXT-BAR OPEN fills -> Ledger -> cost-adjusted equity -> metrics`

A close-derived signal cannot execute until the following bar's open. Spread, slippage and commission are explicit. The same strategy API is intended to feed paper/live execution later through broker adapters.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
trade-o-matic doctor
trade-o-matic strategies
```

## Data

CSV/Parquet columns:

```text
symbol,timestamp,open,high,low,close,volume
SPY,2025-01-02T00:00:00Z,586.08,589.64,582.44,584.64,50204000
```

Use adjusted/clean research data consistently. Duplicate symbol/timestamp observations and invalid OHLC bars are rejected. Corporate-action/survivorship-safe vendor ingestion is a separate upcoming milestone.

## Built-in test strategies

- `tsmom` — time-series momentum
- `ma_cross` — moving-average crossover
- `mean_reversion` — rolling price z-score mean reversion
- `donchian` — Donchian breakout

These are baseline/test strategies, not claims of profitable edges.

## Backtest any registered strategy

```bash
trade-o-matic backtest \
  --data data/daily.csv --symbols SPY,QQQ \
  --start 2010-01-01 --end 2025-12-31 \
  --strategy ma_cross --param fast=50 --param slow=200 \
  --capital 100000 --half-spread-bps 1 --slippage-bps 1 \
  --json results/ma_cross.json
```

Parameters are strategy-specific and repeatable with `--param KEY=VALUE`. `trade-o-matic strategies` lists accepted parameters.

## Basic out-of-sample validation

```bash
trade-o-matic validate \
  --data data/daily.csv --symbols SPY,QQQ \
  --start 2010-01-01 --end 2025-12-31 \
  --strategy tsmom --param lookback=252 \
  --train-fraction 0.70 --cost-stress 3
```

This runs a chronological 70/30 split and repeats the untouched OOS segment with transaction costs multiplied by three. `PASS` is deliberately only a basic screening flag; it is not evidence that a strategy is production-ready.

## Adding a strategy

Implement `Strategy.generate(history, as_of) -> list[Signal]`, put it under `src/trade_o_matic/strategies/`, and register its factory and accepted parameters in `registry.py`. Strategies cannot place orders or import broker SDKs.

## Architecture rules

- strategies emit signals only;
- market data is behind `MarketDataSource`;
- broker execution is behind `Broker` and is absent from backtests;
- risk is portfolio-level and outside strategies;
- bar T information executes no earlier than T+1;
- transaction-cost assumptions are mandatory and visible;
- tests explicitly check future bars cannot alter an as-of signal.

## Known limitations before live/paper trading

The current runner is a daily research simulator. It does not yet model partial fills, limit-order queues, halts, borrow availability/fees, dividends, taxes, exchange fees, corporate actions, delistings, survivorship-safe universes, or intraday microstructure. Those limitations must not be ignored when interpreting results.

## Next research milestones

1. versioned/survivorship-safe equity datasets and corporate actions;
2. persistent experiment registry and result comparison;
3. walk-forward and parameter-stability validation;
4. cross-sectional portfolio construction + Alpha101 subset;
5. paper broker adapter and daily trade proposal/email workflow;
6. separate event-driven intraday simulator for ORB/SPY-intraday strategies.
