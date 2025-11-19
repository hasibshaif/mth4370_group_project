import math
from datetime import timedelta
from pathlib import Path
import traceback

import matplotlib.pyplot as plt
import pandas as pd


# ---------- Data loading ----------


def load_price_data(ticker: str) -> pd.DataFrame:
    """
    Load daily price data for a given ticker from data/raw/{TICKER}.csv.

    Handles two formats:

    1) Normal CSV with a 'Date' column in the header:
         Date,Open,High,Low,Close,...
         2015-01-02,...

    2) Your custom format:
         Price,Close,High,Low,Open,Volume
         Ticker,TSLA,TSLA,TSLA,TSLA,TSLA
         Date,,,,,
         2015-01-02,14.62,...,Volume
         ...

       In this case we:
         - skip the first 3 lines
         - parse col 0 as date
         - parse col 1 as close price
    """
    data_path = Path("data/raw") / f"{ticker.upper()}.csv"
    print(f"[load_price_data] Looking for file: {data_path}")

    if not data_path.exists():
        raise FileNotFoundError(
            f"{data_path} not found. Make sure the CSV exists in data/raw."
        )

    # Read raw lines so we can decide how to parse
    with data_path.open("r") as f:
        lines = f.read().splitlines()

    if not lines:
        raise ValueError("CSV file is empty.")

    first_line = lines[0]
    print(f"[load_price_data] First line: {first_line}")

    # ---------- CASE 1: Normal CSV with 'Date' header ----------
    # e.g. "Date,Open,High,Low,Close,Adj Close,Volume"
    if first_line.lower().startswith("date,"):
        print("[load_price_data] Detected normal 'Date'-header CSV, using pandas parser.")
        df = pd.read_csv(data_path)
        df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)

        if "date" not in df.columns or "close" not in df.columns:
            raise ValueError("Expected 'date' and 'close' columns in the CSV file.")

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df.set_index("date", inplace=True)

        print(
            f"[load_price_data] Final index range: {df.index.min()} -> {df.index.max()}"
        )
        return df

    # ---------- CASE 2: Custom format like you pasted ----------
    print("[load_price_data] Using custom manual parser (Price/Close/... + Date row).")

    if len(lines) <= 3:
        raise ValueError(
            "Custom-format CSV has too few lines. Expected at least 4 lines."
        )

    # Expect:
    # line 0: "Price,Close,High,Low,Open,Volume"
    # line 1: "Ticker,..."
    # line 2: "Date,,,,,"
    # line 3+: "YYYY-MM-DD,<close>,..."
    header_line = lines[2].split(",")[0].strip().upper()
    if header_line != "DATE":
        raise ValueError(
            f"Expected 'Date' on line 3 (index 2), but found '{lines[2]}'"
        )

    data_lines = lines[3:]
    print(f"[load_price_data] Number of data lines after header: {len(data_lines)}")

    dates = []
    closes = []

    for ln in data_lines:
        if not ln.strip():
            continue  # skip empty lines

        parts = ln.split(",")
        if len(parts) < 2:
            continue  # need at least date + close

        date_str = parts[0].strip()
        close_str = parts[1].strip()

        if not date_str or not close_str:
            continue

        try:
            date = pd.to_datetime(date_str)
            close_val = float(close_str)
        except Exception:
            # If parsing fails, skip this line
            continue

        dates.append(date)
        closes.append(close_val)

    if not dates:
        raise ValueError(
            "After parsing custom format, no valid (date, close) rows were found. "
            "Check that column 0 has dates and column 1 has numeric prices."
        )

    df = pd.DataFrame({"close": closes}, index=pd.to_datetime(dates))
    df.sort_index(inplace=True)

    print(
        f"[load_price_data] Parsed {len(df)} rows. "
        f"Index range: {df.index.min()} -> {df.index.max()}"
    )

    return df




# ---------- Strategy config ----------

STRATEGY_CONFIG = {
    "ticker": "TSLA",
    "buy_date": "2023-01-03",       # string in YYYY-MM-DD format
    "holding_period_days": 14,      # 2 weeks
    "initial_capital": 10_000.0,
}


# ---------- Single-trade backtest ----------


def find_next_trading_day(df: pd.DataFrame, target_date: pd.Timestamp) -> pd.Timestamp:
    """
    Return the first trading date in df.index that is >= target_date.
    """
    dates = df.index
    mask = dates >= target_date
    if not mask.any():
        raise ValueError(f"No trading days on or after {target_date.date()}")
    return dates[mask][0]


def run_single_trade_backtest(cfg: dict) -> dict:
    """
    Buy on a given date (or next trading day), hold for N calendar days,
    then sell on the first trading day on/after that sell date.
    """
    print("[run_single_trade_backtest] Starting backtest with config:", cfg)

    ticker = cfg["ticker"]
    initial_capital = cfg["initial_capital"]
    holding_days = cfg["holding_period_days"]

    df = load_price_data(ticker)

    # Parse buy date and find actual trading buy date
    buy_date_raw = pd.to_datetime(cfg["buy_date"])
    print(f"[run_single_trade_backtest] Raw buy date: {buy_date_raw}")

    buy_date = find_next_trading_day(df, buy_date_raw)
    print(f"[run_single_trade_backtest] Actual buy date (trading day): {buy_date}")

    # Compute target sell date and actual trading sell date
    target_sell_date = buy_date + timedelta(days=holding_days)
    print(f"[run_single_trade_backtest] Target sell date: {target_sell_date}")

    sell_date = find_next_trading_day(df, target_sell_date)
    print(f"[run_single_trade_backtest] Actual sell date (trading day): {sell_date}")

    buy_price = df.loc[buy_date, "close"]
    sell_price = df.loc[sell_date, "close"]
    print(f"[run_single_trade_backtest] Buy price: {buy_price}, Sell price: {sell_price}")

    # Compute position: all-in
    shares = math.floor(initial_capital / buy_price)
    if shares == 0:
        raise ValueError("Initial capital is too small to buy even 1 share.")

    cash_after_buy = initial_capital - shares * buy_price
    cash_final = cash_after_buy + shares * sell_price

    pnl = cash_final - initial_capital
    return_pct = pnl / initial_capital

    # Build equity curve (portfolio value over time)
    equity = pd.Series(index=df.index, dtype="float64")

    # Before buy: just holding initial cash
    equity.loc[:buy_date] = initial_capital

    # Between buy and sell: cash_after_buy + shares * price(t)
    between_mask = (df.index > buy_date) & (df.index <= sell_date)
    equity.loc[between_mask] = cash_after_buy + shares * df.loc[between_mask, "close"]

    # After sell: flat at final cash
    after_mask = df.index > sell_date
    equity.loc[after_mask] = cash_final

    results = {
        "ticker": ticker,
        "buy_date": buy_date,
        "sell_date": sell_date,
        "buy_price": float(buy_price),
        "sell_price": float(sell_price),
        "shares": shares,
        "initial_capital": initial_capital,
        "final_capital": float(cash_final),
        "pnl": float(pnl),
        "return_pct": float(return_pct),
        "equity_curve": equity,
    }

    print("[run_single_trade_backtest] Finished backtest.")
    return results


# ---------- Plotting & reporting ----------


def plot_results(results: dict):
    equity = results["equity_curve"]
    buy_date = results["buy_date"]
    sell_date = results["sell_date"]

    print("[plot_results] Creating plot...")

    fig, ax = plt.subplots(figsize=(10, 5))

    # Plot equity curve
    ax.plot(equity.index, equity.values, label="Portfolio value")

    # Mark buy and sell points
    ax.scatter(buy_date, equity.loc[buy_date], marker="^", s=100, label="Buy", zorder=5)
    ax.scatter(
        sell_date, equity.loc[sell_date], marker="v", s=100, label="Sell", zorder=5
    )

    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio value ($)")
    ax.set_title(f"Single Trade Backtest: {results['ticker']}")
    ax.legend()
    plt.tight_layout()

    # Save to file in case the GUI doesn't show
    out_path = Path("backtest_output.png")
    plt.savefig(out_path)
    print(f"[plot_results] Saved plot to {out_path.resolve()}")

    # Also try to show interactively
    plt.show()
    print("[plot_results] Plot show() returned.")


def main():
    print("[main] Starting single-trade backtest...")
    cfg = STRATEGY_CONFIG
    results = run_single_trade_backtest(cfg)

    # Console summary
    print("\n=== Single Trade Backtest ===")
    print(f"Ticker:          {results['ticker']}")
    print(f"Buy date:        {results['buy_date'].date()} @ {results['buy_price']:.2f}")
    print(f"Sell date:       {results['sell_date'].date()} @ {results['sell_price']:.2f}")
    print(f"Shares:          {results['shares']}")
    print(f"Initial capital: {results['initial_capital']:.2f}")
    print(f"Final capital:   {results['final_capital']:.2f}")
    print(f"PnL:             {results['pnl']:.2f}")
    print(f"Return:          {results['return_pct'] * 100:.2f}%")

    plot_results(results)
    print("[main] Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR] An exception occurred while running main():")
        print(e)
        print("\nFull traceback:")
        traceback.print_exc()
