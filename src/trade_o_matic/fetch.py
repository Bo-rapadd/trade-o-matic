from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd


@dataclass(frozen=True, slots=True)
class FetchManifest:
    source: str
    symbols: list[str]
    start: str
    end: str
    timeframe: str
    rows: int
    fetched_at: str
    adjusted: bool
    dataset: str | None = None
    sha256: str | None = None


def _write_snapshot(frame: pd.DataFrame, output: Path, manifest: FetchManifest) -> FetchManifest:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = frame.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    if output.suffix.lower() == ".csv":
        frame.to_csv(output, index=False)
    else:
        frame.to_parquet(output, index=False)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    final = FetchManifest(**{**asdict(manifest), "sha256": digest})
    output.with_suffix(output.suffix + ".manifest.json").write_text(
        json.dumps(asdict(final), indent=2) + "\n"
    )
    return final


def fetch_yahoo(
    symbols: Sequence[str],
    start: str,
    end: str,
    timeframe: str,
    output: Path,
    *,
    adjusted: bool = True,
    prepost: bool = False,
) -> FetchManifest:
    import yfinance as yf

    interval_map = {
        "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
        "60m": "60m", "1h": "1h", "1d": "1d",
    }
    if timeframe not in interval_map:
        raise ValueError(f"Yahoo timeframe not supported: {timeframe}")
    wanted = [s.upper() for s in symbols]
    raw = yf.download(
        wanted, start=start, end=end, interval=interval_map[timeframe], auto_adjust=adjusted,
        actions=False, repair=True, prepost=prepost, group_by="ticker", threads=True,
        progress=False,
    )
    if raw is None or raw.empty:
        raise ValueError("Yahoo returned no data")

    pieces: list[pd.DataFrame] = []
    if len(wanted) == 1:
        if isinstance(raw.columns, pd.MultiIndex):
            try:
                part = raw[wanted[0]].copy()
            except KeyError:
                part = raw.xs(wanted[0], axis=1, level=1).copy()
        else:
            part = raw.copy()
        part["symbol"] = wanted[0]
        pieces.append(part)
    else:
        for symbol in wanted:
            try:
                part = raw[symbol].copy()
            except KeyError:
                part = raw.xs(symbol, axis=1, level=1).copy()
            if not part.empty:
                part["symbol"] = symbol
                pieces.append(part)

    frame = pd.concat(pieces).reset_index()
    time_col = frame.columns[0]
    frame = frame.rename(columns={
        time_col: "timestamp", "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame[["symbol", "timestamp", "open", "high", "low", "close", "volume"]]
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    return _write_snapshot(
        frame, output,
        FetchManifest("yahoo", wanted, start, end, timeframe, len(frame),
                      datetime.now(timezone.utc).isoformat(), adjusted),
    )


def fetch_databento(
    symbols: Sequence[str],
    start: str,
    end: str,
    timeframe: str,
    output: Path,
    *,
    dataset: str,
    api_key: str | None = None,
) -> FetchManifest:
    try:
        import databento as db
    except ImportError as exc:
        raise RuntimeError("Install Databento support with: pip install -e '.[databento]'") from exc

    schema_map = {"1s": "ohlcv-1s", "1m": "ohlcv-1m", "1h": "ohlcv-1h", "1d": "ohlcv-1d"}
    if timeframe not in schema_map:
        raise ValueError("Databento direct OHLCV supports 1s, 1m, 1h, or 1d; resample locally for other bars")
    key = api_key or os.getenv("DATABENTO_API_KEY")
    if not key:
        raise ValueError("DATABENTO_API_KEY is required")
    client = db.Historical(key)
    data = client.timeseries.get_range(
        dataset=dataset,
        schema=schema_map[timeframe],
        symbols=[s.upper() for s in symbols],
        start=start,
        end=end,
        stype_in="raw_symbol",
    )
    frame = data.to_df().reset_index()
    if frame.empty:
        raise ValueError("Databento returned no data")
    symbol_col = "symbol" if "symbol" in frame.columns else "raw_symbol"
    if symbol_col not in frame.columns:
        raise ValueError("Databento response does not contain resolved symbols")
    ts_col = "ts_event" if "ts_event" in frame.columns else frame.columns[0]
    frame = frame.rename(columns={symbol_col: "symbol", ts_col: "timestamp"})
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame[["symbol", "timestamp", "open", "high", "low", "close", "volume"]]
    return _write_snapshot(
        frame, output,
        FetchManifest("databento", [s.upper() for s in symbols], start, end, timeframe, len(frame),
                      datetime.now(timezone.utc).isoformat(), False, dataset=dataset),
    )
