"""
Data Loader Module
==================

Provides a `DataLoader` class for reading cleaned historical price data
from CSV files on disk.

It knows how to handle **two** formats:

1) Normal Yahoo Finance / yfinance-style CSV

    Date,Open,High,Low,Close,Adj Close,Volume
    2015-01-02,...

2) Your custom class CSV format (what you pasted), which looks like:

    Price,Close,High,Low,Open,Volume
    Ticker,AAPL,AAPL,AAPL,AAPL,AAPL
    Date,,,,,
    2015-01-02,24.23,24.70,23.79,24.69,212818400
    ...

The loader will automatically detect which format it is looking at and
standardize the output to have these columns:

    - date (datetime)
    - open
    - high
    - low
    - close
    - volume
    - daily_return  (% change in close)
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd


class DataLoader:
    """
    Load and clean historical price data for one or more tickers.
    """

    def __init__(self, data_dir: str = "data/raw"):
        """
        Parameters
        ----------
        data_dir : str
            Directory where CSV files live, e.g. "data/raw".
        """
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Internal helpers for each CSV format
    # ------------------------------------------------------------------
    def _load_standard_format(self, path: Path) -> pd.DataFrame:
        """
        Load a standard yfinance-style CSV with a 'Date' column in the header.
        """
        df = pd.read_csv(path)

        if "Date" not in df.columns:
            raise KeyError("No 'Date' column found in standard-format loader.")

        # Parse dates, drop invalid, and make timezone-naive
        df["Date"] = pd.to_datetime(df["Date"], utc=True, errors="coerce").dt.tz_convert(None)
        df = df.dropna(subset=["Date"])

        # Normalize column names to lowercase for consistency
        df.columns = df.columns.str.lower()

        # Ensure sorted chronologically
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def _load_custom_class_format(self, path: Path) -> pd.DataFrame:
        """
        Load your custom class CSV format that starts with:

            Price,Close,High,Low,Open,Volume
            Ticker,<ticker>,<ticker>,...
            Date,,,,,
            2015-01-02,24.23,...

        We ignore the first two rows and use the 'Date' marker row to
        detect where real data starts.
        """
        raw = pd.read_csv(path, header=None)

        if raw.shape[0] < 4:
            raise ValueError("File too short to be in custom class format.")

        # Row index 2, column 0 should be 'Date'
        header_marker = str(raw.iloc[2, 0]).strip().upper()
        if header_marker != "DATE":
            raise ValueError(
                "File does not look like the custom Price/Ticker/Date format "
                f"(marker={header_marker!r})."
            )

        # Data starts at row index 3, first 6 columns
        data = raw.iloc[3:].copy()
        data = data.loc[:, :5]  # keep exactly 6 columns

        data.columns = [
            "date_raw",
            "close_raw",
            "high_raw",
            "low_raw",
            "open_raw",
            "volume_raw",
        ]

        # Drop completely empty rows
        data = data[
            data["date_raw"].notna()
            & (data["date_raw"].astype(str).str.strip() != "")
        ]

        # Parse date and numeric columns
        data["date"] = pd.to_datetime(data["date_raw"], errors="coerce")
        for col in ["close_raw", "high_raw", "low_raw", "open_raw", "volume_raw"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        # Require a valid date and close
        data = data.dropna(subset=["date", "close_raw"])

        # Build final standardized DataFrame
        df = pd.DataFrame(
            {
                "date": data["date"],
                "open": data["open_raw"],
                "high": data["high_raw"],
                "low": data["low_raw"],
                "close": data["close_raw"],
                "volume": data["volume_raw"],
            }
        )

        df = df.sort_values("date").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self, ticker: str, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """
        Load and clean price data for a single ticker.

        Parameters
        ----------
        ticker : str
            Symbol of the stock, e.g. "AAPL".
        start : str, optional
            Start date for filtering (YYYY-MM-DD).
        end : str, optional
            End date for filtering (YYYY-MM-DD).

        Returns
        -------
        pd.DataFrame
            DataFrame with columns:
            - date
            - open
            - high
            - low
            - close
            - volume
            - daily_return
        """
        path = self.data_dir / f"{ticker.upper()}.csv"

        if not path.exists():
            raise FileNotFoundError(f"Data file not found for {ticker} at {path}")

        # First try the standard yfinance-style loader
        try:
            df = self._load_standard_format(path)
        except Exception:
            # If that fails, fall back to the custom class CSV format
            df = self._load_custom_class_format(path)

        # Apply optional date filters
        if start:
            df = df[df["date"] >= pd.Timestamp(start)]
        if end:
            df = df[df["date"] <= pd.Timestamp(end)]

        df = df.sort_values("date").reset_index(drop=True)

        # Compute daily return if we have close prices
        if "close" in df.columns:
            df["daily_return"] = df["close"].pct_change()

        return df

    def load_many(self, tickers: List[str], start: Optional[str] = None, end: Optional[str] = None) -> dict:
        """
        Load data for multiple tickers at once.

        Returns
        -------
        dict
            Mapping from ticker symbol -> cleaned DataFrame.
        """
        out = {}
        for t in tickers:
            out[t] = self.load(t, start=start, end=end)
        return out
