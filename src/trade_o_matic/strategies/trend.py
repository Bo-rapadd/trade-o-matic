from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from ..domain import Bar, Signal
from ..interfaces import Strategy


@dataclass(frozen=True, slots=True)
class TimeSeriesMomentum(Strategy):
    lookback: int = 252
    horizon_days: int = 21
    name: str = "tsmom"

    def generate(self, history: Sequence[Bar], as_of: datetime) -> list[Signal]:
        grouped: dict[str, list[Bar]] = defaultdict(list)
        for bar in history:
            if bar.timestamp <= as_of:
                grouped[bar.symbol].append(bar)

        signals: list[Signal] = []
        for symbol, bars in grouped.items():
            bars.sort(key=lambda bar: bar.timestamp)
            if len(bars) < self.lookback + 1:
                continue
            window = bars[-(self.lookback + 1) :]
            lookback_return = window[-1].close / window[0].close - 1
            score = 1.0 if lookback_return > 0 else -1.0 if lookback_return < 0 else 0.0
            signals.append(
                Signal(
                    strategy=self.name,
                    symbol=symbol,
                    timestamp=as_of,
                    score=score,
                    horizon=timedelta(days=self.horizon_days),
                    metadata={"lookback": self.lookback, "lookback_return": lookback_return},
                )
            )
        return signals
