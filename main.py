"""
Main entry point for the simple single-trade backtest.

What this does (end-to-end):

1. Read a strategy config:
   - ticker (e.g. "TSLA")
   - buy_date
   - holding_period_days
   - initial_capital

2. Use `DataLoader` to read historical prices for that ticker from CSV.

3. Use `Backtester` to run a Buy & Hold strategy:
   - Buy on the first trading day >= buy_date
   - Hold until (buy_date + holding_period_days)
   - Use integer shares and leave leftover cash uninvested.

4. Print a summary:
   - entry/exit prices
   - shares
   - PnL
   - return %

5. Plot the equity curve with buy/sell markers.
"""

from datetime import datetime, timedelta
import traceback
import pandas as pd

# Flexible imports so it works whether modules live in `src/` or alongside main.py
try:  # pragma: no cover - import flexibility helper
    from src.data_loader import DataLoader
    from src.backtester import Backtester
except ImportError:  # pragma: no cover
    from data_loader import DataLoader
    from backtester import Backtester


# Strategy configuration
# ----------------------------------------------------------------------
STRATEGY_CONFIG = {
    "ticker": "TSLA",
    "buy_date": "2023-01-03",       # YYYY-MM-DD
    "holding_period_days": 14,      # calendar days
    "initial_capital": 10_000.0,    # dollars
}

# Tickers to compare on the same buy/sell dates
COMPARISON_TICKERS = ["TSLA", "AAPL", "MSFT", "GOOGL"]


def main() -> None:
    print("[main] Starting single-trade backtest using Backtester...")

    cfg = STRATEGY_CONFIG
    ticker = cfg["ticker"]
    buy_date_str = cfg["buy_date"]
    holding_period_days = cfg["holding_period_days"]
    initial_capital = cfg["initial_capital"]

    # Compute sell date in calendar days
    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
    sell_date = buy_date + timedelta(days=holding_period_days)
    sell_date_str = sell_date.strftime("%Y-%m-%d")

    print(f"  Primary ticker:      {ticker}")
    print(f"  Buy date (request):  {buy_date_str}")
    print(f"  Sell date (request): {sell_date_str}")
    print(f"  Holding period:      {holding_period_days} days")
    print(f"  Initial capital:     {initial_capital:.2f}")
    print("  Comparison tickers:  " + ", ".join(COMPARISON_TICKERS))

    # Initialize loader and backtester
    # Make sure your CSVs live under `data/raw/{TICKER}.csv`
    loader = DataLoader(data_dir="data/raw")
    backtester = Backtester(loader)

    # Run the Buy & Hold simulation for each comparison ticker
    results_by_ticker: dict[str, pd.DataFrame] = {}

    for comp_ticker in COMPARISON_TICKERS:
        print(f"\n[main] Running Buy & Hold for {comp_ticker}...")
        df_comp = backtester.run_buy_and_hold(
            ticker=comp_ticker,
            start=buy_date_str,
            end=sell_date_str,
            initial_capital=initial_capital,
        )
        results_by_ticker[comp_ticker] = df_comp

    # Use the primary ticker's DataFrame for the text summary
    df_main = results_by_ticker[ticker]

    # Extract summary stats for the primary ticker
    buy_price = df_main["price"].iloc[0]
    sell_price = df_main["price"].iloc[-1]
    shares = df_main["shares"].iloc[0]
    final_value = df_main["portfolio_value"].iloc[-1]
    pnl = final_value - initial_capital
    ret_pct = pnl / initial_capital

    print("\n=== Single-Trade Backtest Summary (Primary Ticker) ===")
    print(f"Ticker:           {ticker}")
    print(f"Buy date:         {buy_date_str} @ {buy_price:.2f}")
    print(f"Sell date:        {sell_date_str} @ {sell_price:.2f}")
    print(f"Shares (integer): {shares}")
    print(f"Initial capital:  {initial_capital:.2f}")
    print(f"Final value:      {final_value:.2f}")
    print(f"PnL:              {pnl:.2f}")
    print(f"Return:           {ret_pct*100:.2f}%")

    # Plot comparison of all tickers on the same chart
    backtester.plot_comparison(results_by_ticker)

    print("[main] Backtest complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR] An exception occurred while running main():")
        print(e)
        print("\nFull traceback:")
        traceback.print_exc()
