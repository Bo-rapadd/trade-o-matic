from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("bar timestamp must be timezone-aware")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("inconsistent OHLC bar")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")


@dataclass(frozen=True, slots=True)
class Signal:
    strategy: str
    symbol: str
    timestamp: datetime
    score: float
    horizon: timedelta
    expected_return: float | None = None
    confidence: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not -1 <= self.score <= 1:
            raise ValueError("score must be in [-1, 1]")
        if self.horizon <= timedelta(0):
            raise ValueError("horizon must be positive")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class Order:
    client_order_id: str
    symbol: str
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    strategy: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type is OrderType.LIMIT and (
            self.limit_price is None or self.limit_price <= 0
        ):
            raise ValueError("limit orders require a positive limit price")


@dataclass(frozen=True, slots=True)
class Fill:
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    slippage: float = 0.0
