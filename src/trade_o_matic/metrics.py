from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np


@dataclass(frozen=True, slots=True)
class Performance:
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float


def calculate(equity: list[float], periods_per_year: int = 252) -> Performance:
    values = np.asarray(equity, dtype=float)
    if len(values) < 2 or np.any(values <= 0):
        raise ValueError("equity must contain at least two positive observations")

    returns = values[1:] / values[:-1] - 1
    total = values[-1] / values[0] - 1
    years = len(returns) / periods_per_year
    annual_return = (values[-1] / values[0]) ** (1 / years) - 1
    volatility = float(np.std(returns, ddof=0))
    annual_vol = volatility * sqrt(periods_per_year)
    sharpe = float(np.mean(returns) / volatility * sqrt(periods_per_year)) if volatility else 0.0
    downside = returns[returns < 0]
    downside_vol = float(np.std(downside, ddof=0)) if len(downside) else 0.0
    sortino = (
        float(np.mean(returns) / downside_vol * sqrt(periods_per_year)) if downside_vol else 0.0
    )
    peaks = np.maximum.accumulate(values)
    max_drawdown = float(np.min(values / peaks - 1))
    return Performance(total, annual_return, annual_vol, sharpe, sortino, max_drawdown)
