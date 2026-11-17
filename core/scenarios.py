"""Historical block-bootstrap scenario projections; no AI or future knowledge."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd


def simulate_scenarios(
    close: pd.Series,
    horizons=(7, 14, 30),
    simulations: int = 10_000,
    lookback: int = 252,
    block_size: int = 5,
    seed: int = 42,
) -> dict:
    if simulations < 100 or block_size < 1 or not horizons or min(horizons) < 1:
        raise ValueError("Invalid scenario settings")
    max_horizon = max(horizons)
    recent = close.tail(lookback + 1)
    returns = np.log(recent / recent.shift(1)).dropna().to_numpy(dtype=float)
    if len(returns) < max(60, block_size * 3):
        raise ValueError("Need at least 60 daily returns for scenario simulation")

    warning = []
    jumps = np.abs(np.expm1(returns)) > 0.30
    if np.any(jumps):
        warning.append("Daily changes above 30% detected; check splits and data quality.")

    rng = np.random.default_rng(seed)
    number_of_blocks = math.ceil(max_horizon / block_size)
    start_indices = rng.integers(
        0, len(returns) - block_size + 1,
        size=(simulations, number_of_blocks),
    )
    indices = start_indices[:, :, None] + np.arange(block_size)[None, None, :]
    sampled = returns[indices].reshape(simulations, -1)[:, :max_horizon]
    current = float(close.iloc[-1])
    paths = current * np.exp(np.cumsum(sampled, axis=1))

    rows = []
    for horizon in horizons:
        terminal = paths[:, horizon - 1]
        low, median, high = np.percentile(terminal, [10, 50, 90])
        rows.append({
            "sessions": int(horizon),
            "bearish_p10": round(float(low), 4),
            "median_p50": round(float(median), 4),
            "bullish_p90": round(float(high), 4),
            "median_change_pct": round(float(100 * (median / current - 1)), 2),
            "simulated_above_start_pct": round(float(100 * np.mean(terminal > current)), 2),
        })
    return {
        "method": "historical_block_bootstrap",
        "simulations": simulations,
        "lookback_returns": int(len(returns)),
        "block_size": block_size,
        "seed": seed,
        "scenarios": rows,
        "warnings": warning,
        "note": "Simulated ranges are not validated predictions or investment probabilities.",
    }
