"""Crypto market adapter. Yahoo Finance daily candles (e.g. BTC-USD)."""
import pandas as pd
import yfinance as yf

CURRENCY = "USD (quote)"


def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    return yf.download(
        symbol, start=start, end=end, interval="1d", auto_adjust=True,
        threads=False, progress=False, timeout=12, multi_level_index=False,
    )
