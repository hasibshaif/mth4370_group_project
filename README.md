````markdown
# Simple Backtester

Small Python project to run basic backtests (Buy & Hold or Moving Average Crossover) on daily stock data stored in a local SQLite database.

---

## Project Layout

```text
.
├── main.py                  # Entry point: runs the configured strategy
├── test_data.py             # Downloads data with yfinance into data/prices.db
├── src/
│   ├── backtester.py        # Strategies, performance metrics, plots
│   └── data_loader.py       # Loads data from data/prices.db
└── data/
    └── prices.db            # SQLite database (created by test_data.py)
````

---

## Requirements

* Python **3.9+**
* Packages:

```bash
pip install pandas matplotlib yfinance
```

(Activate your virtualenv first if you use one.)

---

## 1. Download Data

From the project root, run:

```bash
python test_data.py
```

This will:

* Ask you for tickers (and use a default set if you just press Enter).
* Download daily OHLCV data from Yahoo Finance.
* Store everything in `data/prices.db`.

You only need to re-run this when you want to add/update tickers.

---

## 2. Configure the Backtest

Open `main.py` and edit:

```python
STRATEGY_CONFIG = {
    "ticker": "TSLA",            # primary ticker to summarize
    "buy_date": "2023-01-03",    # start date (YYYY-MM-DD)
    "holding_period_days": 220,  # length of window in calendar days
    "initial_capital": 10_000.0,
    "transaction_cost_pct": 0.001,   # 0.1% costs

    # "buy_and_hold" or "ma_crossover"
    "strategy": "buy_and_hold",

    # used only when strategy == "ma_crossover"
    "short_window": 20,
    "long_window": 50,
}

COMPARISON_TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
```

Make sure every ticker in `COMPARISON_TICKERS` exists in `data/prices.db`
(i.e., you downloaded it with `test_data.py`).

---

## 3. Run the Backtest

From the project root:

```bash
python main.py
```

What you’ll see:

* Text summary in the terminal for the **primary ticker** (PnL, return, etc.).
* A performance table across all tickers (final value, returns, vol, max drawdown).
* A single matplotlib window with:

  * Top: risk–return scatter (one point per ticker).
  * Bottom: normalized equity curves for all tickers.

Close the plot window to return to the terminal.

That’s it — those are the only steps needed to use the project.
