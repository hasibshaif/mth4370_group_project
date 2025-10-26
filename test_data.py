# test_data.py
"""
Test Data Fetcher
=================

This script tests the Yahoo Finance data acquisition system.

It downloads stock data for one or multiple tickers, prints summary stats,
and saves the results as CSV files. You can run this script independently
to verify that your Yahoo Finance connection works and that data is being
stored correctly for later backtesting.

Usage:
------
Run from the command line:
    python test_data.py

Output:
-------
- Prints summary info for each ticker
- Saves CSV files like:
    data/raw/aapl_data.csv
    data/raw/msft_data.csv
    data/raw/googl_data.csv
"""
# --- Auto-install yfinance if missing ---
try:
    import yfinance
except ImportError:
    import subprocess, sys
    print("📦 yfinance not found — installing automatically...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance
import yfinance as yf
from src.data_acquisition import YahooFinanceDataFetcher
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path


def main():
    """
    Main test function for downloading and saving stock data.
    """

    # Initialize fetcher
    fetcher = YahooFinanceDataFetcher()

    # --- Date range: last 1 year ---
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    # --- Ensure data/raw folder exists ---
    Path("data/raw").mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # 1️⃣ Fetch and save single stock (AAPL)
    # -------------------------------------------------------------------------
    print("📈 Fetching AAPL data for the last 12 months...\n")
    data = fetcher.fetch_stock_data("AAPL", start_date, end_date)

    print(f"✅ Retrieved {len(data)} records for AAPL")
    print(data.head(), "\n")

    # Save to CSV (recommended to store under data/raw/)
    data.to_csv("data/raw/AAPL.csv", index=False)
    print("💾 Saved AAPL data → data/raw/AAPL.csv\n")

    # -------------------------------------------------------------------------
    # 2️⃣ Fetch and save multiple stocks
    # -------------------------------------------------------------------------
    symbols = ["AAPL", "MSFT", "GOOGL"]
    print(f"📊 Fetching data for multiple tickers: {symbols}\n")

    multi_data = fetcher.fetch_multiple_stocks(symbols, start_date, end_date)

    # Loop through and print summary
    for symbol, df in multi_data.items():
        latest_close = df["Close"].iloc[-1]
        print(f"✅ {symbol}: {len(df)} records — Latest Close: ${latest_close:.2f}")

        # Save each file
        save_path = f"data/raw/{symbol.upper()}.csv"
        df.to_csv(save_path, index=False)
        print(f"💾 Saved {symbol.upper()} data → {save_path}")

    print("\n🎉 All data successfully fetched and saved!")


if __name__ == "__main__":
    main()