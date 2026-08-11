from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .interfaces import Strategy
from .strategies.baselines import DonchianBreakout, MeanReversionZScore, MovingAverageCrossover
from .strategies.trend import TimeSeriesMomentum


@dataclass(frozen=True, slots=True)
class StrategySpec:
    name: str
    description: str
    factory: Callable[..., Strategy]
    parameters: tuple[str, ...]


STRATEGIES: dict[str, StrategySpec] = {
    "tsmom": StrategySpec(
        "tsmom", "Time-series momentum", TimeSeriesMomentum, ("lookback", "horizon_days")
    ),
    "ma_cross": StrategySpec(
        "ma_cross", "Moving-average crossover", MovingAverageCrossover,
        ("fast", "slow", "horizon_days")
    ),
    "mean_reversion": StrategySpec(
        "mean_reversion", "Rolling price z-score mean reversion", MeanReversionZScore,
        ("lookback", "entry_z", "horizon_days")
    ),
    "donchian": StrategySpec(
        "donchian", "Donchian channel breakout", DonchianBreakout,
        ("lookback", "horizon_days")
    ),
}


def create_strategy(name: str, **parameters: object) -> Strategy:
    try:
        spec = STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown strategy {name!r}; choose from {', '.join(STRATEGIES)}") from exc
    unknown = set(parameters) - set(spec.parameters)
    if unknown:
        raise ValueError(f"unsupported parameters for {name}: {sorted(unknown)}")
    return spec.factory(**parameters)
