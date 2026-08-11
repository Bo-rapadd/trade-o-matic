from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path

from . import __version__
from .data_local import LocalBarDataSource
from .registry import STRATEGIES, create_strategy
from .research import ResearchResult, run_daily_strategy
from .risk import CostModel, RiskLimits
from .validation import validate_strategy


def _date(value: str, *, end: bool = False) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.combine(parsed, time.max if end else time.min, tzinfo=timezone.utc)


def _params(values: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"strategy parameter must be KEY=VALUE: {value}")
        key, raw = value.split("=", 1)
        try:
            parsed[key] = int(raw)
        except ValueError:
            try:
                parsed[key] = float(raw)
            except ValueError:
                parsed[key] = raw
    return parsed


def _result_dict(result: ResearchResult) -> dict[str, object]:
    p = result.performance
    return {
        "strategy": result.strategy,
        "start": result.start.isoformat(),
        "end": result.end.isoformat(),
        "final_equity": result.equity[-1],
        "total_return": p.total_return,
        "cagr": p.annualized_return,
        "volatility": p.annualized_volatility,
        "sharpe": p.sharpe,
        "sortino": p.sortino,
        "max_drawdown": p.max_drawdown,
        "fills": result.fills,
        "turnover": result.turnover,
        "trading_costs": result.trading_costs,
    }


def _print_result(result: ResearchResult, capital: float) -> None:
    p = result.performance
    print(f"Strategy:          {result.strategy}")
    print(f"Period:            {result.start.date()} -> {result.end.date()}")
    print(f"Initial capital:   ${capital:,.2f}")
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


def _add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--data", required=True, type=Path, help="CSV or Parquet OHLCV file")
    command.add_argument("--symbols", required=True, help="comma-separated symbols")
    command.add_argument("--start", required=True, help="YYYY-MM-DD")
    command.add_argument("--end", required=True, help="YYYY-MM-DD")
    command.add_argument("--strategy", choices=sorted(STRATEGIES), required=True)
    command.add_argument("--param", action="append", default=[], help="strategy KEY=VALUE; repeatable")
    command.add_argument("--capital", type=float, default=100_000.0)
    command.add_argument("--commission-bps", type=float, default=0.0)
    command.add_argument("--half-spread-bps", type=float, default=1.0)
    command.add_argument("--slippage-bps", type=float, default=1.0)
    command.add_argument("--max-position", type=float, default=0.10)
    command.add_argument("--max-gross", type=float, default=1.0)
    command.add_argument("--max-turnover", type=float, default=2.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trade-o-matic", description="Quantitative strategy test bench")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="verify the local research environment")
    sub.add_parser("strategies", help="list built-in strategies and parameters")
    backtest = sub.add_parser("backtest", help="run one strategy")
    _add_common(backtest)
    backtest.add_argument("--json", type=Path, help="write machine-readable result")
    validate = sub.add_parser("validate", help="chronological IS/OOS + cost-stress test")
    _add_common(validate)
    validate.add_argument("--train-fraction", type=float, default=0.70)
    validate.add_argument("--cost-stress", type=float, default=3.0)
    return parser


def _load(args):
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    source = LocalBarDataSource(args.data)
    bars = source.bars(symbols, _date(args.start), _date(args.end, end=True), "1d")
    strategy = create_strategy(args.strategy, **_params(args.param))
    costs = CostModel(args.commission_bps, args.half_spread_bps, args.slippage_bps)
    risk = RiskLimits(args.max_gross, args.max_position, args.max_turnover)
    return bars, strategy, costs, risk


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "doctor":
        print("trade-o-matic: OK\nresearch test bench: available\nlive execution: disabled")
        return 0
    if args.command == "strategies":
        for spec in STRATEGIES.values():
            print(f"{spec.name:16} {spec.description:38} params={','.join(spec.parameters)}")
        return 0
    if args.command in {"backtest", "validate"}:
        try:
            bars, strategy, costs, risk = _load(args)
            if args.command == "backtest":
                result = run_daily_strategy(bars, strategy, initial_capital=args.capital, costs=costs, risk=risk)
                _print_result(result, args.capital)
                if args.json:
                    args.json.parent.mkdir(parents=True, exist_ok=True)
                    args.json.write_text(json.dumps(_result_dict(result), indent=2) + "\n")
                return 0
            report = validate_strategy(
                bars, strategy, train_fraction=args.train_fraction, initial_capital=args.capital,
                costs=costs, risk=risk, cost_stress_multiple=args.cost_stress,
            )
            print(f"Strategy: {report.strategy}  split={report.split_timestamp.date()}")
            for label, result in [
                ("IN-SAMPLE", report.in_sample), ("OUT-OF-SAMPLE", report.out_of_sample),
                (f"OOS COST x{args.cost_stress:g}", report.stressed_out_of_sample),
            ]:
                p = result.performance
                print(f"{label:16} return={p.total_return:>8.2%} sharpe={p.sharpe:>6.2f} drawdown={p.max_drawdown:>8.2%} costs=${result.trading_costs:,.2f}")
            print(f"Basic robustness: {'PASS' if report.passed_basic_robustness else 'FAIL'}")
            return 0
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
