"""Present one selected asset and export a JSON result for later app integration."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"


def save_report(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_symbol = re.sub(r"[^A-Za-z0-9._-]", "_", report["symbol"])
    output = REPORTS_DIR / f"advisor_{report['market']}_{safe_symbol}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
                      encoding="utf-8")
    return output


def print_report(report: dict, path: Path) -> None:
    print("\n" + "=" * 65)
    print(f"{report['market'].upper()} | {report['symbol']} | {report['as_of']}")
    print(f"Last close: {report['close']:,.4f} {report['currency']}")
    print(f"Experimental recommendation: {report['recommendation']}")
    tech = report["technical"]
    print(f"Indicators: MA20={tech['ma20']} | MA50={tech['ma50']} | RSI14={tech['rsi14']}")
    print("Why:")
    for reason in report["explanations"]:
        print("  - " + reason)
    print("\nFuture sessions | Bearish P10 | Median P50 | Bullish P90 | Simulated above start")
    for row in report["scenario_projections"]["scenarios"]:
        print(f"  {row['sessions']:>2} sessions  | {row['bearish_p10']:>11,.4f} | "
              f"{row['median_p50']:>10,.4f} | {row['bullish_p90']:>11,.4f} | "
              f"{row['simulated_above_start_pct']:>6.2f}%")
    bt = report["historical_backtest"]
    print(f"\nIn-sample backtest: {bt['total_return_pct']}% | "
          f"Trades: {bt['trades']} | Max drawdown: {bt['max_drawdown_pct']}%")
    for warning in report["warnings"]:
        print("[CAUTION] " + warning)
    print(f"\nJSON saved: {path.relative_to(ROOT)}")
    print("Research-only simulations; no actual trades were placed.")
