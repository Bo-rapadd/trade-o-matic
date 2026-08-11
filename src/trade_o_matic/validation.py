from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Sequence

from .domain import Bar
from .interfaces import Strategy
from .research import ResearchResult, run_daily_strategy
from .risk import CostModel, RiskLimits


@dataclass(frozen=True, slots=True)
class ValidationReport:
    strategy: str
    in_sample: ResearchResult
    out_of_sample: ResearchResult
    stressed_out_of_sample: ResearchResult
    split_timestamp: datetime

    @property
    def passed_basic_robustness(self) -> bool:
        return (
            self.out_of_sample.performance.total_return > 0
            and self.stressed_out_of_sample.performance.total_return > 0
            and self.out_of_sample.performance.max_drawdown > -0.50
        )


def chronological_split(bars: Sequence[Bar], train_fraction: float = 0.70) -> tuple[list[Bar], list[Bar], datetime]:
    if not 0.5 <= train_fraction < 0.95:
        raise ValueError("train_fraction must be in [0.5, 0.95)")
    timestamps = sorted({bar.timestamp for bar in bars})
    if len(timestamps) < 10:
        raise ValueError("validation requires at least 10 timestamps")
    index = max(2, min(len(timestamps) - 2, int(len(timestamps) * train_fraction)))
    split = timestamps[index]
    train = [bar for bar in bars if bar.timestamp < split]
    test = [bar for bar in bars if bar.timestamp >= split]
    return train, test, split


def validate_strategy(
    bars: Sequence[Bar],
    strategy: Strategy,
    *,
    train_fraction: float = 0.70,
    initial_capital: float = 100_000.0,
    costs: CostModel | None = None,
    risk: RiskLimits | None = None,
    cost_stress_multiple: float = 3.0,
) -> ValidationReport:
    if cost_stress_multiple < 1:
        raise ValueError("cost stress multiple must be >= 1")
    costs = costs or CostModel()
    train, test, split = chronological_split(bars, train_fraction)
    stressed = CostModel(
        commission_bps=costs.commission_bps * cost_stress_multiple,
        half_spread_bps=costs.half_spread_bps * cost_stress_multiple,
        slippage_bps=costs.slippage_bps * cost_stress_multiple,
    )
    return ValidationReport(
        strategy=strategy.name,
        in_sample=run_daily_strategy(train, strategy, initial_capital=initial_capital, costs=costs, risk=risk),
        out_of_sample=run_daily_strategy(test, strategy, initial_capital=initial_capital, costs=costs, risk=risk),
        stressed_out_of_sample=run_daily_strategy(test, strategy, initial_capital=initial_capital, costs=stressed, risk=risk),
        split_timestamp=split,
    )
