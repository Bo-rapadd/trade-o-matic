from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .domain import Side


@dataclass(slots=True)
class Position:
    quantity: float = 0.0
    average_price: float = 0.0
    realized_pnl: float = 0.0


@dataclass(frozen=True, slots=True)
class LedgerFill:
    timestamp: datetime
    symbol: str
    side: Side
    quantity: float
    price: float
    commission: float
    slippage_cost: float


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    timestamp: datetime
    cash: float
    market_value: float
    equity: float
    gross_exposure: float


@dataclass(slots=True)
class Ledger:
    initial_cash: float
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    fills: list[LedgerFill] = field(default_factory=list)
    snapshots: list[AccountSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial cash must be positive")
        self.cash = self.initial_cash

    def apply_fill(
        self,
        *,
        timestamp: datetime,
        symbol: str,
        side: Side,
        quantity: float,
        price: float,
        commission: float = 0.0,
        slippage_cost: float = 0.0,
    ) -> None:
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        if commission < 0 or slippage_cost < 0:
            raise ValueError("fill costs cannot be negative")

        signed_qty = quantity if side is Side.BUY else -quantity
        position = self.positions.setdefault(symbol, Position())
        old_qty = position.quantity
        new_qty = old_qty + signed_qty

        # Cash includes the actual execution price. slippage_cost is informational;
        # commission is an additional cash charge.
        self.cash -= signed_qty * price
        self.cash -= commission

        if old_qty == 0 or old_qty * signed_qty > 0:
            total_abs = abs(old_qty) + abs(signed_qty)
            position.average_price = (
                (abs(old_qty) * position.average_price + abs(signed_qty) * price) / total_abs
            )
        else:
            closing_qty = min(abs(old_qty), abs(signed_qty))
            direction = 1.0 if old_qty > 0 else -1.0
            position.realized_pnl += closing_qty * (price - position.average_price) * direction
            if new_qty == 0:
                position.average_price = 0.0
            elif old_qty * new_qty < 0:
                position.average_price = price

        position.quantity = new_qty
        self.fills.append(
            LedgerFill(timestamp, symbol, side, quantity, price, commission, slippage_cost)
        )

    def mark(self, timestamp: datetime, prices: dict[str, float]) -> AccountSnapshot:
        market_value = 0.0
        gross = 0.0
        for symbol, position in self.positions.items():
            if abs(position.quantity) < 1e-15:
                continue
            if symbol not in prices:
                raise ValueError(f"missing mark price for open position {symbol}")
            value = position.quantity * prices[symbol]
            market_value += value
            gross += abs(value)
        equity = self.cash + market_value
        snapshot = AccountSnapshot(timestamp, self.cash, market_value, equity, gross)
        self.snapshots.append(snapshot)
        return snapshot
