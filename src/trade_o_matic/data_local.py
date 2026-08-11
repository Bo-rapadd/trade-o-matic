from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from .domain import Bar
from .interfaces import MarketDataSource

_REQUIRED = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
_SUPPORTED = {"1s", "1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1day", "daily"}


def _to_utc(value: object) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


@dataclass(slots=True)
class LocalBarDataSource(MarketDataSource):
    """Reproducible local OHLCV source backed by CSV or Parquet."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)

    def _frame(self) -> pd.DataFrame:
        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            frame = pd.read_csv(self.path)
        elif suffix in {".parquet", ".pq"}:
            frame = pd.read_parquet(self.path)
        else:
            raise ValueError("market data must be CSV or Parquet")
        missing = _REQUIRED - set(frame.columns)
        if missing:
            raise ValueError(f"market data missing columns: {sorted(missing)}")
        frame = frame[["symbol", "timestamp", "open", "high", "low", "close", "volume"]].copy()
        frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        if frame[["symbol", "timestamp"]].duplicated().any():
            raise ValueError("duplicate symbol/timestamp bars detected")
        for column in ["open", "high", "low", "close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        return frame.sort_values(["timestamp", "symbol"]).reset_index(drop=True)

    @staticmethod
    def _rows_to_bars(frame: pd.DataFrame) -> list[Bar]:
        return [Bar(row.symbol, _to_utc(row.timestamp), float(row.open), float(row.high),
                    float(row.low), float(row.close), float(row.volume))
                for row in frame.itertuples(index=False)]

    def bars(self, symbols: Sequence[str], start: datetime, end: datetime, timeframe: str) -> list[Bar]:
        if timeframe not in _SUPPORTED:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
        end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)
        wanted = {symbol.upper() for symbol in symbols}
        frame = self._frame()
        mask = (frame["symbol"].isin(wanted) &
                (frame["timestamp"] >= pd.Timestamp(start_utc)) &
                (frame["timestamp"] <= pd.Timestamp(end_utc)))
        return self._rows_to_bars(frame.loc[mask])

    def latest(self, symbols: Sequence[str], timeframe: str) -> list[Bar]:
        if timeframe not in _SUPPORTED:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        wanted = {symbol.upper() for symbol in symbols}
        frame = self._frame()
        frame = frame[frame["symbol"].isin(wanted)]
        if frame.empty:
            return []
        latest = frame.sort_values("timestamp").groupby("symbol", as_index=False).tail(1)
        return self._rows_to_bars(latest.sort_values("symbol"))
