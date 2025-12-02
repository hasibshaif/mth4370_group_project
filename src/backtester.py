"""
Backtester Module
=================

Provides a `Backtester` class that uses a `DataLoader` to simulate
simple trading strategies.

Right now we implement a **single** strategy:

    - Buy & Hold between two calendar dates.

The backtester:

- Uses integer shares (no fractional shares).
- Invests as much of the initial capital as possible at the entry date
  (optionally net of transaction costs).
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
        transaction_cost_pct: float = 0.0,
    ) -> pd.DataFrame:
        """
        Simulate a Buy & Hold strategy.

        We:
        - Buy on the first trading day >= `start`
        - Hold until the last trading day <= `end`
        - Use integer shares, investing as much of `initial_capital` as possible
        - Optionally apply a round-trip transaction cost (percentage of initial capital)
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
        transaction_cost_pct : float, optional
            Round-trip transaction cost as a fraction of initial capital.
            Example: 0.001 = 0.1% of initial capital lost to fees (entry+exit).

        Returns
        -------
        pd.DataFrame
            DataFrame with at least the following columns:
            - date
            - close
            - price                (alias of close)
            - shares               (constant over time)
            - cash                 (unused leftover from initial capital net of fees)
            - portfolio_value      (shares * price + cash)
            - returns_factor       (portfolio_value / initial_capital)
        """
        # Load data for the given window (inclusive)
        df = self.loader.load(ticker, start=start, end=end)

        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")

        # Use closing price for valuation
        df["price"] = df["close"]

        # Capital after applying round-trip transaction costs
        # We treat transaction_cost_pct as a one-shot cost on initial_capital
        # so all subsequent PnL is net of fees.
        effective_capital = initial_capital * (1.0 - transaction_cost_pct)

        # Entry is at the first row
        entry_price = df["price"].iloc[0]

        # Integer number of shares based on capital net of fees
        shares = math.floor(effective_capital / entry_price)
        if shares <= 0:
            raise ValueError(
                f"Effective capital {effective_capital} is too small to buy even 1 share "
                f"of {ticker} at entry price {entry_price:.2f}"
            )

        # Any leftover stays as unused cash
        cash = effective_capital - shares * entry_price

        # Store position info in the DataFrame
        df["shares"] = shares
        df["cash"] = cash

        # Portfolio value through time
        df["portfolio_value"] = df["shares"] * df["price"] + df["cash"]

        # Normalized returns factor relative to original initial capital
        df["returns_factor"] = df["portfolio_value"] / initial_capital

        # Performance summary
        summary = self.summarize_performance(df, initial_capital=initial_capital)

        print(
            f"[Backtester] Buy & Hold {ticker}: {start} -> {end}\n"
            f"  Final value:         ${summary['final_value']:,.2f}\n"
            f"  Total return:        {summary['total_return']:.2%}\n"
            f"  Annualized return:   {summary['annualized_return']:.2%}\n"
            f"  Annualized vol:      {summary['annualized_vol']:.2%}\n"
            f"  Max drawdown:        {summary['max_drawdown']:.2%}\n"
            f"  Max DD duration:     {summary['max_drawdown_duration_days']} days"
        )

        return df
    
    def run_ma_crossover(
        self,
        ticker: str,
        start: str,
        end: str,
        initial_capital: float = 1000.0,
        short_window: int = 20,
        long_window: int = 50,
        transaction_cost_pct: float = 0.0,
    ) -> pd.DataFrame:
        """
        Moving Average Crossover strategy.

        Rules (long-only):
        - Compute short and long moving averages of the closing price.
        - When short_ma > long_ma -> be fully invested (long).
        - When short_ma <= long_ma -> be in cash.
        - Each switch between cash <-> invested incurs transaction costs.

        Parameters
        ----------
        ticker : str
            Stock symbol, e.g. "TSLA".
        start : str
            Start date (YYYY-MM-DD) for the backtest window.
        end : str
            End date (YYYY-MM-DD) for the backtest window.
        initial_capital : float
            Starting capital for the strategy.
        short_window : int
            Lookback window for the short moving average.
        long_window : int
            Lookback window for the long moving average.
        transaction_cost_pct : float
            Per-trade fee (fraction of traded notional).
            Example: 0.001 = 0.1% of trade value per buy or sell.

        Returns
        -------
        pd.DataFrame
            Same structure as `run_buy_and_hold`, with:
            - price
            - short_ma, long_ma
            - signal (1 = invested, 0 = cash)
            - shares, cash, portfolio_value, returns_factor
        """
        if long_window <= short_window:
            raise ValueError("long_window must be greater than short_window for MA crossover.")

        # Load data for the given window
        df = self.loader.load(ticker, start=start, end=end)
        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")

        # Use close as price
        df["price"] = df["close"]

        # Compute moving averages
        df["short_ma"] = df["price"].rolling(window=short_window).mean()
        df["long_ma"] = df["price"].rolling(window=long_window).mean()

        # Drop rows before both MAs are defined
        df = df.dropna(subset=["short_ma", "long_ma"]).copy()
        if df.empty:
            raise ValueError(
                f"Not enough data to compute moving averages for {ticker} "
                f"(short_window={short_window}, long_window={long_window})"
            )

        # Signal: 1 if short_ma > long_ma, else 0
        df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)

        # Initialize portfolio state
        cash = initial_capital
        shares = 0
        position = 0  # 0 = cash, 1 = invested

        cash_list = []
        shares_list = []
        portval_list = []

        # Walk forward in time
        for i in range(len(df)):
            price = df["price"].iloc[i]
            signal = df["signal"].iloc[i]

            # Buy: go from cash -> invested
            if signal == 1 and position == 0:
                # Pay fee on the cash we are about to deploy
                fee = cash * transaction_cost_pct
                tradable_cash = cash - fee
                if tradable_cash > 0:
                    new_shares = math.floor(tradable_cash / price)
                else:
                    new_shares = 0

                spend = new_shares * price
                cash = cash - fee - spend
                shares = new_shares
                position = 1

            # Sell: go from invested -> cash
            elif signal == 0 and position == 1:
                trade_notional = shares * price
                fee = trade_notional * transaction_cost_pct
                cash = cash + trade_notional - fee
                shares = 0
                position = 0

            # Portfolio value at the end of the day
            portfolio_value = cash + shares * price

            cash_list.append(cash)
            shares_list.append(shares)
            portval_list.append(portfolio_value)

        # Attach portfolio series
        df["cash"] = cash_list
        df["shares"] = shares_list
        df["portfolio_value"] = portval_list

        # Normalize by initial capital
        df["returns_factor"] = df["portfolio_value"] / initial_capital

        # Performance summary
        summary = self.summarize_performance(df, initial_capital=initial_capital)

        print(
            f"[Backtester] MA Crossover {ticker}: {start} -> {end}\n"
            f"  Final value:         ${summary['final_value']:,.2f}\n"
            f"  Total return:        {summary['total_return']:.2%}\n"
            f"  Annualized return:   {summary['annualized_return']:.2%}\n"
            f"  Annualized vol:      {summary['annualized_vol']:.2%}\n"
            f"  Max drawdown:        {summary['max_drawdown']:.2%}\n"
            f"  Max DD duration:     {summary['max_drawdown_duration_days']} days"
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

    def plot_comparison(self, results_by_ticker: dict[str, pd.DataFrame]) -> None:
        """
        Plot normalized equity curves for several tickers on the same figure.

        Parameters
        ----------
        results_by_ticker : dict[str, pd.DataFrame]
            Mapping from ticker symbol to the DataFrame returned by
            `run_buy_and_hold` for that ticker.
        """
        if not results_by_ticker:
            raise ValueError("No results to plot in plot_comparison().")

        plt.figure(figsize=(10, 6))

        for ticker, df in results_by_ticker.items():
            if df.empty:
                continue

            # X-axis: use the date column if present, otherwise the index
            x = df["date"] if "date" in df.columns else df.index
            y = df["returns_factor"]  # normalized so all start at 1.0

            plt.plot(x, y, label=ticker)

        # Use the first ticker's dates for buy/sell vertical markers (optional)
        first_df = next(iter(results_by_ticker.values()))
        if "date" in first_df.columns:
            buy_date = first_df["date"].iloc[0]
            sell_date = first_df["date"].iloc[-1]
            plt.axvline(buy_date, linestyle="--", alpha=0.3)
            plt.axvline(sell_date, linestyle="--", alpha=0.3)

        plt.title("Buy & Hold Comparison Across Tickers")
        plt.xlabel("Date")
        plt.ylabel("Portfolio value (normalized to 1.0)")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------
    def summarize_performance(self, df: pd.DataFrame, initial_capital: float) -> dict:
        """
        Compute basic performance statistics for a single buy & hold run.

        Returns a dict with:
        - final_value
        - total_return
        - annualized_return
        - annualized_vol
        - max_drawdown
        - max_drawdown_duration_days
        """
        if df.empty:
            raise ValueError("Cannot summarize performance of an empty DataFrame.")

        # Final portfolio value and total return
        final_value = float(df["portfolio_value"].iloc[-1])
        total_return = final_value / initial_capital - 1.0

        # Daily simple returns of the portfolio
        daily_returns = df["portfolio_value"].pct_change().dropna()

        # Number of calendar days in the trade
        if "date" in df.columns and len(df.index) > 1:
            n_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
        else:
            n_days = 0

        # Annualized return (using total_return over n_days)
        if n_days > 0:
            annualized_return = (1.0 + total_return) ** (252.0 / n_days) - 1.0
        else:
            annualized_return = float("nan")

        # Annualized volatility of daily returns
        if len(daily_returns) > 1:
            annualized_vol = float(daily_returns.std() * (252.0 ** 0.5))
        else:
            annualized_vol = float("nan")

        # Max drawdown
        cum_max = df["portfolio_value"].cummax()
        drawdown = df["portfolio_value"] / cum_max - 1.0
        max_drawdown = float(drawdown.min())

        # Max drawdown duration (consecutive days below a peak)
        durations = []
        current_duration = 0
        for dd in drawdown:
            if dd < 0:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                current_duration = 0
        if current_duration > 0:
            durations.append(current_duration)

        max_drawdown_duration_days = max(durations) if durations else 0

        return {
            "final_value": final_value,
            "total_return": total_return,
            "annualized_return": annualized_return,
            "annualized_vol": annualized_vol,
            "max_drawdown": max_drawdown,
            "max_drawdown_duration_days": max_drawdown_duration_days,
        }
