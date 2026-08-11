from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .metrics import Performance, calculate
from .risk import CostModel, RiskLimits, validate_weights


@dataclass(frozen=True, slots=True)
class BacktestResult:
    equity: list[float]
    gross_equity: list[float]
    turnover: float
    trading_costs: float
    performance: Performance


def run_weight_backtest(
    returns: list[Mapping[str, float]],
    target_weights: list[Mapping[str, float]],
    *,
    initial_capital: float = 100_000.0,
    costs: CostModel | None = None,
    risk: RiskLimits | None = None,
) -> BacktestResult:
    """Deterministic close-to-close portfolio simulator.

    Weight chosen at index t is applied to return t. Callers are responsible for
    constructing weights only from information available before that return. This
    deliberately small engine is the accounting baseline; event/intraday execution
    will be layered on top without changing strategy or broker interfaces.
    """
    if len(returns) != len(target_weights):
        raise ValueError("returns and target weights must have equal length")
    if initial_capital <= 0:
        raise ValueError("initial capital must be positive")

    costs = costs or CostModel()
    risk = risk or RiskLimits()
    net_equity = [initial_capital]
    gross_equity = [initial_capital]
    previous: dict[str, float] = {}
    total_turnover = 0.0
    total_cost = 0.0

    for period_returns, weights_mapping in zip(returns, target_weights, strict=True):
        weights = dict(weights_mapping)
        validate_weights(weights, risk)
        symbols = set(previous) | set(weights)
        turnover = sum(abs(weights.get(s, 0.0) - previous.get(s, 0.0)) for s in symbols)
        if turnover > risk.max_turnover + 1e-12:
            raise ValueError(f"turnover {turnover:.4f} exceeds configured limit")

        gross_return = sum(weights.get(symbol, 0.0) * value for symbol, value in period_returns.items())
        period_cost = costs.estimate(net_equity[-1] * turnover)
        gross_equity.append(gross_equity[-1] * (1 + gross_return))
        net_equity.append(net_equity[-1] * (1 + gross_return) - period_cost)
        total_turnover += turnover
        total_cost += period_cost
        previous = weights

    return BacktestResult(
        equity=net_equity,
        gross_equity=gross_equity,
        turnover=total_turnover,
        trading_costs=total_cost,
        performance=calculate(net_equity),
    )
