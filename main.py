"""
Main entry point for the simple single-trade backtest.

What this does (end-to-end):

1. Read a strategy config:
   - ticker (e.g. "TSLA")
   - buy_date
   - holding_period_days
   - initial_capital
   - transaction_cost_pct (NEW: round-trip cost on initial capital)

2. Use `DataLoader` to read historical prices for that ticker from the DB.

3. Use `Backtester` to run a Buy & Hold strategy:
   - Buy on the first trading day >= buy_date
   - Hold until (buy_date + holding_period_days)
   - Use integer shares and leave leftover cash uninvested.

4. Print a summary:
   - entry/exit prices
   - shares
   - PnL
   - return %

5. Plot the equity curve with buy/sell markers and compare multiple tickers.
"""

from datetime import datetime, timedelta
import traceback
import pandas as pd  # <-- needed for type hints (pd.DataFrame)


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
    "holding_period_days": 220,     # calendar days for the test window
    "initial_capital": 10_000.0,    # dollars

    # Round-trip transaction cost as a percentage of initial capital
    # (for Buy & Hold) or per-trade fee (for MA crossover).
    "transaction_cost_pct": 0.001,

    # NEW: which strategy to run: "buy_and_hold" or "ma_crossover"
    "strategy": "buy_and_hold",

    # NEW: parameters for the moving average crossover strategy
    "short_window": 20,
    "long_window": 50,
}


# Tickers to compare on the same buy/sell dates
# COMPARISON_TICKERS = [
#     "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "JPM", "V", "DIS",
#     "NFLX", "PYPL", "ADBE", "INTC", "CSCO", "CMCSA", "PEP", "COST", "TM",
#     "NKE", "SBUX", "BA", "WMT", "T", "XOM", "CVX"
# ]
COMPARISON_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]


def main() -> None:
    print("[main] Starting single-trade backtest using Backtester...")

    cfg = STRATEGY_CONFIG
    ticker = cfg["ticker"]
    buy_date_str = cfg["buy_date"]
    holding_period_days = cfg["holding_period_days"]
    initial_capital = cfg["initial_capital"]
    transaction_cost_pct = cfg.get("transaction_cost_pct", 0.0)

    # NEW: strategy + MA windows
    strategy = cfg.get("strategy", "buy_and_hold")
    short_window = cfg.get("short_window", 20)
    long_window = cfg.get("long_window", 50)


    # Compute sell date in calendar days
    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
    sell_date = buy_date + timedelta(days=holding_period_days)
    sell_date_str = sell_date.strftime("%Y-%m-%d")

    print(f"  Primary ticker:      {ticker}")
    print(f"  Strategy:            {strategy}")
    print(f"  Buy date (request):  {buy_date_str}")
    print(f"  Sell date (request): {sell_date_str}")
    print(f"  Holding period:      {holding_period_days} days")
    print(f"  Initial capital:     {initial_capital:.2f}")
    print(f"  Transaction cost:    {transaction_cost_pct * 100:.3f}%")
    if strategy == "ma_crossover":
        print(f"  MA windows:          short={short_window}, long={long_window}")
    print("  Comparison tickers:  " + ", ".join(COMPARISON_TICKERS))


    # Initialize DataLoader (now backed by SQLite DB) and Backtester
    data_loader = DataLoader(db_path="data/prices.db")
    backtester = Backtester(data_loader=data_loader)

    # Run the Buy & Hold simulation for each comparison ticker
    results_by_ticker: dict[str, pd.DataFrame] = {}

    for comp_ticker in COMPARISON_TICKERS:
        if strategy == "buy_and_hold":
            print(f"\n[main] Running Buy & Hold for {comp_ticker}...")
            df_comp = backtester.run_buy_and_hold(
                ticker=comp_ticker,
                start=buy_date_str,
                end=sell_date_str,
                initial_capital=initial_capital,
                transaction_cost_pct=transaction_cost_pct,
            )
        elif strategy == "ma_crossover":
            print(f"\n[main] Running MA Crossover for {comp_ticker}...")
            df_comp = backtester.run_ma_crossover(
                ticker=comp_ticker,
                start=buy_date_str,
                end=sell_date_str,
                initial_capital=initial_capital,
                short_window=short_window,
                long_window=long_window,
                transaction_cost_pct=transaction_cost_pct,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        results_by_ticker[comp_ticker] = df_comp


    # Use the primary ticker's DataFrame for the text summary
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
    print(f"Shares (integerrun_buy_and_hold(): {shares}")
    print(f"Initial capital:  {initial_capital:.2f}")
    print(f"Transaction cost: {transaction_cost_pct * 100:.3f}% (round-trip)")
    print(f"Final value:      {final_value:.2f}")
    print(f"PnL:              {pnl:.2f}")
    print(f"Return:           {ret_pct*100:.2f}%")

    # ------------------------------------------------------------------
    # Performance summary table across all tickers (terminal only)
    # ------------------------------------------------------------------
    summary_rows: list[dict] = []

    for tkr, df in results_by_ticker.items():
        stats = backtester.summarize_performance(df, initial_capital=initial_capital)
        stats["ticker"] = tkr
        summary_rows.append(stats)

    summary_df = pd.DataFrame(summary_rows).set_index("ticker")

    # Reorder columns for nicer display
    cols = [
        "final_value",
        "total_return",
        "annualized_return",
        "annualized_vol",
        "max_drawdown",
        "max_drawdown_duration_days",
    ]
    summary_df = summary_df[cols]

    # Print a clean table to the terminal
    print("\n=== Performance Summary Across Tickers ===")
    # Format % columns as percents, others as numbers
    def fmt(x: float) -> str:
        return f"{x:,.4f}"

    print(summary_df.to_string(float_format=fmt))

    # Plot comparison of all tickers on the same chart
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
