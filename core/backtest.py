"""Optional in-sample VectorBT trading-strategy simulation (long-only)."""
from pathlib import Path
import re

import pandas as pd
import vectorbt as vbt

ROOT = Path(__file__).resolve().parent.parent


def _number(value, digits=3):
    return round(float(value), digits) if pd.notna(value) else None


def run_backtest(close: pd.Series, signals: pd.Series,
                 save_chart: bool = False, market: str = "", symbol: str = "") -> dict:
    # Use today's close to decide; a signal can only execute on the following bar.
    # Simplified price model (next daily close): NOT a realistic fill model.
    buy_state = signals.eq("BUY")
    sell_state = signals.eq("SELL")
    entries = (buy_state & ~buy_state.shift(1, fill_value=False)).shift(1, fill_value=False)
    exits = (sell_state & ~sell_state.shift(1, fill_value=False)).shift(1, fill_value=False)
    portfolio = vbt.Portfolio.from_signals(
        close, entries=entries, exits=exits,
        init_cash=10_000, fees=0.001, slippage=0.0005, freq="1D",
    )
    stats = portfolio.stats()
    if save_chart:
        folder = ROOT / "reports"
        folder.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", f"{market}_{symbol}")
        portfolio.plot().write_html(str(folder / f"backtest_{stem}.html"))
    return {
        "total_return_pct": _number(stats["Total Return [%]"]),
        "max_drawdown_pct": _number(stats["Max Drawdown [%]"]),
        "trades": int(stats["Total Trades"]),
        "win_rate_pct": _number(stats["Win Rate [%]"]),
        "note": "In-sample, simplified long-only backtest; not predictive performance.",
    }
