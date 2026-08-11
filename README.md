# trade-o-matic

A research-first quantitative trading platform.

The project is designed around a strict separation between research, portfolio/risk decisions, and execution. Strategies generate signals; they never talk directly to a broker. This allows the same research code to be used for historical backtests, paper trading, and eventually live trading through interchangeable broker adapters.

## Current milestone

The repository now has an end-to-end **daily research path**:

`CSV/Parquet bars -> Strategy -> delayed target portfolio -> simulated next-open fills -> Ledger -> cost-adjusted equity -> metrics`

A close-derived signal is structurally unable to execute until the following bar's open. Spread, slippage and commission are explicit assumptions rather than deductions made after the backtest.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
trade-o-matic doctor
```

## Market data format

CSV and Parquet inputs use one row per symbol/bar:

```text
symbol,timestamp,open,high,low,close,volume
SPY,2025-01-02T00:00:00Z,586.08,589.64,582.44,584.64,50204000
```

Duplicate symbol/timestamp observations and invalid OHLC bars are rejected. Local files make research runs reproducible; vendor adapters will be added separately.

## Run a backtest

```bash
trade-o-matic backtest \
  --data data/daily.csv \
  --symbols SPY,QQQ \
  --start 2010-01-01 \
  --end 2025-12-31 \
  --strategy tsmom \
  --lookback 252 \
  --capital 100000 \
  --half-spread-bps 1 \
  --slippage-bps 1 \
  --commission-bps 0
```

The report includes final equity, total return, CAGR, volatility, Sharpe, Sortino, maximum drawdown, fills, turnover and modeled trading costs.

## Architecture rules

- Strategies emit `Signal` objects and cannot execute orders.
- Market data is behind `MarketDataSource`.
- Paper/live execution will be behind `Broker`; backtests never import broker SDKs.
- Portfolio risk is applied outside strategies.
- Decisions based on bar T execute no earlier than bar T+1.
- Every research run must declare transaction-cost assumptions.
- Failed research is retained; future alpha experiments will be registered rather than selectively discarded.

## Initial goals

- reproducible quantitative research from the command line
- explicit transaction costs and execution assumptions
- deterministic accounting with an auditable ledger
- portfolio-level risk controls
- vendor-neutral market-data and broker interfaces
- paper/live execution without rewriting strategies
- equities first, with futures, crypto, and prediction markets later

## Next

1. Add downloadable/versioned equity data snapshots and corporate-action handling.
2. Add research-run persistence and an alpha registry.
3. Add cross-sectional portfolio construction and initial Alpha101 signals.
4. Add walk-forward/OOS/cost-stress validation.
5. Only after validation, add paper broker adapters and intraday strategies.
