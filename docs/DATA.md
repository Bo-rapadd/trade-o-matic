# Market data policy

Trade-o-matic freezes provider responses into local Parquet/CSV snapshots. Every snapshot gets a sidecar manifest with source, symbols, interval, fetch time, adjustment flag and SHA-256 digest. Backtests consume the frozen snapshot, never a live provider response.

## Tier 0: Yahoo bootstrap

Use Yahoo/yfinance for immediate prototyping and sanity checks. It is convenient, supports daily and recent intraday intervals, and can auto-adjust OHLC for splits/dividends. It is **not** the canonical source for production-quality historical research and must not be used to make claims about survivorship-safe universes.

Example:

```bash
trade-o-matic fetch --source yahoo --symbols SPY,QQQ,AAPL,MSFT \
  --start 2015-01-01 --end 2026-08-12 --timeframe 1d --output data/us_etf_daily.parquet
```

Recent intraday bootstrap:

```bash
trade-o-matic fetch --source yahoo --symbols SPY,QQQ \
  --start 2026-07-01 --end 2026-08-12 --timeframe 5m --output data/spy_qqq_5m.parquet
```

Yahoo intraday history is provider-limited; request only ranges the provider supports.

## Tier 1: Databento research source

Databento is the preferred paid/research-grade path for short-horizon work. The adapter supports provider-native OHLCV at 1 second, 1 minute, 1 hour and 1 day. Other bars should be resampled from the finest appropriate frozen snapshot so the transformation is reproducible.

Set the key only in the environment:

```bash
export DATABENTO_API_KEY='...'
pip install -e '.[databento]'
```

Then, for example:

```bash
trade-o-matic fetch --source databento --dataset XNAS.ITCH \
  --symbols AAPL,MSFT,NVDA --start 2025-01-01 --end 2026-01-01 \
  --timeframe 1m --output data/nasdaq_1m_2025.parquet
```

Dataset choice is intentionally explicit. Do not silently mix feeds/exchanges.

## Research-quality rules

1. Keep raw/frozen snapshots immutable.
2. Commit manifests, not large market-data files, to Git.
3. Record provider and adjustment policy with every experiment.
4. Do not backtest historical stock selection using today's index constituents and call it survivorship-safe.
5. For single-instrument strategies (SPY intraday, futures, liquid crypto), survivorship bias is less central, but symbol mapping/rolls/corporate actions still matter.
6. For cross-sectional equity alpha research, acquire point-in-time security master/universe membership before treating results as serious.
7. Intraday tests must use realistic spread/slippage assumptions; later versions will add quote-derived costs and session calendars.

## Current limitation

The execution engine can consume intraday bars and preserves next-bar execution, but annualized metrics and the validation command are still calibrated for daily observations. Intraday performance annualization/session-aware validation is the next engine milestone.
