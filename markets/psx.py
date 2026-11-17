"""Pakistan Stock Exchange adapter. Daily OHLCV from psxdata.

Split detection and verified corrections happen in core/corporate_actions.py.
Existing properly adjusted local CSVs are left unchanged.
"""
import pandas as pd

CURRENCY = "PKR"


def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    try:
        import psxdata
    except ImportError as exc:
        raise ImportError("Install psxdata: python -m pip install psxdata") from exc
    return psxdata.stocks(symbol, start=start, end=end, cache=True)
