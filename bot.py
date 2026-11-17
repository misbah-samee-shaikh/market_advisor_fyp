"""FYP Market Advisor — edit the settings, then run: python bot.py.

Works with saved daily OHLCV CSV files, no network on repeat runs.
Experimental research only. Never places orders.
"""
from __future__ import annotations

from core.advisor import create_report
from core.backtest import run_backtest
from core.data import load_prices
from core.indicators import calculate_indicators
from core.reports import print_report, save_report
from core.scenarios import simulate_scenarios
from core.signals import generate_signals
from markets import crypto, forex, psx

# ===================== YOUR INPUTS =====================
MARKET = "psx"         # "crypto", "forex", or "psx"
SYMBOL = "HBL"        # crypto: BTC-USD / ETH-USD
                         # forex: EURUSD=X / GBPUSD=X
                         # psx: LUCK / HBL / OGDC

DOWNLOAD_IF_MISSING = True  # First run only; saved data is reused afterwards
SAVE_BACKTEST_CHART = False  # Optional HTML chart; not needed for the bot
SIMULATIONS = 10_000
SCENARIO_HORIZONS = (7, 14, 30)  # Future market sessions, not calendar days
# =======================================================

MARKET_ADAPTERS = {
    "crypto": crypto,
    "forex": forex,
    "psx": psx,
}


def main() -> None:
    market = MARKET.strip().lower()
    symbol = SYMBOL.strip().upper()
    if market not in MARKET_ADAPTERS:
        raise ValueError("MARKET must be 'crypto', 'forex', or 'psx'")
    if not symbol:
        raise ValueError("Set a nonempty SYMBOL in bot.py")
    if not SCENARIO_HORIZONS or min(SCENARIO_HORIZONS) < 1:
        raise ValueError("SCENARIO_HORIZONS must contain positive session counts")

    adapter = MARKET_ADAPTERS[market]
    prices = load_prices(
        market=market,
        symbol=symbol,
        fetcher=adapter.fetch_prices,
        download_if_missing=DOWNLOAD_IF_MISSING,
    )
    close = prices["Close"]

    indicators = calculate_indicators(close)
    signals = generate_signals(indicators)
    backtest = run_backtest(close, signals, save_chart=SAVE_BACKTEST_CHART,
                            market=market, symbol=symbol)
    projection = simulate_scenarios(close, horizons=SCENARIO_HORIZONS,
                                     simulations=SIMULATIONS)
    report = create_report(market, symbol, close, indicators, signals,
                           backtest, projection, currency=adapter.CURRENCY)
    path = save_report(report)
    print_report(report, path)


if __name__ == "__main__":
    main()
