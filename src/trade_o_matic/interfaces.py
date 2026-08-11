from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Mapping, Sequence

from .domain import Bar, Fill, Order, Signal


class Strategy(ABC):
    """Pure research component: it observes history and emits signals only."""

    name: str

    @abstractmethod
    def generate(self, history: Sequence[Bar], as_of: datetime) -> list[Signal]:
        raise NotImplementedError


class MarketDataSource(ABC):
    """Vendor-neutral market-data boundary."""

    @abstractmethod
    def bars(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> list[Bar]:
        raise NotImplementedError

    @abstractmethod
    def latest(self, symbols: Sequence[str], timeframe: str) -> list[Bar]:
        raise NotImplementedError


class Broker(ABC):
    """Paper/live execution boundary. Backtests must never depend on a broker SDK."""

    @abstractmethod
    def submit(self, order: Order) -> str:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, broker_order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def open_orders(self) -> Mapping[str, Order]:
        raise NotImplementedError

    @abstractmethod
    def fills(self) -> Sequence[Fill]:
        raise NotImplementedError
