"""Conservative PSX stock-split detection and adjustment for cached daily OHLCV.

Only KNOWN, SOURCE-VERIFIED splits are auto-corrected. An abnormal move without
an identified corporate action is flagged and blocks analysis instead of being
invented as a split. All corrections are idempotent and backed up.

The registry is independent of providers and can be extended using
`data/corporate_actions.json` (see `corporate_actions.example.json`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import uuid

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SplitEvent:
    date: str
    factor: float  # number of NEW shares for each OLD share (5-for-1 => 5.0)
    source: str


# Confirmed via PSX/Lucky Cement disclosure. No unverified corporate actions
# should be added here. See data/corporate_actions.json for extra confirmed splits.
VERIFIED_SPLITS: dict[str, tuple[SplitEvent, ...]] = {
    "LUCK": (
        SplitEvent(
            date="2025-04-28",
            factor=5.0,
            source="https://dps.psx.com.pk/download/document/257573.pdf",
        ),
    ),
}


class CorporateActionError(ValueError):
    """Prices cannot be safely analyzed until a suspected action is verified."""


def _split_events(symbol: str, registry_path: Path | None = None) -> list[SplitEvent]:
    events: dict[str, SplitEvent] = {
        event.date: event for event in VERIFIED_SPLITS.get(symbol.upper(), ())
    }
    path = registry_path or ROOT / "data" / "corporate_actions.json"
    if path.is_file():
        content = json.loads(path.read_text(encoding="utf-8"))
        records = content.get("psx", {}).get(symbol.upper(), [])
        if not isinstance(records, list):
            raise CorporateActionError(f"Expected a list of events for {symbol} in {path}")
        for obj in records:
            try:
                event = SplitEvent(
                    date=pd.Timestamp(obj["date"]).strftime("%Y-%m-%d"),
                    factor=float(obj["factor"]),
                    source=str(obj["source"]).strip(),
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise CorporateActionError(f"Invalid split event for {symbol}: {obj}") from exc
            if not (math.isfinite(event.factor) and event.factor > 0 and
                    event.factor != 1 and event.source):
                raise CorporateActionError(f"Invalid factor or missing verification source: {obj}")
            if event.date in events and events[event.date].factor != event.factor:
                raise CorporateActionError(
                    f"Conflicting split factors for {symbol} on {event.date}"
                )
            events[event.date] = event
    # Newer splits first to ensure all historical prices are expressed in
    # the latest post-split share units after a multi-split dataset is fixed.
    return sorted(events.values(), key=lambda item: item.date, reverse=True)


def _near(value: float, expected: float, tolerance_log: float = 0.20) -> bool:
    return value > 0 and abs(math.log(value / expected)) <= tolerance_log


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _atomic_save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="._split_", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            df.to_csv(f)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def ensure_split_adjusted(
    market: str,
    symbol: str,
    data: pd.DataFrame,
    cache_path: Path,
    registry_path: Path | None = None,
) -> pd.DataFrame:
    """Return checked/adjusted data and persist verified fixes to its cache.

    This function does NOT download corporate actions, assume large drops are
    splits, or alter currencies/crypto. It verifies known date+ratio first.
    """
    if market.lower() != "psx":
        return data

    symbol = symbol.upper()
    df = data.copy().sort_index()
    if df.empty or "Close" not in df.columns:
        raise CorporateActionError("Split checks require dated Close prices")
    events = _split_events(symbol, registry_path)
    messages: list[str] = []
    adjusted: list[SplitEvent] = []

    for event in events:
        split_day = pd.Timestamp(event.date)
        before = df.loc[df.index < split_day, "Close"]
        after = df.loc[df.index >= split_day, "Close"]
        if before.empty or after.empty:
            # No candles spanning the event: cannot and need not adjust.
            continue
        prev_day, next_day = before.index[-1], after.index[0]
        # Long suspensions or missing candles make close-to-close estimates
        # unreliable, even with a confirmed corporate-action date.
        if (split_day - prev_day).days > 21 or (next_day - split_day).days > 10:
            raise CorporateActionError(
                f"{symbol}: cannot safely check verified split {event.date}; "
                f"data gap around event is too long ({prev_day.date()} to {next_day.date()})."
            )

        ratio = float(before.iloc[-1] / after.iloc[0])
        looks_unadjusted = _near(ratio, event.factor)
        looks_adjusted = _near(ratio, 1.0)
        if looks_adjusted and not looks_unadjusted:
            messages.append(f"[SPLIT OK] {symbol} {event.date} already adjusted (ratio {ratio:.3f})")
            continue
        if looks_unadjusted and not looks_adjusted:
            mask = df.index < split_day
            for col in ("Open", "High", "Low", "Close"):
                if col in df.columns:
                    df.loc[mask, col] = df.loc[mask, col].astype(float) / event.factor
            if "Volume" in df.columns:
                df.loc[mask, "Volume"] = df.loc[mask, "Volume"].astype(float) * event.factor
            adjusted.append(event)
            messages.append(
                f"[SPLIT FIX] {symbol} {event.date}: {event.factor:g} new shares per old share; "
                f"adjusted pre-split OHLC and volume"
            )
            continue
        raise CorporateActionError(
            f"{symbol}: verified split {event.date} (factor {event.factor:g}), but "
            f"pre/post close ratio {ratio:.3f} is ambiguous. No data changed. "
            f"Inspect provider history before using it. Source: {event.source}"
        )

    # No automatic correction for arbitrary moves: prices can gap because of
    # dividends, rights/bonus issues, bad data, or genuine large moves.
    daily = df["Close"].pct_change(fill_method=None)
    suspicious = daily.loc[daily.abs() > 0.35]
    if len(suspicious):
        samples = ", ".join(f"{day:%Y-%m-%d} ({move:+.1%})" for day, move in suspicious.iloc[:5].items())
        raise CorporateActionError(
            f"{symbol}: unusually large daily price movement(s): {samples}. "
            "Possible UNVERIFIED split, bonus issue, corporate action or bad candle. "
            "Analysis stopped; no automatic adjustment was applied. Confirm the "
            "event in a PSX announcement, then add its date, factor and source "
            "to data/corporate_actions.json."
        )

    # Persist only AFTER all known-split checks and anomaly checks have passed.
    if adjusted:
        if not cache_path.exists():
            raise CorporateActionError(f"Cannot make split backup: cache missing at {cache_path}")
        backup_dir = cache_path.parent.parent / "backups" / "psx"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_dir / f"{cache_path.stem}_{stamp}_{uuid.uuid4().hex[:8]}.original.csv"
        shutil.copy2(cache_path, backup)
        _atomic_save_csv(df, cache_path)
        for msg in messages:
            print(msg)
        print(f"[BACKUP] Original PSX data saved to {_display_path(backup)}")
        print(f"[SAVED] Corrected cached data: {_display_path(cache_path)}")
    else:
        for msg in messages:
            print(msg)
    return df
