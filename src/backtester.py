# src/backtester.py
"""
Backtester Module
=================

This module provides the `Backtester` class, which simulates investment
strategies (starting with a Buy & Hold strategy) using historical price data
from the DataLoader class.

It supports:
- Simulating portfolio value over time
- Calculating total returns
- Plotting performance charts

Future versions can extend this class with other strategies (e.g. moving average, RSI, etc.).
"""

import pandas as pd
import matplotlib.pyplot as plt
from src.data_loader import DataLoader


class Backtester:
    """
    A simple backtesting engine for running trading strategy simulations.

    The class currently supports a Buy & Hold strategy but is designed
    to be extended with more complex strategies in the future.
    """

    def __init__(self, data_loader: DataLoader):
        """
        Initialize the Backtester with a DataLoader instance.

        Parameters
        ----------
        data_loader : DataLoader
            An instance of DataLoader that provides access to historical stock data.
        """
        self.loader = data_loader

    # -------------------------------------------------------------------------
    # STRATEGY 1: BUY & HOLD
    # -------------------------------------------------------------------------
    def run_buy_and_hold(self, ticker: str, start: str, end: str, initial_capital: float = 1000.0) -> pd.DataFrame:
        """
        Simulate a Buy & Hold strategy.

        This strategy assumes you buy the stock at the start date and hold it
        until the end date without selling in between.

        Parameters
        ----------
        ticker : str
            The stock symbol to backtest (e.g., "AAPL", "MSFT").
        start : str
            Start date for the backtest (format: "YYYY-MM-DD").
        end : str
            End date for the backtest (format: "YYYY-MM-DD").
        initial_capital : float, optional
            The starting amount of capital to invest, by default 1000.0.

        Returns
        -------
        pd.DataFrame
            DataFrame containing the portfolio value over time with columns:
            - date: trading day
            - price: stock's closing price
            - returns_factor: price normalized to starting price
            - portfolio_value: value of portfolio at each date
        """
        # Load historical price data
        df = self.loader.load(ticker, start, end)

        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")

        # Use closing price for valuation
        df["price"] = df["close"]

        # Normalize prices to start at 1 (so returns_factor = 1 on first day)
        df["returns_factor"] = df["price"] / df["price"].iloc[0]

        # Portfolio value = normalized price * initial capital
        df["portfolio_value"] = df["returns_factor"] * initial_capital

        # Print total return in console
        total_return = (df["price"].iloc[-1] / df["price"].iloc[0]) - 1
        print(f"Buy & Hold return for {ticker} from {start} to {end}: {total_return:.2%}")

        return df

    # -------------------------------------------------------------------------
    # VISUALIZATION
    # -------------------------------------------------------------------------
    def plot_results(self, df: pd.DataFrame, ticker: str):
        """
        Plot the portfolio performance over time.

        Parameters
        ----------
        df : pd.DataFrame
            The DataFrame returned by a backtest function (e.g., `run_buy_and_hold`).
        ticker : str
            The stock symbol being plotted (for chart title/legend).
        """
        plt.figure(figsize=(10, 5))

        # Plot portfolio value curve
        plt.plot(
            df["date"],
            df["portfolio_value"],
            label=f"{ticker} Portfolio Value",
            linewidth=2
        )

        # Styling and labels
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value ($)")
        plt.title(f"Buy & Hold Simulation for {ticker}")
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Note: In future, you could save the figure using:
        # plt.savefig(f"results/{ticker}_buy_and_hold.png", dpi=300)

