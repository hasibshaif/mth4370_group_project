"""
Backtester Module
=================

Provides a `Backtester` class that uses a `DataLoader` to simulate
simple trading strategies.

Right now we implement a **single** strategy:

    - Buy & Hold between two calendar dates.

The backtester:

- Uses integer shares (no fractional shares).
- Invests as much of the initial capital as possible at the entry date.
- Keeps leftover cash in the portfolio (uninvested).
- Tracks portfolio value over time.
- Plots the equity curve with markers for buy/sell.
"""

import math

import matplotlib.pyplot as plt
import pandas as pd

# Try to import DataLoader regardless of whether you're using a `src/` package
# layout or keeping the files in the project root.
try:  # pragma: no cover - import flexibility helper
    from src.data_loader import DataLoader
except ImportError:  # pragma: no cover
    from data_loader import DataLoader


class Backtester:
    """
    Simple backtesting engine wired to a `DataLoader`.
    """

    def __init__(self, data_loader: DataLoader):
        """
        Parameters
        ----------
        data_loader : DataLoader
            An instance of DataLoader that knows how to load price data.
        """
        self.loader = data_loader

    # ------------------------------------------------------------------
    # Strategy: Buy & Hold
    # ------------------------------------------------------------------
    def run_buy_and_hold(
        self,
        ticker: str,
        start: str,
        end: str,
        initial_capital: float = 1000.0,
    ) -> pd.DataFrame:
        """
        Simulate a Buy & Hold strategy.

        We:
        - Buy on the first trading day >= `start`
        - Hold until the last trading day <= `end`
        - Use integer shares, investing as much of `initial_capital` as possible
        - Leave leftover cash sitting in the portfolio

        Parameters
        ----------
        ticker : str
            Stock symbol, e.g. "TSLA".
        start : str
            Start date (YYYY-MM-DD) for the backtest window.
        end : str
            End date (YYYY-MM-DD) for the backtest window.
        initial_capital : float, optional
            Starting capital for the strategy.

        Returns
        -------
        pd.DataFrame
            DataFrame with at least the following columns:
            - date
            - close
            - price                (alias of close)
            - shares               (constant over time)
            - cash                 (unused leftover from initial capital)
            - portfolio_value      (shares * price + cash)
            - returns_factor       (portfolio_value / initial_capital)
        """
        # Load data for the given window (inclusive)
        df = self.loader.load(ticker, start=start, end=end)

        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")

        # Use closing price for valuation
        df["price"] = df["close"]

        # Entry is at the first row
        entry_price = df["price"].iloc[0]

        # Integer number of shares
        shares = math.floor(initial_capital / entry_price)
        if shares <= 0:
            raise ValueError(
                f"Initial capital {initial_capital} is too small to buy even 1 share "
                f"of {ticker} at entry price {entry_price:.2f}"
            )

        # Any leftover stays as unused cash
        cash = initial_capital - shares * entry_price

        # Store position info in the DataFrame
        df["shares"] = shares
        df["cash"] = cash

        # Portfolio value through time
        df["portfolio_value"] = df["shares"] * df["price"] + df["cash"]

        # Normalized returns factor relative to initial capital
        df["returns_factor"] = df["portfolio_value"] / initial_capital

        # Print a quick summary line
        total_return = df["portfolio_value"].iloc[-1] / initial_capital - 1
        print(
            f"[Backtester] Buy & Hold {ticker}: "
            f"{start} -> {end} | return = {total_return:.2%}"
        )

        return df

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------
    def plot_results(self, df: pd.DataFrame, ticker: str) -> None:
        """
        Plot portfolio value over time, with buy/sell markers.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame returned by `run_buy_and_hold`.
        ticker : str
            Symbol being plotted (used for the title/legend).
        """
        if df.empty:
            raise ValueError("Cannot plot results: DataFrame is empty.")

        plt.figure(figsize=(10, 5))

        # Equity curve
        plt.plot(df["date"], df["portfolio_value"], label=f"{ticker} equity curve", linewidth=2)

        # Mark entry and exit
        buy_date = df["date"].iloc[0]
        sell_date = df["date"].iloc[-1]
        buy_value = df["portfolio_value"].iloc[0]
        sell_value = df["portfolio_value"].iloc[-1]

        plt.scatter([buy_date], [buy_value], marker="^", s=80, label="Buy")
        plt.scatter([sell_date], [sell_value], marker="v", s=80, label="Sell")

        plt.title(f"Buy & Hold Strategy for {ticker}")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()
