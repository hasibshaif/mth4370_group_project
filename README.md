
## Project Structure

```text
.
├── main.py                  # Entry point: runs a single-trade buy & hold backtest
├── test_data.py             # Helper script to download/update CSV data via yfinance
├── src/
│   ├── backtester.py        # Backtester class: executes the buy & hold simulation
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

`src/data_loader.py` handles all the quirks of the CSV files:

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

the loader treats the first column as the date column (renames it to `date`) and uses `close` as the price.

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
     Ticker:              TSLA
     Buy date (request):  2023-01-03
     Sell date (request): 2023-01-17
     Holding period:      14 days
     Initial capital:     10000.00
   ```

2. Use `DataLoader` to load the chosen ticker’s historical prices from `data/raw/`.

3. Use `Backtester` to simulate a **buy & hold** strategy:

   * Buy as many whole shares as possible on the first trading day **on or after** the requested buy date.
   * Hold these shares until the requested sell date / holding period.
   * Keep leftover cash uninvested.

4. Compute and store:

   * `shares` held over time
   * `cash` balance
   * `price` (from the `close` column)
   * `portfolio_value = shares * price + cash`
   * `returns_factor = portfolio_value / initial_capital`

5. Print a basic performance summary and plot the **equity curve** over time.

---

## Customizing the Strategy Configuration

Inside `main.py`, there is a configuration section that defines the trade:

* **ticker** (e.g. `"TSLA"`)
* **buy_date** (e.g. `"2023-01-03"`)
* **holding_period_days** (e.g. `14`)
* **initial_capital** (e.g. `10000.0`)

To run a different scenario:

1. Open `main.py`.
2. Locate the section where these values are set (near the top of `main()`).
3. Change the values to match the ticker and dates you want to test.
4. Make sure you have a corresponding CSV in `data/raw/` (e.g. `data/raw/TSLA.csv`).
5. Run:

   ```bash
   python main.py
   ```

---

## Notes & Limitations

* This engine is **single-asset, single-trade**:

  * No multiple overlapping trades.
  * No portfolio of many tickers at once.
* Execution assumptions are very simple:

  * No transaction costs, slippage, or bid/ask spread modeling.
  * Filled at the daily close price.
* It is intended for **teaching and experimentation**, not for production trading.

---
