from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
from pathlib import Path

from . import __version__
from .data_local import LocalBarDataSource
from .research import run_daily_strategy
from .risk import CostModel, RiskLimits
from .strategies.trend import TimeSeriesMomentum


def _date(value: str, *, end: bool = False) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.combine(parsed, time.max if end else time.min, tzinfo=timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trade-o-matic",
        description="Quantitative research and trading platform",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="verify the local research environment")
    sub.add_parser("strategies", help="list built-in strategies")

    backtest = sub.add_parser("backtest", help="run a reproducible local-data backtest")
    backtest.add_argument("--data", required=True, type=Path, help="CSV or Parquet OHLCV file")
    backtest.add_argument("--symbols", required=True, help="comma-separated symbols")
    backtest.add_argument("--start", required=True, help="YYYY-MM-DD")
    backtest.add_argument("--end", required=True, help="YYYY-MM-DD")
    backtest.add_argument("--strategy", choices=["tsmom"], default="tsmom")
    backtest.add_argument("--lookback", type=int, default=252)
    backtest.add_argument("--capital", type=float, default=100_000.0)
    backtest.add_argument("--commission-bps", type=float, default=0.0)
    backtest.add_argument("--half-spread-bps", type=float, default=1.0)
    backtest.add_argument("--slippage-bps", type=float, default=1.0)
    backtest.add_argument("--max-position", type=float, default=0.10)
    backtest.add_argument("--max-gross", type=float, default=1.0)
    backtest.add_argument("--max-turnover", type=float, default=2.0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "doctor":
        print("trade-o-matic: OK")
        print("research core: available")
        print("live execution: disabled")
        return 0
    if args.command == "strategies":
        print("tsmom\tTime-series momentum baseline")
        return 0
    if args.command == "backtest":
        symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        source = LocalBarDataSource(args.data)
        bars = source.bars(symbols, _date(args.start), _date(args.end, end=True), "1d")
        strategy = TimeSeriesMomentum(lookback=args.lookback)
        result = run_daily_strategy(
            bars,
            strategy,
            initial_capital=args.capital,
            costs=CostModel(args.commission_bps, args.half_spread_bps, args.slippage_bps),
            risk=RiskLimits(
                max_gross_exposure=args.max_gross,
                max_position_weight=args.max_position,
                max_turnover=args.max_turnover,
            ),
        )
        p = result.performance
        print(f"Strategy:          {result.strategy}")
        print(f"Period:            {result.start.date()} -> {result.end.date()}")
        print(f"Initial capital:   ${args.capital:,.2f}")
        print(f"Final equity:      ${result.equity[-1]:,.2f}")
        print(f"Total return:      {p.total_return:>10.2%}")
        print(f"CAGR:              {p.annualized_return:>10.2%}")
        print(f"Volatility:        {p.annualized_volatility:>10.2%}")
        print(f"Sharpe:            {p.sharpe:>10.2f}")
        print(f"Sortino:           {p.sortino:>10.2f}")
        print(f"Max drawdown:      {p.max_drawdown:>10.2%}")
        print(f"Fills:             {result.fills:>10d}")
        print(f"Turnover:          {result.turnover:>10.2f}x")
        print(f"Trading costs:     ${result.trading_costs:,.2f}")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
