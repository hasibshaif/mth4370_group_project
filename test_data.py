# test_data.py
from __future__ import annotations

from datetime import date
from typing import List

import yfinance as yf

from src.db_store import PriceStore


DEFAULT_TICKERS: List[str] = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "JPM", "V", "DIS", "NFLX", "PYPL", "ADBE", "INTC", "CSCO", "CMCSA", "PEP", "COST", "TM", "NKE", "SBUX", "BA", "WMT", "T", "XOM", "CVX"]
DEFAULT_START = "2018-01-01"
DEFAULT_END = date.today().isoformat()


def fetch_and_store(
    tickers: list[str],
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    interval: str = "1d",
) -> None:
    store = PriceStore("data/prices.db")

    for symbol in tickers:
        symbol = symbol.upper().strip()
        if not symbol:
            continue
        print(f"[test_data] Downloading {symbol} from Yahoo: {start} → {end} ({interval})")
        df = yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        group_by="column",   # avoid MultiIndex with ticker level
        auto_adjust=False,   # explicit; avoids the future default confusion
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

    # You can later make these inputs as well if you want
    fetch_and_store(tickers)


if __name__ == "__main__":
    main()
