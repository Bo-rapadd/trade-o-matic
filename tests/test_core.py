from datetime import datetime, timedelta, timezone

import pytest

from trade_o_matic.backtest import run_weight_backtest
from trade_o_matic.domain import Bar, Signal
from trade_o_matic.risk import CostModel, RiskLimits, RiskViolation, validate_weights


def test_bar_requires_timezone():
    with pytest.raises(ValueError):
        Bar("SPY", datetime(2026, 1, 1), 100, 101, 99, 100, 1000)


def test_signal_score_is_bounded():
    with pytest.raises(ValueError):
        Signal("x", "SPY", datetime.now(timezone.utc), 1.1, timedelta(days=1))


def test_risk_rejects_large_position():
    with pytest.raises(RiskViolation):
        validate_weights({"SPY": 0.2}, RiskLimits(max_position_weight=0.1))


def test_backtest_applies_costs():
    result = run_weight_backtest(
        returns=[{"SPY": 0.01}, {"SPY": 0.01}],
        target_weights=[{"SPY": 0.1}, {"SPY": 0.1}],
        costs=CostModel(commission_bps=1, half_spread_bps=1, slippage_bps=1),
        risk=RiskLimits(max_position_weight=0.2, max_turnover=1.0),
    )
    assert result.trading_costs > 0
    assert result.equity[-1] < result.gross_equity[-1]


def test_backtest_rejects_turnover_violation():
    with pytest.raises(ValueError):
        run_weight_backtest(
            returns=[{"SPY": 0.0}],
            target_weights=[{"SPY": 0.5}],
            risk=RiskLimits(max_position_weight=0.5, max_turnover=0.1),
        )
