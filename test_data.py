# test_data.py
from __future__ import annotations

from datetime import date
from typing import List

import yfinance as yf

from src.db_store import PriceStore


DEFAULT_TICKERS: List[str] = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "JPM", "V", "DIS", "NFLX", "PYPL", "ADBE", "INTC", "CSCO", "CMCSA", "PEP", "COST", "TM", "NKE", "SBUX", "BA", "WMT", "T", "XOM", "CVX"]
START_DATE = "2018-01-01"
END_DATE = date.today().isoformat()
INTERVAL = "1d"


def fetch_and_store(symbols: List[str],
                    start: str = START_DATE,
                    end: str = END_DATE,
                    interval: str = INTERVAL) -> None:
    store = PriceStore("data/prices.db")

    for symbol in symbols:
        symbol = symbol.upper()

        # 🔹 NEW: skip tickers that are already in the DB
        if store.has_ticker(symbol):
            print(f"[test_data] {symbol} already in DB, skipping download.")
            continue

        print(f"[test_data] Downloading {symbol} from Yahoo: {start} → {end} ({interval})")
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            group_by="column",
            auto_adjust=False,
        )
        print(f"[test_data] Rows for {symbol}: {len(df)}")

        store.insert_from_dataframe(symbol, df)

    print("[test_data] Done. Data stored in data/prices.db")


def main() -> None:
    print("Default tickers:", ", ".join(DEFAULT_TICKERS))
    extra = input("Enter extra tickers (comma-separated) or leave blank: ").strip()

    tickers = DEFAULT_TICKERS.copy()
    if extra:
        tickers.extend([t.strip().upper() for t in extra.split(",") if t.strip()])

    fetch_and_store(tickers)


if __name__ == "__main__":
    main()

