from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from trade_o_matic.data_local import LocalBarDataSource
from trade_o_matic.domain import Bar, Side
from trade_o_matic.interfaces import Strategy
from trade_o_matic.ledger import Ledger
from trade_o_matic.research import run_daily_strategy
from trade_o_matic.risk import CostModel, RiskLimits
from trade_o_matic.strategies.trend import TimeSeriesMomentum


UTC = timezone.utc


def bar(day: int, *, open_: float, close: float, symbol: str = "TEST") -> Bar:
    ts = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day)
    return Bar(symbol, ts, open_, max(open_, close), min(open_, close), close, 1_000_000)


class CloseDirection(Strategy):
    """Signal intentionally depends on today's close; execution must wait until tomorrow."""

    name = "close-direction"

    def generate(self, history, as_of):
        from datetime import timedelta
        from trade_o_matic.domain import Signal

        latest = [item for item in history if item.timestamp == as_of][0]
        score = 1.0 if latest.close > latest.open else -1.0
        return [Signal(self.name, latest.symbol, as_of, score, timedelta(days=1))]


def test_close_signal_cannot_capture_same_day_move():
    bars = [
        bar(0, open_=100, close=200),  # signal becomes long only after this close
        bar(1, open_=200, close=200),  # executes here; no profit available
        bar(2, open_=200, close=200),
    ]
    result = run_daily_strategy(
        bars,
        CloseDirection(),
        costs=CostModel(0, 0, 0),
        risk=RiskLimits(max_position_weight=1.0, max_gross_exposure=1.0, max_turnover=2.0),
    )
    assert result.performance.total_return == pytest.approx(0.0)


def test_execution_costs_reduce_equity():
    bars = [bar(i, open_=100 + i, close=101 + i) for i in range(5)]
    zero = run_daily_strategy(
        bars,
        TimeSeriesMomentum(lookback=1),
        costs=CostModel(0, 0, 0),
        risk=RiskLimits(max_position_weight=1.0, max_gross_exposure=1.0, max_turnover=2.0),
    )
    costly = run_daily_strategy(
        bars,
        TimeSeriesMomentum(lookback=1),
        costs=CostModel(2, 3, 5),
        risk=RiskLimits(max_position_weight=1.0, max_gross_exposure=1.0, max_turnover=2.0),
    )
    assert costly.equity[-1] < zero.equity[-1]
    assert costly.trading_costs > 0


def test_ledger_round_trip_realized_pnl():
    ledger = Ledger(10_000)
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    ledger.apply_fill(timestamp=ts, symbol="X", side=Side.BUY, quantity=10, price=100)
    ledger.apply_fill(timestamp=ts, symbol="X", side=Side.SELL, quantity=10, price=110)
    assert ledger.cash == pytest.approx(10_100)
    assert ledger.positions["X"].quantity == pytest.approx(0)
    assert ledger.positions["X"].realized_pnl == pytest.approx(100)


def test_local_source_rejects_duplicate_bars(tmp_path):
    path = tmp_path / "bars.csv"
    pd.DataFrame(
        [
            {"symbol": "X", "timestamp": "2026-01-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
            {"symbol": "X", "timestamp": "2026-01-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        ]
    ).to_csv(path, index=False)
    source = LocalBarDataSource(path)
    with pytest.raises(ValueError, match="duplicate"):
        source.latest(["X"], "1d")
