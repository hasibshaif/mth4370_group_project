````markdown
## Project Structure

```text
.
├── main.py                  # Entry point: runs buy & hold backtests (and comparison plot)
├── test_data.py             # Helper script to download/update CSV data via yfinance
├── src/
│   ├── backtester.py        # Backtester class: executes the buy & hold simulations + plots
│   ├── data_loader.py       # DataLoader: reads & normalizes CSV price data
│   └── data_acquisition.py  # (Optional) YahooFinanceDataFetcher utilities
└── data/
    └── raw/                 # Folder where per-ticker CSV files are stored
````

---

## Requirements

* Python **3.9+** (3.10/3.11 also fine)
* Recommended packages:

  * `pandas`
  * `matplotlib`
  * `yfinance`

You can install them with:

```bash
pip install pandas matplotlib yfinance
```

(If you are using a virtual environment, activate it first.)

---

## Getting Data

Before running a backtest, you need historical price data saved as CSV files in `data/raw/`.

This repo provides a helper script, `test_data.py`, which uses **yfinance**:

```bash
python test_data.py
```

What it does:

1. Automatically includes a small set of core tickers (by default: `AAPL`, `MSFT`, `GOOGL`, `TSLA`).
2. Asks you if you want to add extra tickers (comma-separated).
3. Downloads daily OHLCV data from Yahoo Finance.
4. Saves one CSV per ticker under `data/raw/` (e.g. `data/raw/TSLA.csv`).

Once this is done, your `data/raw/` folder will contain files like:

```text
data/raw/AAPL.csv
data/raw/MSFT.csv
data/raw/GOOGL.csv
data/raw/TSLA.csv
...
```

---

## How the Data Loader Works

`src/data_loader.py` handles the quirks of the CSV files:

* Reads each CSV **once** and caches it in memory (for speed).
* Detects whether the first row is a header.
* Normalizes column names to **lowercase**.
* Tries to build a `DatetimeIndex` from a `date`-like column.
* Ensures the DataFrame has:

  * a `date` column (for plotting)
  * a numeric `close` column (used as the price series)

For files with columns like:

```text
Price, Close, High, Low, Open, Volume
```

the loader:

* Treats the first column as the date column (renames it to `date`), and
* Uses `close` as the price series.

If needed, it falls back to other columns (like `adj close` or `price`) to create a consistent `close` field.

---

## Running a Single-Trade Backtest

Once data is available, you can run the main script:

```bash
python main.py
```

This will:

1. Print the configured trade parameters, e.g.:

   ```text
   [main] Starting single-trade backtest using Backtester...
     Primary ticker:      TSLA
     Buy date (request):  2023-01-03
     Sell date (request): 2023-01-17
     Holding period:      14 days
     Initial capital:     10000.00
     Comparison tickers:  TSLA, AAPL, MSFT, GOOGL
   ```

2. Use `DataLoader` to load each chosen ticker’s historical prices from `data/raw/`.

3. Use `Backtester` to simulate a **buy & hold** strategy for each ticker:

   * Buy as many whole shares as possible on the first trading day **on or after** the requested buy date.
   * Hold these shares until the requested sell date / holding period.
   * Keep leftover cash uninvested.

4. For each ticker, compute and store:

   * `shares` held over time
   * `cash` balance
   * `price` (from the `close` column)
   * `portfolio_value = shares * price + cash`
   * `returns_factor = portfolio_value / initial_capital` (normalized equity curve)

5. Compute a **performance summary** (per ticker), including for example:

   * Final portfolio value
   * Total return
   * Approximate annualized return
   * Approximate annualized volatility of daily returns
   * Max drawdown
   * Max drawdown duration (in days)

6. Print a detailed summary in the terminal for the **primary ticker** (e.g. TSLA), and basic stats for each ticker as the backtests run.

---

## Multi-Ticker Comparison Plot

By default, `main.py` defines:

```python
STRATEGY_CONFIG = {
    "ticker": "TSLA",
    "buy_date": "2023-01-03",
    "holding_period_days": 14,
    "initial_capital": 10_000.0,
}

COMPARISON_TICKERS = ["TSLA", "AAPL", "MSFT", "GOOGL"]
```

When you run:

```bash
python main.py
```

the engine will:

1. Run the same buy & hold trade (same buy and sell dates, same initial capital) **for each ticker** listed in `COMPARISON_TICKERS`.
2. Store the results for each ticker in a dictionary.
3. Call `Backtester.plot_comparison(...)` to plot **all normalized equity curves on the same chart**, so you can visually compare which stock performed better over that period.

Each curve starts at 1.0 on the buy date (via `returns_factor`), making the relative performance easy to see.

---

## Customizing the Strategy Configuration

Inside `main.py`, there is a configuration section that defines the trade and which tickers to compare:

* **ticker** (e.g. `"TSLA"`) – the primary ticker for the printed summary
* **buy_date** (e.g. `"2023-01-03"`)
* **holding_period_days** (e.g. `14`)
* **initial_capital** (e.g. `10000.0`)
* **COMPARISON_TICKERS** (e.g. `["TSLA", "AAPL", "MSFT", "GOOGL"]`)

To run a different scenario:

1. Open `main.py`.
2. Locate `STRATEGY_CONFIG` and `COMPARISON_TICKERS`.
3. Change the values to match:

   * the primary ticker,
   * the buy date,
   * the holding period,
   * the tickers you want to compare.
4. Make sure you have corresponding CSVs in `data/raw/` (e.g. `data/raw/NVDA.csv` if you add `"NVDA"`).
5. Run:

   ```bash
   python main.py
   ```

---

## Notes & Limitations

* This engine is **per-ticker, single-trade**:

  * For each ticker, it simulates one buy & hold trade over the chosen date range.
  * It does **not** yet model multiple overlapping trades or complex strategies.
* The multi-ticker comparison:

  * Treats each ticker separately with its own $X initial capital.
  * The comparison chart is **not** a multi-asset portfolio; it is a side-by-side comparison of separate trades.
* Execution assumptions are very simple:

  * No transaction costs, slippage, or bid/ask spread modeling.
  * Orders are filled at the daily close price.
* It is intended for **teaching and experimentation**, not for production trading.

---