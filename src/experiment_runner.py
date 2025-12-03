from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal, Dict, Any, List

import pandas as pd

from .data_loader import DataLoader
from .backtester import Backtester


StrategyName = Literal["buy_and_hold", "ma_crossover"]


@dataclass
class ExperimentConfig:
    """
    Configuration for a single backtest experiment.

    You can extend this later with more strategy-specific parameters.
    """
    ticker: str
    strategy: StrategyName
    buy_date: str              # "YYYY-MM-DD"
    holding_period_days: int
    initial_capital: float = 10_000.0
    transaction_cost_pct: float = 0.0

    # Only used for ma_crossover
    short_window: int = 20
    long_window: int = 50


@dataclass
class ExperimentResult:
    """
    Output of a single backtest experiment.

    This is designed to be JSON-friendly (via .to_dict()) and
    super easy to show in a frontend table.
    """
    ticker: str
    strategy: StrategyName
    buy_date: str
    sell_date: str

    # Strategy parameters
    initial_capital: float
    transaction_cost_pct: float
    short_window: int | None
    long_window: int | None

    # Key metrics
    final_value: float
    total_return: float
    annualized_return: float
    annualized_vol: float
    sharpe_like: float
    max_drawdown: float
    max_drawdown_duration_days: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentRunner:
    """
    Helper to run many backtest experiments and collect their metrics
    in a single pandas DataFrame.
    """

    def __init__(self, db_path: str = "data/prices.db"):
        self.data_loader = DataLoader(db_path=db_path)
        self.backtester = Backtester(data_loader=self.data_loader)

    def run_experiments(
        self,
        configs: List[ExperimentConfig],
    ) -> pd.DataFrame:
        """
        Run a batch of experiments and return a DataFrame where each row
        corresponds to one (ticker, strategy, parameter set).
        """
        results: List[ExperimentResult] = []

        for cfg in configs:
            # Compute date range strings
            buy_ts = pd.to_datetime(cfg.buy_date)
            sell_ts = buy_ts + pd.Timedelta(days=cfg.holding_period_days)
            sell_date_str = sell_ts.strftime("%Y-%m-%d")

            if cfg.strategy == "buy_and_hold":
                df = self.backtester.run_buy_and_hold(
                    ticker=cfg.ticker,
                    start=cfg.buy_date,
                    end=sell_date_str,
                    initial_capital=cfg.initial_capital,
                    transaction_cost_pct=cfg.transaction_cost_pct,
                )
                short_window = None
                long_window = None

            elif cfg.strategy == "ma_crossover":
                df = self.backtester.run_ma_crossover(
                    ticker=cfg.ticker,
                    start=cfg.buy_date,
                    end=sell_date_str,
                    initial_capital=cfg.initial_capital,
                    short_window=cfg.short_window,
                    long_window=cfg.long_window,
                    transaction_cost_pct=cfg.transaction_cost_pct,
                )
                short_window = cfg.short_window
                long_window = cfg.long_window

            else:
                raise ValueError(f"Unknown strategy: {cfg.strategy}")

            # Summarize performance using your existing helper
            stats = self.backtester.summarize_performance(
                df, initial_capital=cfg.initial_capital
            )

            sharpe_like = (
                stats["annualized_return"] / stats["annualized_vol"]
                if stats["annualized_vol"] != 0
                else float("nan")
            )

            result = ExperimentResult(
                ticker=cfg.ticker,
                strategy=cfg.strategy,
                buy_date=cfg.buy_date,
                sell_date=sell_date_str,
                initial_capital=cfg.initial_capital,
                transaction_cost_pct=cfg.transaction_cost_pct,
                short_window=short_window,
                long_window=long_window,
                final_value=stats["final_value"],
                total_return=stats["total_return"],
                annualized_return=stats["annualized_return"],
                annualized_vol=stats["annualized_vol"],
                sharpe_like=sharpe_like,
                max_drawdown=stats["max_drawdown"],
                max_drawdown_duration_days=stats["max_drawdown_duration_days"],
            )
            results.append(result)

        # Turn the list of dataclasses into a DataFrame
        df_results = pd.DataFrame([r.to_dict() for r in results])

        # Nice default index: (ticker, strategy)
        df_results = df_results.set_index(["ticker", "strategy"]).sort_index()

        return df_results