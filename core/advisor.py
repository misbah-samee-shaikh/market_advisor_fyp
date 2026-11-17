"""Combine indicators, technical label, and scenarios in ONE readable result."""
from __future__ import annotations

from datetime import date
import pandas as pd


def _float(value):
    return round(float(value), 4) if pd.notna(value) else None


def create_report(market, symbol, close, indicators, signals,
                  backtest, projection, currency):
    last = indicators.iloc[-1]
    signal = str(signals.iloc[-1])
    as_of = close.index[-1].date()
    trend = "up" if last["ma20"] > last["ma50"] else (
        "down" if last["ma20"] < last["ma50"] else "flat"
    )
    reasons = [
        f"The 20-session moving average is {'above' if trend == 'up' else 'below' if trend == 'down' else 'equal to'} the 50-session average.",
    ]
    rsi = float(last["rsi14"])
    if rsi < 30:
        reasons.append(f"RSI {rsi:.1f} is oversold, which also creates rebound risk.")
    elif rsi > 70:
        reasons.append(f"RSI {rsi:.1f} is elevated/overbought; reversals are possible.")
    else:
        reasons.append(f"RSI {rsi:.1f} is between 30 and 70.")
    reasons.append({
        "BUY": "BUY means a potential long entry under our experimental rules.",
        "SELL": "SELL means exit or avoid a long position; NOT a short-selling instruction.",
        "WAIT": "WAIT means neither entry nor exit rule is active.",
    }[signal])

    selected = projection["scenarios"][-1]
    med_change = selected["median_change_pct"]
    tilt = "upward" if med_change > 0.5 else (
        "downward" if med_change < -0.5 else "near-flat"
    )
    if signal == "WAIT" or tilt == "near-flat":
        alignment = "inconclusive"
    elif (signal == "BUY" and tilt == "upward") or (signal == "SELL" and tilt == "downward"):
        alignment = "same_direction"
    else:
        alignment = "different_direction"
    reasons.append(
        f"{selected['sessions']}-session simulated median is {med_change:+.2f}% "
        f"from the last close; technical/scenario alignment: {alignment}."
    )

    warnings = list(projection["warnings"])
    age_days = (date.today() - as_of).days
    if age_days > 7:
        warnings.append(f"Cached candle is {age_days} calendar days old; result is stale.")
    if age_days < 0:
        warnings.append("Dataset contains future-dated candle(s); verify your clock and dates.")
    if market == "psx":
        warnings.append("PSX split checks do not cover every possible bonus issue, right, dividend, or data error.")

    return {
        "market": market,
        "symbol": symbol,
        "as_of": as_of.isoformat(),
        "currency": currency,
        "close": _float(close.iloc[-1]),
        "recommendation": signal,
        "technical": {
            "ma20": _float(last["ma20"]),
            "ma50": _float(last["ma50"]),
            "rsi14": _float(last["rsi14"]),
            "trend": trend,
        },
        "explanations": reasons,
        "scenario_alignment": alignment,
        "scenario_projections": projection,
        "historical_backtest": backtest,
        "warnings": warnings,
        "disclaimer": (
            "Learning-only FYP output. No orders are placed. Technical rules are "
            "not validated financial advice; historical simulations do not predict "
            "future prices. The in-sample backtest is not proof of profitability."
        ),
    }
