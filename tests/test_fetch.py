from datetime import datetime, timezone

import pandas as pd

from trade_o_matic.data_local import LocalBarDataSource
from trade_o_matic.fetch import FetchManifest, _write_snapshot


def test_snapshot_writes_manifest_and_digest(tmp_path):
    frame = pd.DataFrame([{
        "symbol": "SPY", "timestamp": "2026-01-02T14:30:00Z", "open": 100.0,
        "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000,
    }])
    path = tmp_path / "bars.parquet"
    manifest = _write_snapshot(frame, path, FetchManifest(
        "test", ["SPY"], "2026-01-02", "2026-01-03", "1m", 1,
        "2026-01-03T00:00:00+00:00", False,
    ))
    assert path.exists()
    assert path.with_suffix(".parquet.manifest.json").exists()
    assert manifest.sha256 and len(manifest.sha256) == 64


def test_local_source_accepts_intraday(tmp_path):
    path = tmp_path / "bars.csv"
    pd.DataFrame([
        {"symbol":"SPY","timestamp":"2026-01-02T14:30:00Z","open":100,"high":101,"low":99,"close":100.5,"volume":1000},
        {"symbol":"SPY","timestamp":"2026-01-02T14:35:00Z","open":100.5,"high":102,"low":100,"close":101.5,"volume":1200},
    ]).to_csv(path, index=False)
    bars = LocalBarDataSource(path).bars(
        ["SPY"], datetime(2026,1,2,tzinfo=timezone.utc),
        datetime(2026,1,3,tzinfo=timezone.utc), "5m",
    )
    assert len(bars) == 2
    assert bars[1].close == 101.5
