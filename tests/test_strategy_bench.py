from datetime import datetime, timedelta, timezone

import pytest

from trade_o_matic.domain import Bar
from trade_o_matic.registry import STRATEGIES, create_strategy
from trade_o_matic.validation import chronological_split


def bars(count: int = 300) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(count):
        price = 100 + i * 0.1
        result.append(Bar("AAA", start + timedelta(days=i), price, price + 1, price - 1, price + 0.2, 1000))
    return result


def test_registry_exposes_multiple_strategy_families():
    assert {"tsmom", "ma_cross", "mean_reversion", "donchian"} <= set(STRATEGIES)


def test_registry_rejects_unknown_parameters():
    with pytest.raises(ValueError):
        create_strategy("tsmom", nonsense=1)


def test_all_registered_strategies_generate_without_future_data():
    history = bars()
    as_of = history[-1].timestamp
    configs = {
        "tsmom": {"lookback": 20},
        "ma_cross": {"fast": 5, "slow": 20},
        "mean_reversion": {"lookback": 20},
        "donchian": {"lookback": 20},
    }
    future = Bar("AAA", as_of + timedelta(days=1), 1, 10000, 0.5, 9999, 1000)
    for name, params in configs.items():
        strategy = create_strategy(name, **params)
        before = strategy.generate(history, as_of)
        after = strategy.generate(history + [future], as_of)
        assert before == after


def test_chronological_split_has_no_timestamp_overlap():
    train, test, split = chronological_split(bars(100), 0.7)
    assert max(bar.timestamp for bar in train) < split
    assert min(bar.timestamp for bar in test) >= split
