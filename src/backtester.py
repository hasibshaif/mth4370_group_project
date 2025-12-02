"""
Backtester Module
=================

Provides a `Backtester` class that uses a `DataLoader` to simulate
simple trading strategies.

Implemented strategies:

    - Buy & Hold between two calendar dates.
    - Moving Average Crossover (long-only).

The backtester:

- Uses integer shares (no fractional shares).
- Invests as much of the capital as possible at the entry date
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
        Plot portfolio value over time with buy/sell markers
        and a drawdown subplot.
        """
        if df.empty:
            raise ValueError("Cannot plot results: DataFrame is empty.")

        # Compute drawdown series
        cum_max = df["portfolio_value"].cummax()
        drawdown = df["portfolio_value"] / cum_max - 1.0

        fig, (ax_equity, ax_dd) = plt.subplots(
            2, 1, figsize=(10, 7), sharex=True,
            gridspec_kw={"height_ratios": [3, 1]}
        )

        # --- Top: equity curve ---
        ax_equity.plot(df["date"], df["portfolio_value"],
                       label=f"{ticker} equity curve", linewidth=2)

        # Mark entry and exit
        buy_date = df["date"].iloc[0]
        sell_date = df["date"].iloc[-1]
        buy_value = df["portfolio_value"].iloc[0]
        sell_value = df["portfolio_value"].iloc[-1]

        ax_equity.scatter([buy_date], [buy_value], marker="^", s=80, label="Buy")
        ax_equity.scatter([sell_date], [sell_value], marker="v", s=80, label="Sell")

        ax_equity.set_title(f"Strategy Equity Curve for {ticker}")
        ax_equity.set_ylabel("Portfolio Value")
        ax_equity.legend()
        ax_equity.grid(True, linestyle="--", alpha=0.5)

        # --- Bottom: drawdown ---
        ax_dd.plot(df["date"], drawdown, linewidth=1.5)
        ax_dd.set_ylabel("Drawdown")
        ax_dd.set_xlabel("Date")
        ax_dd.grid(True, linestyle="--", alpha=0.5)

        # Force y-axis to show negatives clearly
        ax_dd.set_ylim(drawdown.min() * 1.05, 0.0)

        plt.tight_layout()
        plt.show()

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------
    def summarize_performance(self, df: pd.DataFrame, initial_capital: float) -> dict:
        """
        Compute basic performance statistics for a single strategy run.
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

    def plot_risk_return(self, summary_df: pd.DataFrame) -> None:
        """
        Plot a risk-return scatter for multiple tickers.

        Expects summary_df to have:
        - 'annualized_return'
        - 'annualized_vol'
        indexed by ticker.
        """
        if summary_df.empty:
            raise ValueError("summary_df is empty in plot_risk_return().")

        plt.figure(figsize=(8, 6))

        x = summary_df["annualized_vol"]
        y = summary_df["annualized_return"]

        plt.scatter(x, y)

        # Annotate each point with the ticker
        for ticker, (vol, ret) in summary_df[["annualized_vol", "annualized_return"]].iterrows():
            plt.annotate(
                ticker,
                (vol, ret),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )

        plt.xlabel("Annualized Volatility")
        plt.ylabel("Annualized Return")
        plt.title("Risk–Return Scatter (per ticker)")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()

    def plot_comparison(self, results_by_ticker: dict[str, pd.DataFrame]) -> None:
        """
        Plot normalized equity curves for several tickers on the same figure.
        """
        if not results_by_ticker:
            raise ValueError("No results to plot in plot_comparison().")

        plt.figure(figsize=(10, 6))

        for ticker, df in results_by_ticker.items():
            if df.empty:
                continue

            x = df["date"] if "date" in df.columns else df.index
            y = df["returns_factor"]

            plt.plot(x, y, label=ticker)

        first_df = next(iter(results_by_ticker.values()))
        if "date" in first_df.columns:
            buy_date = first_df["date"].iloc[0]
            sell_date = first_df["date"].iloc[-1]
            plt.axvline(buy_date, linestyle="--", alpha=0.3)
            plt.axvline(sell_date, linestyle="--", alpha=0.3)

        plt.title("Strategy Comparison Across Tickers")
        plt.xlabel("Date")
        plt.ylabel("Portfolio value (normalized to 1.0)")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.show()

    def plot_overview(
        self,
        results_by_ticker: dict[str, pd.DataFrame],
        summary_df: pd.DataFrame,
    ) -> None:
        """
        Combined overview figure:

        Top:  risk–return scatter (annualized_return vs annualized_vol)
        Bottom: normalized equity curves (returns_factor) across tickers.
        """
        if not results_by_ticker:
            raise ValueError("No results to plot in plot_overview().")
        if summary_df.empty:
            raise ValueError("summary_df is empty in plot_overview().")

        fig, (ax_rr, ax_eq) = plt.subplots(
            2, 1, figsize=(10, 10),
            gridspec_kw={"height_ratios": [1, 2]},
            sharex=False
        )

        # --- Top: risk–return scatter ---
        x = summary_df["annualized_vol"]
        y = summary_df["annualized_return"]

        ax_rr.scatter(x, y)

        for ticker, (vol, ret) in summary_df[["annualized_vol", "annualized_return"]].iterrows():
            ax_rr.annotate(
                ticker,
                (vol, ret),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )

        ax_rr.set_xlabel("Annualized Volatility")
        ax_rr.set_ylabel("Annualized Return")
        ax_rr.set_title("Risk–Return Scatter (per ticker)")
        ax_rr.grid(True, linestyle="--", alpha=0.5)

        # --- Bottom: normalized equity curves ---
        for ticker, df in results_by_ticker.items():
            if df.empty:
                continue
            x_eq = df["date"] if "date" in df.columns else df.index
            y_eq = df["returns_factor"]
            ax_eq.plot(x_eq, y_eq, label=ticker)

        first_df = next(iter(results_by_ticker.values()))
        if "date" in first_df.columns:
            buy_date = first_df["date"].iloc[0]
            sell_date = first_df["date"].iloc[-1]
            ax_eq.axvline(buy_date, linestyle="--", alpha=0.3)
            ax_eq.axvline(sell_date, linestyle="--", alpha=0.3)

        ax_eq.set_title("Strategy Comparison Across Tickers")
        ax_eq.set_xlabel("Date")
        ax_eq.set_ylabel("Portfolio value (normalized to 1.0)")
        ax_eq.legend()
        ax_eq.grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()
        plt.show()

