from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path

from . import __version__
from .data_local import LocalBarDataSource
from .fetch import fetch_databento, fetch_yahoo
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
        try: parsed[key] = int(raw)
        except ValueError:
            try: parsed[key] = float(raw)
            except ValueError: parsed[key] = raw
    return parsed


def _result_dict(result: ResearchResult) -> dict[str, object]:
    p = result.performance
    return {"strategy": result.strategy, "start": result.start.isoformat(), "end": result.end.isoformat(),
            "final_equity": result.equity[-1], "total_return": p.total_return,
            "cagr": p.annualized_return, "volatility": p.annualized_volatility,
            "sharpe": p.sharpe, "sortino": p.sortino, "max_drawdown": p.max_drawdown,
            "fills": result.fills, "turnover": result.turnover, "trading_costs": result.trading_costs}


def _print_result(result: ResearchResult, capital: float) -> None:
    p = result.performance
    print(f"Strategy:          {result.strategy}\nPeriod:            {result.start} -> {result.end}")
    print(f"Initial capital:   ${capital:,.2f}\nFinal equity:      ${result.equity[-1]:,.2f}")
    print(f"Total return:      {p.total_return:>10.2%}\nCAGR*:             {p.annualized_return:>10.2%}")
    print(f"Volatility*:       {p.annualized_volatility:>10.2%}\nSharpe*:           {p.sharpe:>10.2f}")
    print(f"Sortino*:          {p.sortino:>10.2f}\nMax drawdown:      {p.max_drawdown:>10.2%}")
    print(f"Fills:             {result.fills:>10d}\nTurnover:          {result.turnover:>10.2f}x")
    print(f"Trading costs:     ${result.trading_costs:,.2f}")
    print("* Annualization currently assumes 252 observations/year; use daily bars for comparable annualized metrics.")


def _add_common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--data", required=True, type=Path)
    command.add_argument("--symbols", required=True)
    command.add_argument("--start", required=True)
    command.add_argument("--end", required=True)
    command.add_argument("--timeframe", default="1d", choices=["1s","1m","2m","5m","15m","30m","60m","1h","1d"])
    command.add_argument("--strategy", choices=sorted(STRATEGIES), required=True)
    command.add_argument("--param", action="append", default=[])
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
    sub.add_parser("doctor")
    sub.add_parser("strategies")
    fetch = sub.add_parser("fetch", help="download and freeze a local market-data snapshot")
    fetch.add_argument("--source", choices=["yahoo", "databento"], default="yahoo")
    fetch.add_argument("--symbols", required=True)
    fetch.add_argument("--start", required=True)
    fetch.add_argument("--end", required=True)
    fetch.add_argument("--timeframe", default="1d")
    fetch.add_argument("--output", required=True, type=Path)
    fetch.add_argument("--dataset", help="Databento dataset, e.g. XNAS.ITCH or DBEQ.BASIC")
    fetch.add_argument("--unadjusted", action="store_true", help="Yahoo: do not auto-adjust OHLC")
    fetch.add_argument("--prepost", action="store_true", help="Yahoo: include extended hours")
    backtest = sub.add_parser("backtest")
    _add_common(backtest); backtest.add_argument("--json", type=Path)
    validate = sub.add_parser("validate")
    _add_common(validate); validate.add_argument("--train-fraction", type=float, default=0.70)
    validate.add_argument("--cost-stress", type=float, default=3.0)
    return parser


def _load(args):
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    bars = LocalBarDataSource(args.data).bars(symbols, _date(args.start), _date(args.end, end=True), args.timeframe)
    strategy = create_strategy(args.strategy, **_params(args.param))
    return bars, strategy, CostModel(args.commission_bps, args.half_spread_bps, args.slippage_bps), RiskLimits(args.max_gross, args.max_position, args.max_turnover)


def main() -> int:
    parser = build_parser(); args = parser.parse_args()
    try:
        if args.command == "doctor":
            print("trade-o-matic: OK\nresearch test bench: available\nYahoo bootstrap data: available\nDatabento: optional\nlive execution: disabled"); return 0
        if args.command == "strategies":
            for spec in STRATEGIES.values(): print(f"{spec.name:16} {spec.description:38} params={','.join(spec.parameters)}")
            return 0
        if args.command == "fetch":
            symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
            if args.source == "yahoo":
                manifest = fetch_yahoo(symbols, args.start, args.end, args.timeframe, args.output, adjusted=not args.unadjusted, prepost=args.prepost)
            else:
                if not args.dataset: raise ValueError("--dataset is required for Databento")
                manifest = fetch_databento(symbols, args.start, args.end, args.timeframe, args.output, dataset=args.dataset)
            print(f"Saved {manifest.rows:,} rows to {args.output}\nSHA256: {manifest.sha256}"); return 0
        if args.command in {"backtest", "validate"}:
            bars, strategy, costs, risk = _load(args)
            if args.command == "backtest":
                result = run_daily_strategy(bars, strategy, initial_capital=args.capital, costs=costs, risk=risk)
                _print_result(result, args.capital)
                if args.json:
                    args.json.parent.mkdir(parents=True, exist_ok=True); args.json.write_text(json.dumps(_result_dict(result), indent=2)+"\n")
                return 0
            if args.timeframe != "1d": raise ValueError("validation annualization/splitting is currently restricted to daily bars")
            report = validate_strategy(bars, strategy, train_fraction=args.train_fraction, initial_capital=args.capital, costs=costs, risk=risk, cost_stress_multiple=args.cost_stress)
            print(f"Strategy: {report.strategy}  split={report.split_timestamp.date()}")
            for label, result in [("IN-SAMPLE", report.in_sample),("OUT-OF-SAMPLE", report.out_of_sample),(f"OOS COST x{args.cost_stress:g}", report.stressed_out_of_sample)]:
                p=result.performance; print(f"{label:16} return={p.total_return:>8.2%} sharpe={p.sharpe:>6.2f} drawdown={p.max_drawdown:>8.2%} costs=${result.trading_costs:,.2f}")
            print(f"Basic robustness: {'PASS' if report.passed_basic_robustness else 'FAIL'}"); return 0
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        parser.error(str(exc))
    parser.print_help(); return 0


if __name__ == "__main__": raise SystemExit(main())
