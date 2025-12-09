````markdown
# Simple Backtester

Small Python project to run basic stock backtests on daily data stored in a local SQLite database.

Supported strategies:

- **`buy_and_hold`** – buy once and hold for a fixed date range.  
- **`ma_crossover`** – long-only moving average crossover.  
- **`volatility_tp`** – enter after big daily moves, exit on take-profit / stop-loss.

---

## Project Layout

```text
.
├── main.py                  # Entry point: runs the chosen strategy
├── test_data.py             # Downloads data via yfinance into data/prices.db
├── src/
│   ├── backtester.py        # Strategies, performance metrics, plotting
│   └── data_loader.py       # Loads data from data/prices.db
└── data/
    └── prices.db            # SQLite database (created by test_data.py)
````

---

## Requirements

* Python **3.9+**
* Packages:

```bash
pip install -r requirements.txt
```

**Note:** If `pip` doesn't work, try `pip3` instead.

Or install manually:

```bash
pip install pandas matplotlib yfinance flask flask-cors
```

(Activate your virtualenv first if you use one.)

`sqlite3` is part of the standard library; no extra install needed.

### Frontend (Node.js)
* Node.js **16+** and npm
* Frontend dependencies are in `frontend/package.json` and will be installed automatically.

---

## Running the Application

This project consists of a Flask backend API server and a React frontend. Both need to be running simultaneously.

### Step 1: Start the Flask Backend Server

From the project root directory (`mth4370_group_project`):

```bash
python api_server.py
```

**Note:** If `python` doesn't work, try `python3` instead.

The server will start on `http://localhost:5001` and you should see:

```
🚀 Starting Flask API server...
📊 Available endpoints:
   - GET /api/health - Health check
   - GET /api/stocks - List available tickers
   - GET /api/stock/<ticker> - Get stock data
   - GET /api/stock/<ticker>?start=YYYY-MM-DD&end=YYYY-MM-DD - Get filtered data
   - POST /api/backtest - Run backtest (Buy & Hold strategy)
   - POST /api/backtest/compare - Run comparison backtest for multiple tickers

🌐 Server running on http://localhost:5001
```

**Keep this terminal window open** - the server needs to stay running.

### Step 2: Start the Frontend Development Server

Open a **new terminal window** and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies (only needed the first time):

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

You should see output like:

```
  VITE v7.2.4  ready in 92 ms
  ➜  Local:   http://localhost:5173/
```

### Step 3: Open the Application

Open your web browser and navigate to:

```
http://localhost:5173
```

The frontend will connect to the backend API automatically. You should see the Backtesting Engine Dashboard.

**Note:** Make sure both the Flask server (port 5001) and the frontend dev server (port 5173) are running at the same time.

---

## 1. Download Data

From the project root, run:

```bash
python test_data.py
```

This will:

* Show a list of default tickers and let you add more (or just press **Enter**).
* Download daily OHLCV data from Yahoo Finance.
* Store everything in `data/prices.db`.

Re-run this script whenever you want to **add** tickers or **refresh** data.

---

## 2. Configure the Backtest

The engine reads defaults from `STRATEGY_CONFIG` in `main.py`, and you can
override everything from the command line.

### 2.1 Defaults in `main.py`

```python
STRATEGY_CONFIG = {
    "ticker": "TSLA",              # primary ticker to summarize
    "buy_date": "2023-01-03",      # start date (YYYY-MM-DD)
    "holding_period_days": 220,    # length of window in calendar days
    "initial_capital": 10_000.0,
    "transaction_cost_pct": 0.001, # 0.1% costs per round trip / trade

    # Strategy: "buy_and_hold", "ma_crossover", or "volatility_tp"
    "strategy": "buy_and_hold",

    # Used only when strategy == "ma_crossover"
    "short_window": 20,
    "long_window": 50,

    # Used only when strategy == "volatility_tp"
    "vol_window": 20,          # reserved for future rolling-vol logic
    "vol_threshold": 0.05,     # |daily return| trigger, e.g. 0.05 = 5%
    "take_profit": 0.02,       # +2% vs entry
    "stop_loss": None,         # e.g. 0.03 = -3% vs entry
}

COMPARISON_TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
```

> Make sure every ticker in `COMPARISON_TICKERS` exists in `data/prices.db`
> (i.e., you downloaded it with `test_data.py`).

### 2.2 Command-line Options

You don’t have to edit the file for every run; you can override everything:

```bash
python main.py \
  --ticker TSLA \
  --buy-date 2023-01-03 \
  --holding-days 220 \
  --initial-capital 10000 \
  --transaction-cost-pct 0.001 \
  --strategy buy_and_hold \
  --comparison-tickers AAPL,MSFT,GOOGL,TSLA,AMZN
```

**Strategy choice:**

```bash
--strategy buy_and_hold        # default
--strategy ma_crossover
--strategy volatility_tp
```

**Extra flags per strategy:**

* `ma_crossover`:

  ```bash
  --short-window 20 \
  --long-window 50
  ```

  (Optional) MA grid search for the primary ticker:

  ```bash
  --strategy ma_crossover --ma-grid
  ```

* `volatility_tp`:

  ```bash
  --strategy volatility_tp \
  --vol-threshold 0.05 \
  --take-profit 0.02 \
  --stop-loss 0.03
  ```

  Meaning: enter after a daily move larger than 5% (up or down), take profit at +2%,
  stop out at –3%.

---

## 3. Run the Backtest

Simplest run (uses defaults from `main.py`):

```bash
python main.py
```

Custom examples:

```bash
# Buy & Hold MSFT for 1 year
python main.py \
  --strategy buy_and_hold \
  --ticker MSFT \
  --buy-date 2022-01-03 \
  --holding-days 252

# MA crossover on AAPL with custom windows
python main.py \
  --strategy ma_crossover \
  --ticker AAPL \
  --buy-date 2023-01-03 \
  --holding-days 220 \
  --short-window 10 \
  --long-window 50

# Volatility TP on TSLA with TP 2%, SL 3%
python main.py \
  --strategy volatility_tp \
  --ticker TSLA \
  --buy-date 2023-01-03 \
  --holding-days 220 \
  --vol-threshold 0.05 \
  --take-profit 0.02 \
  --stop-loss 0.03
```

---

## 4. Output

When you run `main.py`, you’ll get:

1. **Console summary for the primary ticker**

   * Buy / sell dates and prices
   * Approximate position size (shares)
   * Final portfolio value
   * PnL and percentage return

2. **Performance table across all comparison tickers**

   For each ticker:

   * Final value
   * Total return
   * Annualized return
   * Annualized volatility
   * Max drawdown & drawdown duration
   * A simple “Sharpe-like” metric = annualized return / annualized vol

   The table is sorted by the Sharpe-like metric (best at the top).

3. **Matplotlib overview figure**

   One window with two panels:

   * **Top:** Risk–return scatter (one point per ticker).
   * **Bottom:** Normalized equity curves (`portfolio_value / initial_capital`)
     for all tickers, plus vertical lines for the start and end dates.

   Close the plot window to return to the terminal.

---

## 5. Notes

* All strategies use **integer shares**; leftover cash stays idle in the portfolio.
* Prices are daily **close** prices from Yahoo Finance.
* If you see “No data available…” errors, make sure the ticker was downloaded
  into `data/prices.db` with `test_data.py` and that the date range overlaps
  the available data.

That’s everything you need to download data, configure a strategy, and run backtests with this project.
