from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .domain import Bar, Side
from .interfaces import Strategy
from .ledger import Ledger
from .metrics import Performance, calculate
from .risk import CostModel, RiskLimits, validate_weights


@dataclass(frozen=True, slots=True)
class ResearchResult:
    strategy: str
    equity: list[float]
    performance: Performance
    fills: int
    turnover: float
    trading_costs: float
    start: datetime
    end: datetime


def _group_bars(bars: Sequence[Bar]) -> dict[datetime, dict[str, Bar]]:
    grouped: dict[datetime, dict[str, Bar]] = defaultdict(dict)
    for bar in sorted(bars, key=lambda item: (item.timestamp, item.symbol)):
        if bar.symbol in grouped[bar.timestamp]:
            raise ValueError(f"duplicate bar for {bar.symbol} at {bar.timestamp}")
        grouped[bar.timestamp][bar.symbol] = bar
    return dict(sorted(grouped.items()))


def _weights_from_scores(scores: dict[str, float], limits: RiskLimits) -> dict[str, float]:
    active = {symbol: score for symbol, score in scores.items() if abs(score) > 1e-12}
    if not active:
        return {}
    denominator = sum(abs(score) for score in active.values())
    gross_target = min(limits.max_gross_exposure, limits.max_position_weight * len(active))
    weights = {
        symbol: gross_target * score / denominator
        for symbol, score in active.items()
    }
    validate_weights(weights, limits)
    return weights


def run_daily_strategy(
    bars: Sequence[Bar],
    strategy: Strategy,
    *,
    initial_capital: float = 100_000.0,
    costs: CostModel | None = None,
    risk: RiskLimits | None = None,
) -> ResearchResult:
    """Run a daily strategy with structurally delayed execution.

    At timestamp T the strategy receives bars through T and creates target weights.
    Those targets are *queued* and can only execute at the OPEN of the next timestamp.
    P&L is then marked at that timestamp's close. This prevents a close-derived signal
    from receiving the same close as an executable price.
    """
    if not bars:
        raise ValueError("no bars supplied")
    costs = costs or CostModel()
    risk = risk or RiskLimits()
    grouped = _group_bars(bars)
    timestamps = list(grouped)
    if len(timestamps) < 2:
        raise ValueError("at least two timestamps are required")

    ledger = Ledger(initial_capital)
    history: list[Bar] = []
    pending_weights: dict[str, float] | None = None
    current_weights: dict[str, float] = {}
    total_turnover = 0.0
    total_cost = 0.0

    for timestamp in timestamps:
        today = grouped[timestamp]

        # Execute yesterday's decision at today's open.
        if pending_weights is not None:
            open_prices = {symbol: bar.open for symbol, bar in today.items()}
            pretrade = ledger.mark(timestamp, open_prices)
            equity = pretrade.equity
            symbols = set(current_weights) | set(pending_weights)
            turnover = sum(
                abs(pending_weights.get(s, 0.0) - current_weights.get(s, 0.0))
                for s in symbols
            )
            if turnover > risk.max_turnover + 1e-12:
                raise ValueError(f"turnover {turnover:.4f} exceeds configured limit")

            for symbol in symbols:
                if symbol not in open_prices:
                    if abs(pending_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0)) > 1e-12:
                        raise ValueError(f"cannot rebalance {symbol}: no opening bar")
                    continue
                target_value = pending_weights.get(symbol, 0.0) * equity
                current_qty = ledger.positions.get(symbol).quantity if symbol in ledger.positions else 0.0
                current_value = current_qty * open_prices[symbol]
                trade_value = target_value - current_value
                if abs(trade_value) < 1e-9:
                    continue
                quantity = abs(trade_value) / open_prices[symbol]
                side = Side.BUY if trade_value > 0 else Side.SELL
                half_spread = costs.half_spread_bps / 10_000
                slippage = costs.slippage_bps / 10_000
                direction = 1 if side is Side.BUY else -1
                execution_price = open_prices[symbol] * (1 + direction * (half_spread + slippage))
                commission = abs(trade_value) * costs.commission_bps / 10_000
                slippage_cost = abs(trade_value) * (costs.half_spread_bps + costs.slippage_bps) / 10_000
                ledger.apply_fill(
                    timestamp=timestamp,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=execution_price,
                    commission=commission,
                    slippage_cost=slippage_cost,
                )
                total_cost += commission + slippage_cost
            total_turnover += turnover
            current_weights = dict(pending_weights)

        close_prices = {symbol: bar.close for symbol, bar in today.items()}
        ledger.mark(timestamp, close_prices)
        history.extend(today.values())
        signals = strategy.generate(history, timestamp)
        pending_weights = _weights_from_scores(
            {signal.symbol: signal.score for signal in signals}, risk
        )

    # Use close marks only (each day also has an optional pre-trade open mark).
    close_equity: list[float] = []
    for timestamp in timestamps:
        candidates = [s for s in ledger.snapshots if s.timestamp == timestamp]
        close_equity.append(candidates[-1].equity)

    return ResearchResult(
        strategy=strategy.name,
        equity=close_equity,
        performance=calculate(close_equity),
        fills=len(ledger.fills),
        turnover=total_turnover,
        trading_costs=total_cost,
        start=timestamps[0],
        end=timestamps[-1],
    )
