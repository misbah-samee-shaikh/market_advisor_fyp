"""Read saved OHLCV, download only if missing, and safely validate split events."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re
from typing import Callable

import numpy as np
import pandas as pd

from core.corporate_actions import ensure_split_adjusted

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def symbol_filename(symbol: str) -> str:
    # Matches old cache naming: EURUSD=X -> EURUSD_X.csv
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol) + ".csv"


def clean_prices(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError("Empty market dataset")
    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip().title() for c in df.columns]
    if "Date" in df.columns:
        df = df.set_index("Date")

    if "Is_Anomaly" in df.columns:
        flagged = df["Is_Anomaly"].astype(str).str.lower().eq("true")
        df = df.loc[~flagged].drop(columns="Is_Anomaly")

    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.loc[~df.index.isna()].copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index = df.index.normalize()
    df = df.sort_index()
    df = df.loc[~df.index.duplicated(keep="last")]
    columns = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df]
    if "Close" not in columns:
        raise ValueError("Missing Close column in market dataset")
    df = df[columns].copy()
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.loc[df["Close"].notna() & np.isfinite(df["Close"]) & (df["Close"] > 0)]
    df.index.name = "Date"
    if df.empty:
        raise ValueError("No valid positive close prices")
    return df


def load_prices(
    market: str,
    symbol: str,
    fetcher: Callable[[str, str, str], pd.DataFrame],
    download_if_missing: bool,
) -> pd.DataFrame:
    path = DATA_DIR / market / symbol_filename(symbol)
    if path.is_file():
        data = clean_prices(pd.read_csv(path, index_col=0, parse_dates=True))
        print(f"[CACHE] {path.relative_to(ROOT)} — {len(data)} daily candles")
    else:
        if not download_if_missing:
            raise FileNotFoundError(f"Missing {path}; set DOWNLOAD_IF_MISSING=True")
        start = (date.today() - timedelta(days=730)).isoformat()
        end = (date.today() + timedelta(days=1)).isoformat()
        print(f"[DOWNLOAD] {market}/{symbol}, {start} to {end}", flush=True)
        data = clean_prices(fetcher(symbol, start, end))
        path.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(path)
        print(f"[SAVED] {path.relative_to(ROOT)} — {len(data)} daily candles")
    if len(data) < 90:
        raise ValueError(f"{symbol}: need at least 90 daily candles, got {len(data)}")
    # PSX: check known splits / unknown anomalies BEFORE any indicators or tests.
    # Crypto and Forex are returned unchanged.
    return ensure_split_adjusted(market, symbol, data, path)
