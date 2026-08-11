from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    commission_bps: float = 0.0
    half_spread_bps: float = 1.0
    slippage_bps: float = 1.0

    @property
    def total_bps(self) -> float:
        return self.commission_bps + self.half_spread_bps + self.slippage_bps

    def estimate(self, notional: float) -> float:
        if notional < 0:
            raise ValueError("notional must be non-negative")
        return notional * self.total_bps / 10_000


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_gross_exposure: float = 1.0
    max_position_weight: float = 0.10
    max_turnover: float = 0.50
    max_drawdown: float = 0.20

    def __post_init__(self) -> None:
        if self.max_gross_exposure <= 0:
            raise ValueError("max gross exposure must be positive")
        if not 0 < self.max_position_weight <= self.max_gross_exposure:
            raise ValueError("invalid max position weight")
        if self.max_turnover <= 0:
            raise ValueError("max turnover must be positive")
        if not 0 < self.max_drawdown < 1:
            raise ValueError("max drawdown must be in (0, 1)")


class RiskViolation(RuntimeError):
    pass


def validate_weights(weights: dict[str, float], limits: RiskLimits) -> None:
    gross = sum(abs(weight) for weight in weights.values())
    if gross > limits.max_gross_exposure + 1e-12:
        raise RiskViolation("gross exposure limit exceeded")
    for symbol, weight in weights.items():
        if abs(weight) > limits.max_position_weight + 1e-12:
            raise RiskViolation(f"position limit exceeded for {symbol}")
