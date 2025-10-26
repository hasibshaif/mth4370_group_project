# src/data_loader.py
"""
Data Loader Module
==================

This module defines the `DataLoader` class, which loads and preprocesses
historical stock data from locally stored CSV files.

It performs:
- File validation
- Date parsing and timezone removal
- Column normalization
- Optional date filtering
- Daily return computation

This serves as the main bridge between raw downloaded data (via Yahoo Finance)
and the backtesting engine.

Example usage:
--------------
    from src.data_loader import DataLoader

    loader = DataLoader(data_dir="data/raw")
    aapl = loader.load("AAPL", start="2024-01-01", end="2024-12-31")

    print(aapl.head())
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional


class DataLoader:
    """
    Loads and preprocesses stock data from local CSV files.

    Expected CSV Format:
    --------------------
    Each file should contain columns like:
        Date, Open, High, Low, Close, Volume, Dividends, Stock Splits

    Typical File Location:
        data/raw/AAPL.csv
        data/raw/MSFT.csv
    """

    def __init__(self, data_dir: str = "data/raw"):
        """
        Initialize the DataLoader with a directory containing CSV files.

        Parameters
        ----------
        data_dir : str, optional
            Path to the folder containing CSV files, by default "data/raw".
        """
        self.data_dir = Path(data_dir)

    # -------------------------------------------------------------------------
    # Load data for a single ticker
    # -------------------------------------------------------------------------
    def load(self, ticker: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """
        Load and clean historical stock data for a single ticker.

        Parameters
        ----------
        ticker : str
            The stock symbol (e.g., "AAPL", "MSFT").
        start : str, optional
            Start date (e.g., "2024-01-01") for filtering the dataset.
        end : str, optional
            End date (e.g., "2024-12-31") for filtering the dataset.

        Returns
        -------
        pd.DataFrame
            A cleaned DataFrame with standardized columns:
            - date
            - open
            - high
            - low
            - close
            - volume
            - dividends
            - stock splits
            - daily_return (computed % change)
        """
        # Construct full file path (e.g., data/raw/AAPL.csv)
        path = self.data_dir / f"{ticker.upper()}.csv"

        # Validate that the file exists
        if not path.exists():
            raise FileNotFoundError(f"Data file not found for {ticker} at {path}")

        # --- Step 1: Read the CSV file ---
        df = pd.read_csv(path)

        # --- Step 2: Parse dates and remove timezone info ---
        # Ensure 'Date' column is converted to pandas datetime and timezone-neutral
        df["Date"] = pd.to_datetime(df["Date"], utc=True, errors="coerce").dt.tz_convert(None)

        # --- Step 3: Standardize column names to lowercase ---
        df.columns = df.columns.str.lower()

        # --- Step 4: Sort data chronologically ---
        df = df.sort_values("date").reset_index(drop=True)

        # --- Step 5: Apply optional date filters ---
        if start:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end:
            df = df[df["date"] <= pd.Timestamp(end)]

        # --- Step 6: Compute daily returns (% change in closing price) ---
        if "close" in df.columns:
            df["daily_return"] = df["close"].pct_change()

        return df

    # -------------------------------------------------------------------------
    # Load data for multiple tickers at once
    # -------------------------------------------------------------------------
    def load_many(self, tickers: List[str], start: Optional[str] = None, end: Optional[str] = None) -> dict:
        """
        Load multiple tickers at once into a dictionary.

        Parameters
        ----------
        tickers : List[str]
            List of stock symbols (e.g., ["AAPL", "MSFT", "GOOGL"]).
        start : str, optional
            Start date filter.
        end : str, optional
            End date filter.

        Returns
        -------
        dict
            Dictionary of {ticker: DataFrame} pairs.
        """
        results = {}
        for ticker in tickers:
            try:
                results[ticker.upper()] = self.load(ticker, start, end)
            except FileNotFoundError:
                print(f"⚠️  File for {ticker} not found — skipping.")
        return results
