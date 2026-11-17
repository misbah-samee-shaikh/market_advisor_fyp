# FYP Market Advisor — Modular Version

A simple experimental **Forex + Crypto + PSX** market analysis bot.
It runs **one chosen asset** at a time, reuses locally cached candles, computes
technical indicators with VectorBT, simulates possible price ranges with NumPy,
and writes one JSON report. **No real-money trades and no frontend.**

## 1. Add files to your existing project

Extract the ZIP **into** your existing `C:\Users\HP\market-advisor-fyp\`
directory. Keep your existing `.venv/`, `data/`, and `reports/` directories;
the ZIP does not include or replace those. Your old Python scripts can remain
beside the new `bot.py` as an archive; none are imported by the modular bot.

```
market-advisor-fyp/
  bot.py                   <-- edit this file for your input
  markets/
    __init__.py
    crypto.py              <-- fetch BTC-USD or ETH-USD
    forex.py               <-- fetch EURUSD=X or GBPUSD=X
    psx.py                 <-- fetch LUCK, HBL, OGDC, etc.
  core/
    __init__.py
    data.py                <-- saved CSV and data-quality checks
    corporate_actions.py   <-- detect known splits, fix safely, back up
    indicators.py          <-- VectorBT MA / RSI
    signals.py             <-- BUY / SELL / WAIT rules
    backtest.py            <-- VectorBT historical simulation
    scenarios.py           <-- Monte Carlo-style historical bootstrap
    advisor.py             <-- explanations and combined result
    reports.py             <-- JSON export and console output
  data/                    <-- existing cached CSVs, unchanged
  reports/                 <-- single-asset JSON results
  .venv/                   <-- your existing Python environment
```

## 2. Edit the input in `bot.py`

```
MARKET = "crypto"
SYMBOL = "BTC-USD"
```

To analyze EUR/USD instead:

```
MARKET = "forex"
SYMBOL = "EURUSD=X"
```

To analyze Lucky Cement:

```
MARKET = "psx"
SYMBOL = "LUCK"
```

Supported `MARKET` values: `crypto`, `forex`, `psx`. Symbols depend on
provider coverage (Yahoo Finance for crypto/Forex, psxdata for PSX).

## 3. Run in Windows PowerShell

From `C:\Users\HP\market-advisor-fyp`:

```powershell
.\.venv\Scripts\python.exe bot.py
```

The bot only analyzes the chosen asset and produces, e.g.,
`reports/advisor_crypto_BTC-USD.json`.

If dependencies aren't installed in your `.venv`, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Offline caching behavior

If `data/crypto/BTC-USD.csv` exists, the bot uses that file **without connecting
to the internet**. Similarly, it reuses `data/forex/EURUSD_X.csv` and
`data/psx/LUCK.csv` from your earlier work.

If a new symbol has *no* cached CSV, the bot downloads its last ~2 years of
prices **once** and writes a CSV. To strictly forbid any network access, set:

```
DOWNLOAD_IF_MISSING = False
```

This version deliberately **does not auto-refresh existing datasets**.
Their last candle can therefore be stale. Add a separate, safely validated
refresh workflow later when needed—especially for PSX split-adjusted prices.

### Automatic PSX split correction (safe by default)

The bot checks PSX prices automatically when they are loaded. There is no
need to run `fyp_validation.py --fix-luck-split` again.

- **Known event**: LUCK's 5-for-1 split effective **2025-04-28** is built in
  with a link to the company's PSX disclosure. If the cache is raw, the bot
  divides all older OHLC prices by 5 and multiplies old volume by 5.
- **Already adjusted**: The code checks prices across the split and leaves
  the file alone if it is already adjusted. Running the bot repeatedly does
  not double-adjust the file.
- **Backup**: Before the first automatic correction, it saves a copy under
  `data/backups/psx/`. It writes a corrected cache only after passing checks.
- **Other shares**: A daily jump exceeding 35% is **flagged, not guessed**.
  It could be a genuine move, bad data, a bonus issue or another corporate
  action; the bot stops rather than silently giving invalid results.

To add another **verified** PSX split, copy `corporate_actions.example.json`
into `data/corporate_actions.json` and add an entry under its stock symbol:

```json
{
  "psx": {
    "LUCK": [{"date": "2025-04-28", "factor": 5, "source": "https://dps.psx.com.pk/download/document/257573.pdf"}],
    "NEWSTOCK": [{"date": "YYYY-MM-DD", "factor": 2, "source": "https://link-to-verified-PSX-notice"}]
  }
}
```

`factor` means **new shares for each old share**; `2` = 2-for-1 and
`0.2` = 1-for-5 reverse split. No internet lookup is performed for the
corporate-action registry: a newly discovered event requires confirmation
before auto-correction. Different corporate actions (dividends, rights,
bonus shares) are **not** automatically adjusted by this module.

The optional `pypsx` data provider advertises an adjusted historical series
and a corporate-actions feed but requires API credentials; we have not made
that a dependency of the free FYP bot.

## 5. What each module does

1. Market adapter downloads *only when missing*.
2. `core/data.py` loads and caches daily candles; `core/corporate_actions.py` checks PSX split safety before calculations.
3. `core/indicators.py` uses VectorBT to compute MA20, MA50 and RSI14.
4. `core/signals.py` labels each historical candle BUY/SELL/WAIT.
5. `core/backtest.py` uses VectorBT for a simplified long-only historical
   simulation with a one-bar signal delay, model fees and slippage.
6. `core/scenarios.py` resamples past returns in blocks and simulates the next
   7, 14 and 30 **market sessions**.
7. `core/advisor.py` combines the outputs; `core/reports.py` prints/saves JSON.

**SELL = exit/avoid a long position, not a short-selling recommendation.**
The backtest assumes execution using a future daily closing price (an
approximation). The scenario P10/P50/P90 values are simulated outcomes, not
validated predictions or probabilities of success. Earlier walk-forward
results showed weak/mixed generalization; don't present in-sample results as
predictive accuracy.

## 6. Optional outputs

By default `SAVE_BACKTEST_CHART = False`: no HTML chart is necessary for
running the bot. Set it to `True` in `bot.py` if you want an HTML backtest
visualization generated inside `reports/`.

## 7. How to change rules / methods

- Want different RSI thresholds? Edit only `core/signals.py`.
- Want different indicators? Edit only `core/indicators.py`.
- Want different forecasting methodology? Edit `core/scenarios.py`.
- Want to switch the PSX data provider? Edit only `markets/psx.py`.
- Want to add a fourth asset class? Add another module under `markets/`
  and register it in `bot.py`.

## 8. Existing scripts and validation

Your older `fyp_validation.py` and `walk_forward_validation.py` are separate
**evaluation** tools. They don't run as part of every user query. Keep them
for your FYP methodology, but update their configuration if you add symbols.

The sample rules have **not** demonstrated consistently reliable predictive
performance. This is an educational research prototype, not investment advice.
