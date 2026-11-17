"""Experiment-only BUY/SELL/WAIT rules, shared by all asset classes."""
import numpy as np
import pandas as pd


def generate_signals(indicators: pd.DataFrame) -> pd.Series:
    buy = (
        (indicators["ma20"] > indicators["ma50"])
        & indicators["rsi14"].between(40, 70, inclusive="left")
    )
    sell = (
        (indicators["ma20"] < indicators["ma50"])
        | (indicators["rsi14"] > 75)
    )
    labels = np.select([buy, sell], ["BUY", "SELL"], default="WAIT")
    return pd.Series(labels, index=indicators.index, name="signal")
