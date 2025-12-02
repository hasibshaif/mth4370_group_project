"""
Main entry point for the simple single-trade backtest.

What this does (end-to-end):

1. Read a strategy config:
   - ticker (e.g. "TSLA")
   - buy_date
   - holding_period_days
   - initial_capital

2. Use `DataLoader` to read historical prices for that ticker from the DB (data/prices.db).

3. Use `Backtester` to run a Buy & Hold strategy:
   - Buy on the first trading day >= buy_date
   - Hold until (buy_date + holding_period_days)
   - Use integer shares and leave leftover cash uninvested.

4. Print a summary:
   - entry/exit prices
   - shares
   - PnL
   - return %

5. Plot the equity curve with buy/sell markers and a comparison chart.

NEW:
- You can override ticker, buy date, holding period, initial capital, and comparison tickers
  from the command line.
- You also get a small sorted summary table for all comparison tickers.
"""

from datetime import datetime, timedelta
import argparse
import traceback

import pandas as pd

# Flexible imports so it works whether modules live in `src/` or alongside main.py
try:  # pragma: no cover - import flexibility helper
    from src.data_loader import DataLoader
    from src.backtester import Backtester
except ImportError:  # pragma: no cover
    from data_loader import DataLoader
    from backtester import Backtester


# Default strategy configuration (used if no CLI args are provided)
# ----------------------------------------------------------------------
STRATEGY_CONFIG = {
    "ticker": "TSLA",
    "buy_date": "2023-01-03",       # YYYY-MM-DD
    "holding_period_days": 14,      # calendar days
    "initial_capital": 10_000.0,    # dollars
}

# Default tickers to compare on the same buy/sell dates
COMPARISON_TICKERS = ["TSLA", "AAPL", "MSFT", "GOOGL"]


def parse_args() -> argparse.Namespace:
    """
    Parse optional CLI arguments so you can override the strategy without
    editing the file every time.

    Examples:
      python main.py --ticker NVDA --buy-date 2024-01-02 --holding-days 30 \
                     --initial-capital 5000 --compare NVDA AAPL MSFT
    """
    parser = argparse.ArgumentParser(
        description="Single-trade buy & hold backtest with multi-ticker comparison."
    )

    parser.add_argument(
        "--ticker",
        type=str,
        default=STRATEGY_CONFIG["ticker"],
        help=f"Primary ticker (default: {STRATEGY_CONFIG['ticker']})",
    )
    parser.add_argument(
        "--buy-date",
        type=str,
        default=STRATEGY_CONFIG["buy_date"],
        help=f"Buy date YYYY-MM-DD (default: {STRATEGY_CONFIG['buy_date']})",
    )
    parser.add_argument(
        "--holding-days",
        type=int,
        default=STRATEGY_CONFIG["holding_period_days"],
        help=f"Holding period in calendar days (default: {STRATEGY_CONFIG['holding_period_days']})",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=STRATEGY_CONFIG["initial_capital"],
        help=f"Initial capital (default: {STRATEGY_CONFIG['initial_capital']})",
    )
    parser.add_argument(
        "--compare",
        nargs="*",
        default=COMPARISON_TICKERS,
        help=(
            "Space-separated list of tickers to compare. "
            'Example: --compare TSLA AAPL MSFT GOOGL (default: TSLA AAPL MSFT GOOGL)'
        ),
    )

    return parser.parse_args()


def main() -> None:
    print("[main] Starting single-trade backtest using Backtester...")

    # Read CLI args (with sensible defaults)
    args = parse_args()

    ticker = args.ticker
    buy_date_str = args.buy_date
    holding_period_days = args.holding_days
    initial_capital = args.initial_capital
    comparison_tickers = args.compare or []

    # Make sure the primary ticker is in the comparison list
    if ticker not in comparison_tickers:
        comparison_tickers = [ticker] + comparison_tickers

    # Compute sell date in calendar days
    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
    sell_date = buy_date + timedelta(days=holding_period_days)
    sell_date_str = sell_date.strftime("%Y-%m-%d")

    print(f"  Primary ticker:      {ticker}")
    print(f"  Buy date (request):  {buy_date_str}")
    print(f"  Sell date (request): {sell_date_str}")
    print(f"  Holding period:      {holding_period_days} days")
    print(f"  Initial capital:     {initial_capital:.2f}")
    print("  Comparison tickers:  " + ", ".join(comparison_tickers))

    # Initialize DataLoader and Backtester
    # If you're still using CSVs instead of a DB, change this to DataLoader(csv_dir="data/raw")
    data_loader = DataLoader(db_path="data/prices.db")
    backtester = Backtester(data_loader=data_loader)

    # Run the Buy & Hold simulation for each comparison ticker
    results_by_ticker: dict[str, pd.DataFrame] = {}

    for comp_ticker in comparison_tickers:
        print(f"\n[main] Running Buy & Hold for {comp_ticker}...")
        df_comp = backtester.run_buy_and_hold(
            ticker=comp_ticker,
            start=buy_date_str,
            end=sell_date_str,
            initial_capital=initial_capital,
        )
        results_by_ticker[comp_ticker] = df_comp

    # Use the primary ticker's DataFrame for the detailed text summary
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

    # --- NEW: compact performance table for all comparison tickers ---
    print("\n=== Comparison Summary (All Tickers) ===")
    summary_rows = []
    for sym, df in results_by_ticker.items():
        final_val = df["portfolio_value"].iloc[-1]
        pnl_sym = final_val - initial_capital
        ret_sym = pnl_sym / initial_capital
        summary_rows.append(
            {
                "ticker": sym,
                "final_value": final_val,
                "pnl": pnl_sym,
                "return_pct": ret_sym * 100.0,
            }
        )

    summary_df = pd.DataFrame(summary_rows).sort_values(
        by="return_pct", ascending=False
    )

    # Pretty print without scientific notation
    with pd.option_context("display.float_format", "{:,.2f}".format):
        print(summary_df.to_string(index=False))

    # Plot comparison of all tickers on the same chart (normalized equity curves)
    backtester.plot_comparison(results_by_ticker)

    print("\n[main] Backtest complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR] An exception occurred while running main():")
        print(e)
        print("\nFull traceback:")
        traceback.print_exc()
