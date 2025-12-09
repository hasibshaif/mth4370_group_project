"""
Main entry point for the single-trade backtest engine.

What this does (end-to-end):

1. Read a strategy config:
   - ticker (e.g. "TSLA")
   - buy_date
   - holding_period_days
   - initial_capital
   - transaction_cost_pct
   - strategy ("buy_and_hold", "ma_crossover", or "volatility_tp")

2. Use `DataLoader` to read historical prices for that ticker from the DB.

3. Use `Backtester` to run the chosen strategy via `run_strategy`:
   - Buy & Hold
   - Moving Average Crossover
   - Volatility Take-Profit

4. Print a summary for the primary ticker:
   - entry/exit prices
   - approximate position size (shares)
   - PnL
   - return %

5. Print a performance table for all tickers and plot:
   - risk–return scatter
   - normalized equity curves comparison.
"""

from datetime import datetime, timedelta
import argparse

import matplotlib.pyplot as plt
import pandas as pd

# Flexible imports so it works whether modules live in `src/` or alongside main.py
try:  # pragma: no cover - import flexibility helper
    from src.data_loader import DataLoader
    from src.backtester import Backtester
except ImportError:  # pragma: no cover
    from data_loader import DataLoader
    from backtester import Backtester


# Strategy configuration (defaults, can be overridden by CLI)
# ----------------------------------------------------------------------
STRATEGY_CONFIG = {
    "ticker": "TSLA",
    "buy_date": "2023-01-03",       # YYYY-MM-DD
    "holding_period_days": 220,     # calendar days for the test window
    "initial_capital": 10_000.0,    # dollars

    # Round-trip transaction cost as a percentage of initial capital
    # (for Buy & Hold) or per-trade fee (for MA / volatility strategies).
    "transaction_cost_pct": 0.001,

    # Which strategy to run
    "strategy": "buy_and_hold",

    # Parameters for the moving average crossover strategy
    "short_window": 20,
    "long_window": 50,

    # Parameters for volatility_tp strategy
    "vol_window": 20,
    "vol_threshold": 0.05,
    "take_profit": 0.02,
    "stop_loss": None,
}

# Tickers to compare on the same buy/sell dates
COMPARISON_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN",
]

MA_GRID_ENABLED = False


def main() -> None:
    print("[main] Starting single-trade backtest using Backtester...")

    cfg = STRATEGY_CONFIG
    ticker = cfg["ticker"]
    buy_date_str = cfg["buy_date"]
    holding_period_days = cfg["holding_period_days"]
    initial_capital = cfg["initial_capital"]
    transaction_cost_pct = cfg.get("transaction_cost_pct", 0.0)

    # Strategy + parameters
    strategy = cfg.get("strategy", "buy_and_hold")
    short_window = cfg.get("short_window", 20)
    long_window = cfg.get("long_window", 50)

    vol_window = cfg.get("vol_window", 20)
    vol_threshold = cfg.get("vol_threshold", 0.05)
    take_profit = cfg.get("take_profit", 0.02)
    stop_loss = cfg.get("stop_loss", None)

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
    elif strategy == "volatility_tp":
        print(f"  Vol threshold:       {vol_threshold * 100:.2f}% (|daily return|)")
        print(f"  Take profit:         {take_profit * 100:.2f}%")
        if stop_loss is not None:
            print(f"  Stop loss:           {stop_loss * 100:.2f}%")
    print("  Comparison tickers:  " + ", ".join(COMPARISON_TICKERS))

    # Initialize DataLoader (now backed by SQLite DB) and Backtester
    data_loader = DataLoader(db_path="data/prices.db")
    backtester = Backtester(data_loader=data_loader)

    # Run the chosen strategy for each comparison ticker
    results_by_ticker: dict[str, pd.DataFrame] = {}

    for comp_ticker in COMPARISON_TICKERS:
        print(f"\n[main] Running {strategy} for {comp_ticker}...")

        df_comp = backtester.run_strategy(
            strategy=strategy,
            ticker=comp_ticker,
            start=buy_date_str,
            end=sell_date_str,
            initial_capital=initial_capital,
            transaction_cost_pct=transaction_cost_pct,
            short_window=short_window,
            long_window=long_window,
            vol_window=vol_window,
            vol_threshold=vol_threshold,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )

        results_by_ticker[comp_ticker] = df_comp

    # ------------------------------------------------------------------
    # Primary ticker summary
    # ------------------------------------------------------------------
    df_main = results_by_ticker[ticker]

    buy_price = df_main["price"].iloc[0]
    sell_price = df_main["price"].iloc[-1]

    # For strategies like volatility_tp, shares may be 0 for a while.
    # Take the first non-zero position size, if any, as the "entry" size.
    nonzero_shares = df_main.loc[df_main["shares"] > 0, "shares"]
    if not nonzero_shares.empty:
        shares = int(nonzero_shares.iloc[0])
    else:
        shares = 0

    final_value = df_main["portfolio_value"].iloc[-1]
    pnl = final_value - initial_capital
    ret_pct = pnl / initial_capital

    print("\n=== Single-Trade Backtest Summary (Primary Ticker) ===")
    print(f"Ticker:           {ticker}")
    print(f"Strategy:         {strategy}")
    print(f"Buy date:         {buy_date_str} @ {buy_price:.2f}")
    print(f"Sell date:        {sell_date_str} @ {sell_price:.2f}")
    print(f"Shares (integer): {shares}")
    print(f"Initial capital:  {initial_capital:.2f}")
    print(f"Transaction cost: {transaction_cost_pct * 100:.3f}%")
    print(f"Final value:      {final_value:.2f}")
    print(f"PnL:              {pnl:.2f}")
    print(f"Return:           {ret_pct * 100:.2f}%")

    # ------------------------------------------------------------------
    # Performance summary table across all tickers (terminal only)
    # ------------------------------------------------------------------
    summary_rows: list[dict] = []

    for tkr, df in results_by_ticker.items():
        stats = backtester.summarize_performance(df, initial_capital=initial_capital)
        stats["ticker"] = tkr
        summary_rows.append(stats)

    summary_df = pd.DataFrame(summary_rows).set_index("ticker")

    # Add a simple Sharpe-like metric (return / vol)
    summary_df["sharpe_like"] = (
        summary_df["annualized_return"] / summary_df["annualized_vol"]
    )

    # Reorder columns for nicer display
    cols = [
        "final_value",
        "total_return",
        "annualized_return",
        "annualized_vol",
        "sharpe_like",
        "max_drawdown",
        "max_drawdown_duration_days",
    ]
    summary_df = summary_df[cols]

    # Sort by Sharpe-like metric (highest first)
    summary_df = summary_df.sort_values(by="sharpe_like", ascending=False)

    # Print a clean table to the terminal
    print("\n=== Performance Summary Across Tickers (sorted by Sharpe-like) ===")

    def fmt(x: float) -> str:
        return f"{x:,.4f}"

    print(summary_df.to_string(float_format=fmt))

    # Combined overview: top = risk–return, bottom = equity curves
    backtester.plot_overview(results_by_ticker, summary_df)

    print("\n[main] Backtest complete.")

    # ------------------------------------------------------------------
    # Optional: MA window grid search for the primary ticker
    # ------------------------------------------------------------------
    if strategy == "ma_crossover" and MA_GRID_ENABLED:
        print("\n=== MA Crossover Window Grid Search (primary ticker only) ===")
        print(f"Ticker: {ticker}, Buy: {buy_date_str}, Sell: {sell_date_str}")

        # You can tweak this list to whatever combos you like
        window_pairs = [
            (10, 50),
            (20, 50),
            (20, 100),
            (50, 200),
        ]

        grid_rows: list[dict] = []

        for short_w, long_w in window_pairs:
            if short_w >= long_w:
                continue  # skip invalid pairs

            print(f"[ma_grid] Testing short={short_w}, long={long_w}...")
            df_grid = backtester.run_ma_crossover(
                ticker=ticker,
                start=buy_date_str,
                end=sell_date_str,
                initial_capital=initial_capital,
                short_window=short_w,
                long_window=long_w,
                transaction_cost_pct=transaction_cost_pct,
            )

            stats = backtester.summarize_performance(
                df_grid, initial_capital=initial_capital
            )
            stats["short_window"] = short_w
            stats["long_window"] = long_w
            grid_rows.append(stats)

        if grid_rows:
            grid_df = pd.DataFrame(grid_rows)

            # Same Sharpe-like metric as before
            grid_df["sharpe_like"] = (
                grid_df["annualized_return"] / grid_df["annualized_vol"]
            )

            # Order columns nicely
            cols = [
                "short_window",
                "long_window",
                "final_value",
                "total_return",
                "annualized_return",
                "annualized_vol",
                "sharpe_like",
                "max_drawdown",
                "max_drawdown_duration_days",
            ]
            grid_df = grid_df[cols]

            # Sort by Sharpe-like metric (desc)
            grid_df = grid_df.sort_values(by="sharpe_like", ascending=False)

            # --- 1) Print ranked table ---
            print("\n--- MA Grid Results (sorted by Sharpe-like) ---")

            def grid_fmt(x: float) -> str:
                return f"{x:,.4f}"

            print(grid_df.to_string(float_format=grid_fmt))

            # --- 2) Print best config in a single “headline” line ---
            best = grid_df.iloc[0]
            print(
                "\n[ma_grid] Best config: "
                f"short={int(best['short_window'])}, "
                f"long={int(best['long_window'])}, "
                f"ann_return={best['annualized_return']*100:.2f}%, "
                f"vol={best['annualized_vol']*100:.2f}%, "
                f"sharpe_like={best['sharpe_like']:.2f}, "
                f"max_drawdown={best['max_drawdown']*100:.2f}%"
            )

            # --- 3) Plot grid as a Sharpe-like “heatmap” scatter ---
            fig, ax = plt.subplots(figsize=(8, 6))

            scatter = ax.scatter(
                grid_df["short_window"],
                grid_df["long_window"],
                c=grid_df["sharpe_like"],
                s=80,
            )

            # Label points with Sharpe-like value
            for _, row in grid_df.iterrows():
                ax.text(
                    row["short_window"],
                    row["long_window"],
                    f"{row['sharpe_like']:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                )

            cbar = plt.colorbar(scatter, ax=ax)
            cbar.set_label("Sharpe-like (ann_return / ann_vol)")

            ax.set_xlabel("Short MA window")
            ax.set_ylabel("Long MA window")
            ax.set_title(f"MA Grid Sharpe-like for {ticker}")

            ax.grid(True, linestyle="--", alpha=0.3)

            plt.tight_layout()
            plt.show()

        else:
            print("[ma_grid] No valid (short,long) window pairs were tested.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple stock backtest.")

    parser.add_argument("--ticker", type=str, default="TSLA",
                        help="Primary ticker to backtest (default: TSLA)")
    parser.add_argument("--buy-date", type=str, default="2023-01-03",
                        help="Start date YYYY-MM-DD (default: 2023-01-03)")
    parser.add_argument("--holding-days", type=int, default=220,
                        help="Holding period in calendar days (default: 220)")
    parser.add_argument("--initial-capital", type=float, default=10_000.0,
                        help="Initial capital (default: 10000.0)")
    parser.add_argument(
        "--transaction-cost-pct",
        type=float,
        default=0.001,
        # NOTE: 0.1%% so argparse doesn't choke on the %
        help="Transaction cost as fraction (default: 0.001 = 0.1%%)",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        choices=["buy_and_hold", "ma_crossover", "volatility_tp"],
        default="buy_and_hold",
        help="Strategy to run (default: buy_and_hold)",
    )

    parser.add_argument("--short-window", type=int, default=20,
                        help="Short MA window (used only for ma_crossover)")
    parser.add_argument("--long-window", type=int, default=50,
                        help="Long MA window (used only for ma_crossover)")

    # Parameters for volatility_tp strategy
    parser.add_argument(
        "--vol-window",
        type=int,
        default=20,
        help="(Reserved) window length for future volatility-based logic.",
    )
    parser.add_argument(
        "--vol-threshold",
        type=float,
        default=0.05,
        help="Absolute daily return threshold that triggers entry "
             "(e.g. 0.05 = 5%% daily move in either direction).",
    )
    parser.add_argument(
        "--take-profit",
        type=float,
        default=0.02,
        help="Take-profit threshold as return since entry (e.g. 0.02 = +2%%).",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=None,
        help="Optional stop-loss threshold as negative return since entry "
             "(e.g. 0.03 = -3%%).",
    )

    parser.add_argument("--comparison-tickers", type=str,
                        default="AAPL,MSFT,GOOGL,TSLA,AMZN",
                        help="Comma-separated list of comparison tickers")

    # Toggle MA grid search
    parser.add_argument(
        "--ma-grid",
        action="store_true",
        help="If set and strategy=ma_crossover, run a grid of (short,long) "
             "windows for the primary ticker.",
    )

    return parser.parse_args()

if __name__ == "__main__":
    # 1) Parse CLI args
    args = parse_args()

    # 2) Override config with CLI values
    STRATEGY_CONFIG = {
        "ticker": args.ticker,
        "buy_date": args.buy_date,
        "holding_period_days": args.holding_days,
        "initial_capital": args.initial_capital,
        "transaction_cost_pct": args.transaction_cost_pct,
        "strategy": args.strategy,
        "short_window": args.short_window,
        "long_window": args.long_window,
        "vol_window": args.vol_window,
        "vol_threshold": args.vol_threshold,
        "take_profit": args.take_profit,
        "stop_loss": args.stop_loss,
    }

    COMPARISON_TICKERS = [
        t.strip()
        for t in args.comparison_tickers.split(",")
        if t.strip()
    ]

    # Enable MA grid based on CLI flag
    MA_GRID_ENABLED = args.ma_grid

    # 3) Run the backtest
    main()
