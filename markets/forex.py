"""Forex market adapter. Yahoo Finance daily candles (e.g. EURUSD=X)."""
import pandas as pd
import yfinance as yf

CURRENCY = "quote currency per base currency"


def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    return yf.download(
        symbol, start=start, end=end, interval="1d", auto_adjust=True,
        threads=False, progress=False, timeout=12, multi_level_index=False,
    )
