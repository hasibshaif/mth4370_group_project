# src/data_acquisition.py
"""
Data Acquisition Module
=======================

This module provides the `YahooFinanceDataFetcher` class, which allows you to
fetch historical stock market data directly from Yahoo Finance.

It supports:
- Fetching data for a single stock (using ticker symbols like "AAPL", "MSFT")
- Fetching multiple stocks at once
- Retrieving basic company info (sector, market cap, etc.)
- Returning results as clean pandas DataFrames ready for analysis

Example usage:
--------------
    from src.data_acquisition import YahooFinanceDataFetcher, get_popular_stocks
    from datetime import datetime, timedelta

    fetcher = YahooFinanceDataFetcher()
    end = datetime.now()
    start = end - timedelta(days=365)

    # Fetch Apple data
    aapl_data = fetcher.fetch_stock_data("AAPL", start, end)
    aapl_data.to_csv("data/aapl_data.csv", index=False)

    # Fetch multiple popular stocks
    stocks = get_popular_stocks()
    data_dict = fetcher.fetch_multiple_stocks(stocks, start, end)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import List, Union, Dict, Any


class YahooFinanceDataFetcher:
    """
    A helper class for downloading historical market data from Yahoo Finance.

    This class uses the `yfinance` API to retrieve:
    - Price data (Open, High, Low, Close, Volume, Dividends, Stock Splits)
    - Company metadata (name, sector, market cap, etc.)

    Returns pandas DataFrames that can be easily saved, plotted, or analyzed.
    """

    def __init__(self):
        """Initialize the YahooFinanceDataFetcher object."""
        self.session = None  # Placeholder for future HTTP session reuse

    # -------------------------------------------------------------------------
    # 1️⃣ Fetch data for a single stock
    # -------------------------------------------------------------------------
    def fetch_stock_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch historical price data for a single stock from Yahoo Finance.

        Parameters
        ----------
        symbol : str
            Stock ticker symbol (e.g., "AAPL", "MSFT", "TSLA").
        start_date : str or datetime
            Start date of the data range.
        end_date : str or datetime
            End date of the data range.
        interval : str, optional
            Frequency of data (e.g., "1d" for daily, "1wk" for weekly, "1mo" for monthly),
            by default "1d".

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: Date, Open, High, Low, Close, Volume, Dividends, Stock Splits.
        """
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date, interval=interval)

        if data.empty:
            raise ValueError(f"No data found for {symbol} in the given range.")

        # Reset index for cleaner DataFrame output
        data = data.reset_index()

        return data

    # -------------------------------------------------------------------------
    # 2️⃣ Fetch data for multiple stocks
    # -------------------------------------------------------------------------
    def fetch_multiple_stocks(
        self,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple stock symbols.

        Parameters
        ----------
        symbols : List[str]
            List of stock ticker symbols.
        start_date : str or datetime
            Start date for the data.
        end_date : str or datetime
            End date for the data.
        interval : str, optional
            Data interval (e.g., "1d", "1wk", "1mo"), by default "1d".

        Returns
        -------
        Dict[str, pd.DataFrame]
            A dictionary mapping each stock symbol to its corresponding DataFrame.
        """
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.fetch_stock_data(symbol, start_date, end_date, interval)
                print(f"✅ Successfully fetched data for {symbol}")
            except Exception as e:
                print(f"⚠️ Failed to fetch {symbol}: {e}")
        return results

    # -------------------------------------------------------------------------
    # 3️⃣ Fetch general stock information
    # -------------------------------------------------------------------------
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieve general company information from Yahoo Finance.

        Parameters
        ----------
        symbol : str
            Stock ticker symbol.

        Returns
        -------
        Dict[str, Any]
            A dictionary with key information such as:
            - symbol
            - company name
            - sector
            - market capitalization
        """
        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "market_cap": info.get("marketCap", "N/A")
        }


# -------------------------------------------------------------------------
# 4️⃣ Utility function for convenience
# -------------------------------------------------------------------------
def get_popular_stocks() -> List[str]:
    """
    Return a preselected list of popular stock ticker symbols.

    Useful for testing or quick multi-stock downloads.

    Returns
    -------
    List[str]
        A list of commonly traded U.S. stock symbols.
    """
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "PG"]
