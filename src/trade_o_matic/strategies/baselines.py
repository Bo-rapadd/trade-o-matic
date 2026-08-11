from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Sequence

from ..domain import Bar, Signal
from ..interfaces import Strategy


def _group(history: Sequence[Bar], as_of: datetime) -> dict[str, list[Bar]]:
    grouped: dict[str, list[Bar]] = defaultdict(list)
    for bar in history:
        if bar.timestamp <= as_of:
            grouped[bar.symbol].append(bar)
    for bars in grouped.values():
        bars.sort(key=lambda item: item.timestamp)
    return grouped


@dataclass(frozen=True, slots=True)
class MovingAverageCrossover(Strategy):
    fast: int = 50
    slow: int = 200
    horizon_days: int = 21
    name: str = "ma_cross"

    def __post_init__(self) -> None:
        if self.fast <= 0 or self.slow <= self.fast:
            raise ValueError("require 0 < fast < slow")

    def generate(self, history: Sequence[Bar], as_of: datetime) -> list[Signal]:
        signals: list[Signal] = []
        for symbol, bars in _group(history, as_of).items():
            if len(bars) < self.slow:
                continue
            closes = [bar.close for bar in bars]
            fast_value = mean(closes[-self.fast :])
            slow_value = mean(closes[-self.slow :])
            spread = fast_value / slow_value - 1.0
            score = 1.0 if spread > 0 else -1.0 if spread < 0 else 0.0
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=symbol,
                    timestamp=as_of,
                    score=score,
                    horizon=timedelta(days=self.horizon_days),
                    metadata={"fast": self.fast, "slow": self.slow, "ma_spread": spread},
                )
            )
        return signals


@dataclass(frozen=True, slots=True)
class MeanReversionZScore(Strategy):
    lookback: int = 20
    entry_z: float = 1.5
    horizon_days: int = 5
    name: str = "mean_reversion"

    def __post_init__(self) -> None:
        if self.lookback < 3 or self.entry_z <= 0:
            raise ValueError("invalid mean-reversion parameters")

    def generate(self, history: Sequence[Bar], as_of: datetime) -> list[Signal]:
        signals: list[Signal] = []
        for symbol, bars in _group(history, as_of).items():
            if len(bars) < self.lookback:
                continue
            closes = [bar.close for bar in bars[-self.lookback :]]
            mu = mean(closes)
            sigma = pstdev(closes)
            z = (closes[-1] - mu) / sigma if sigma > 0 else 0.0
            if z >= self.entry_z:
                score = -1.0
            elif z <= -self.entry_z:
                score = 1.0
            else:
                score = 0.0
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=symbol,
                    timestamp=as_of,
                    score=score,
                    horizon=timedelta(days=self.horizon_days),
                    metadata={"lookback": self.lookback, "zscore": z, "entry_z": self.entry_z},
                )
            )
        return signals


@dataclass(frozen=True, slots=True)
class DonchianBreakout(Strategy):
    lookback: int = 55
    horizon_days: int = 20
    name: str = "donchian"

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")

    def generate(self, history: Sequence[Bar], as_of: datetime) -> list[Signal]:
        signals: list[Signal] = []
        for symbol, bars in _group(history, as_of).items():
            if len(bars) < self.lookback + 1:
                continue
            previous = bars[-(self.lookback + 1) : -1]
            current = bars[-1].close
            upper = max(bar.high for bar in previous)
            lower = min(bar.low for bar in previous)
            score = 1.0 if current > upper else -1.0 if current < lower else 0.0
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=symbol,
                    timestamp=as_of,
                    score=score,
                    horizon=timedelta(days=self.horizon_days),
                    metadata={"lookback": self.lookback, "upper": upper, "lower": lower},
                )
            )
        return signals
