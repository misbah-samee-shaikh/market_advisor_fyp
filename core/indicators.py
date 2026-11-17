"""Shared technical indicators; calculated by VectorBT, not per-market code."""
import pandas as pd
import vectorbt as vbt


def calculate_indicators(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "close": close,
        "ma20": vbt.MA.run(close, window=20).ma,
        "ma50": vbt.MA.run(close, window=50).ma,
        "rsi14": vbt.RSI.run(close, window=14).rsi,
    }, index=close.index)
