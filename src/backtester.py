"""
Backtester Module
=================

Provides a `Backtester` class that uses a `DataLoader` to simulate
simple trading strategies.

Implemented strategies:

    - Buy & Hold between two calendar dates.
    - Moving Average Crossover (long-only).
    - Volatility Take-Profit (enter after big daily moves, exit on TP/SL).

The backtester:

- Uses integer shares (no fractional shares).
- Invests as much of the capital as possible at the entry date
  (optionally net of transaction costs).
- Keeps leftover cash in the portfolio (uninvested).
- Tracks portfolio value over time.
- Plots equity curves and risk/return diagnostics.
"""

import math
import io
import base64

# Set matplotlib to use non-interactive backend before importing pyplot
# This prevents GUI-related errors when running in Flask/server context
import matplotlib
matplotlib.use('Agg')  # Use Anti-Grain Geometry backend (non-interactive)

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Try to import DataLoader regardless of whether you're using a `src/` package
# layout or keeping the files in the project root.
try:  # pragma: no cover - import flexibility helper
    from src.data_loader import DataLoader
except ImportError:  # pragma: no cover
    from data_loader import DataLoader


class Backtester:
    """
    Simple backtesting engine wired to a `DataLoader`.

    All concrete strategies follow the same pattern:

        - load prices via self.loader
        - produce a DataFrame with at least:
            date, price, shares, cash, portfolio_value, returns_factor
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

    # ------------------------------------------------------------------
    # Strategy: Moving Average Crossover
    # ------------------------------------------------------------------
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
    # Strategy: Volatility Take-Profit
    # ------------------------------------------------------------------
    def run_volatility_tp(
        self,
        ticker: str,
        start: str,
        end: str,
        initial_capital: float,
        vol_window: int = 20,          # currently unused; reserved for future tweaks
        vol_threshold: float = 0.05,   # absolute daily move threshold
        take_profit: float = 0.02,
        stop_loss=None,                # Python 3.9-friendly type
        transaction_cost_pct: float = 0.0,
    ) -> pd.DataFrame:
        """
        Long-only strategy driven by big daily moves and a profit target.

        Logic:

        - Compute daily returns and absolute daily move |ret|.
        - If we are flat and |ret| > vol_threshold on a given day -> buy with all capital.
        - Once in a position, hold until either:
            * price / entry_price - 1 >= take_profit  (take profit)
            * OR stop_loss is set and price / entry_price - 1 <= -stop_loss (stop loss)
        - Liquidate at the end if still holding.

        Note: `vol_window` is currently unused but kept in the signature / CLI
        so we can later switch to a rolling-volatility definition without
        breaking callers.
        """
        print(f"[Backtester] Volatility TP {ticker}: {start} -> {end}")

        # 1) Load data exactly like other strategies
        df = self.loader.load(ticker, start=start, end=end)
        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")

        # Use closing price as "price"
        df["price"] = df["close"]

        # Daily simple returns
        df["ret"] = df["price"].pct_change()

        # Absolute daily move (e.g. 0.05 = 5% move up OR down)
        df["abs_move"] = df["ret"].abs()

        # 2) Simulate trading day by day
        cash = initial_capital
        shares = 0
        entry_price = None

        cash_list = []
        shares_list = []
        value_list = []
        signal_list = []  # 1 when long, 0 when flat

        for idx, row in df.iterrows():
            price = row["price"]
            move = row["abs_move"]

            # Default: keep previous position
            signal = 1 if shares > 0 else 0

            # Entry: currently flat, big daily move (up or down)
            if shares == 0 and move is not None and not np.isnan(move):
                if move > vol_threshold:
                    trade_cost = cash * transaction_cost_pct
                    investable = cash - trade_cost
                    new_shares = int(investable // price)
                    if new_shares > 0:
                        cash = cash - trade_cost - new_shares * price
                        shares = new_shares
                        entry_price = price
                        signal = 1

            # Exit: we are in a position, check TP / SL
            elif shares > 0 and entry_price is not None:
                ret_since_entry = price / entry_price - 1.0
                hit_tp = ret_since_entry >= take_profit
                hit_sl = (stop_loss is not None) and (ret_since_entry <= -stop_loss)

                if hit_tp or hit_sl:
                    trade_value = shares * price
                    trade_cost = trade_value * transaction_cost_pct
                    cash = cash + trade_value - trade_cost
                    shares = 0
                    entry_price = None
                    signal = 0

            portfolio_value = cash + shares * price

            cash_list.append(cash)
            shares_list.append(shares)
            value_list.append(portfolio_value)
            signal_list.append(signal)

        # 3) Liquidate leftovers at end if still holding
        if shares > 0:
            last_price = df["price"].iloc[-1]
            trade_value = shares * last_price
            trade_cost = trade_value * transaction_cost_pct
            cash = cash + trade_value - trade_cost
            shares = 0
            value_list[-1] = cash  # last point reflects liquidation

        # 4) Attach series back to df (keeps 'date' column for plots)
        df["cash"] = cash_list
        df["shares"] = shares_list
        df["portfolio_value"] = value_list
        df["signal"] = signal_list
        df["returns_factor"] = df["portfolio_value"] / initial_capital

        # Performance summary (same print style as the others)
        summary = self.summarize_performance(df, initial_capital=initial_capital)
        print(
            f"  Final value:         ${summary['final_value']:,.2f}\n"
            f"  Total return:        {summary['total_return']:.2%}\n"
            f"  Annualized return:   {summary['annualized_return']:.2%}\n"
            f"  Annualized vol:      {summary['annualized_vol']:.2%}\n"
            f"  Max drawdown:        {summary['max_drawdown']:.2%}\n"
            f"  Max DD duration:     {summary['max_drawdown_duration_days']} days"
        )

        return df

    # ------------------------------------------------------------------
    # Generic strategy dispatcher
    # ------------------------------------------------------------------
    def run_strategy(
        self,
        strategy: str,
        ticker: str,
        start: str,
        end: str,
        initial_capital: float,
        **params,
    ) -> pd.DataFrame:
        """
        Generic entry point to run ANY strategy by name.

        All strategies must:
          - take (ticker, start, end, initial_capital, **params)
          - return a DataFrame with at least:
                price, shares, cash, portfolio_value, returns_factor
        """
        transaction_cost_pct = params.get("transaction_cost_pct", 0.0)

        if strategy == "buy_and_hold":
            return self.run_buy_and_hold(
                ticker=ticker,
                start=start,
                end=end,
                initial_capital=initial_capital,
                transaction_cost_pct=transaction_cost_pct,
            )

        elif strategy == "ma_crossover":
            return self.run_ma_crossover(
                ticker=ticker,
                start=start,
                end=end,
                initial_capital=initial_capital,
                short_window=params.get("short_window", 20),
                long_window=params.get("long_window", 50),
                transaction_cost_pct=transaction_cost_pct,
            )

        elif strategy == "volatility_tp":
            return self.run_volatility_tp(
                ticker=ticker,
                start=start,
                end=end,
                initial_capital=initial_capital,
                vol_window=params.get("vol_window", 20),
                vol_threshold=params.get("vol_threshold", 0.05),
                take_profit=params.get("take_profit", 0.02),
                stop_loss=params.get("stop_loss", None),
                transaction_cost_pct=transaction_cost_pct,
            )

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    # ------------------------------------------------------------------
    # Custom Strategy Execution
    # ------------------------------------------------------------------
    def run_custom_strategy(
        self,
        ticker: str,
        start: str,
        end: str,
        initial_capital: float,
        strategy_code: str,
        transaction_cost_pct: float = 0.0,
    ) -> pd.DataFrame:
        """
        Execute custom user-provided strategy code.
        
        The strategy_code should define a function named `strategy` that takes:
        - df: pd.DataFrame with columns: date, close, price, open, high, low, volume
        - initial_capital: float
        
        And returns:
        - pd.DataFrame with columns: date, price, shares, cash, portfolio_value, returns_factor
        
        Parameters
        ----------
        ticker : str
            Stock symbol
        start : str
            Start date (YYYY-MM-DD)
        end : str
            End date (YYYY-MM-DD)
        initial_capital : float
            Starting capital
        strategy_code : str
            Python code defining the strategy function
        transaction_cost_pct : float
            Transaction cost percentage
            
        Returns
        -------
        pd.DataFrame
            Backtest results with portfolio values over time
        """
        # Load data
        df = self.loader.load(ticker, start=start, end=end)
        if df.empty:
            raise ValueError(f"No data available for {ticker} in range {start} to {end}")
        
        df["price"] = df["close"]
        
        # Create execution environment with necessary imports
        exec_globals = {
            'pd': pd,
            'np': np,
            'math': math,
            'df': df.copy(),
            'initial_capital': initial_capital,
            'transaction_cost_pct': transaction_cost_pct,
        }
        
        # Execute the user's strategy code
        try:
            exec(strategy_code, exec_globals)
            
            # Check if strategy function exists
            if 'strategy' not in exec_globals:
                raise ValueError("Strategy code must define a function named 'strategy'")
            
            # Execute the strategy function
            strategy_func = exec_globals['strategy']
            result_df = strategy_func(df.copy(), initial_capital)
            
            # Validate result
            required_cols = ['date', 'price', 'shares', 'cash', 'portfolio_value']
            missing_cols = [col for col in required_cols if col not in result_df.columns]
            if missing_cols:
                raise ValueError(f"Strategy must return DataFrame with columns: {required_cols}. Missing: {missing_cols}")
            
            # Add returns_factor if not present
            if 'returns_factor' not in result_df.columns:
                result_df['returns_factor'] = result_df['portfolio_value'] / initial_capital
            
            return result_df
            
        except SyntaxError as e:
            raise ValueError(f"Syntax error in strategy code: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error executing strategy: {str(e)}")

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

    def plot_results_to_base64(self, df: pd.DataFrame, ticker: str) -> str:
        """
        Plot portfolio value over time and return as base64 encoded PNG.
        Used for Flask API responses.
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
                       label=f"{ticker} equity curve", linewidth=2, color='#2196F3')

        # Mark entry and exit
        buy_date = df["date"].iloc[0]
        sell_date = df["date"].iloc[-1]
        buy_value = df["portfolio_value"].iloc[0]
        sell_value = df["portfolio_value"].iloc[-1]

        ax_equity.scatter([buy_date], [buy_value], marker="^", s=100, 
                         label="Buy", color='green', zorder=5)
        ax_equity.scatter([sell_date], [sell_value], marker="v", s=100, 
                         label="Sell", color='red', zorder=5)

        ax_equity.set_title(f"Strategy Equity Curve for {ticker}", fontsize=14, fontweight='bold')
        ax_equity.set_ylabel("Portfolio Value ($)", fontsize=11)
        ax_equity.legend(loc='best')
        ax_equity.grid(True, linestyle="--", alpha=0.3)

        # --- Bottom: drawdown ---
        ax_dd.fill_between(df["date"], drawdown, 0, alpha=0.3, color='red')
        ax_dd.plot(df["date"], drawdown, linewidth=1.5, color='darkred')
        ax_dd.set_ylabel("Drawdown", fontsize=11)
        ax_dd.set_xlabel("Date", fontsize=11)
        ax_dd.grid(True, linestyle="--", alpha=0.3)
        ax_dd.set_ylim(drawdown.min() * 1.05, 0.0)

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        plt.close(fig)

        return img_base64
    
    def plot_comparison_to_base64(self, results_by_ticker: dict) -> str:
        """
        Plot normalized equity curves for multiple tickers and return as base64.
        Used for Flask API responses.
        """
        if not results_by_ticker:
            raise ValueError("No results to plot in plot_comparison_to_base64().")

        fig, ax = plt.subplots(figsize=(12, 7))

        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0', 
                  '#00BCD4', '#FFC107', '#795548']
        
        for idx, (ticker, df) in enumerate(results_by_ticker.items()):
            if df.empty:
                continue

            x = df["date"] if "date" in df.columns else df.index
            y = df["returns_factor"]
            color = colors[idx % len(colors)]

            ax.plot(x, y, label=ticker, linewidth=2, color=color)

        first_df = next(iter(results_by_ticker.values()))
        if "date" in first_df.columns:
            buy_date = first_df["date"].iloc[0]
            sell_date = first_df["date"].iloc[-1]
            ax.axvline(buy_date, linestyle="--", alpha=0.3, color='green', linewidth=1)
            ax.axvline(sell_date, linestyle="--", alpha=0.3, color='red', linewidth=1)

        ax.axhline(1.0, linestyle="--", alpha=0.5, color='gray', linewidth=1)
        ax.set_title("Strategy Comparison Across Tickers", fontsize=14, fontweight='bold')
        ax.set_xlabel("Date", fontsize=11)
        ax.set_ylabel("Normalized Portfolio Value (Initial = 1.0)", fontsize=11)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, linestyle="--", alpha=0.3)
        
        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        plt.close(fig)

        return img_base64

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
