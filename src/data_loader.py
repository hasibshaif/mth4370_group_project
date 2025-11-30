# src/data_loader.py
from __future__ import annotations

from typing import Optional, Dict, Tuple

import pandas as pd

from .db_store import PriceStore


class DataLoader:
    """
    Data loader that reads historical prices from a SQLite DB
    via PriceStore and returns a normalized DataFrame with:

        - 'date' column (datetime)
        - 'close' column (float)

    so Backtester does not have to change.
    """

    def __init__(self, db_path: str = "data/prices.db") -> None:
        self.store = PriceStore(db_path=db_path)
        self._cache: Dict[Tuple[str, Optional[str], Optional[str]], pd.DataFrame] = {}

    def load(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        key = (ticker.upper(), start, end)
        if key in self._cache:
            return self._cache[key].copy()

        df = self.store.load_prices(ticker, start=start, end=end)

        # Normalize column names
        cols_lower = {c: c.lower() for c in df.columns}
        df = df.rename(columns=cols_lower)

        # Make sure we have a 'date' column
        if "date" not in df.columns:
            raise ValueError("Expected a 'date' column from DB query")

        # Ensure 'close' exists and is numeric
        if "close" not in df.columns:
            # fallbacks if needed
            for alt in ["adj close", "price"]:
                if alt in df.columns:
                    df["close"] = df[alt]
                    break
            else:
                raise ValueError("No 'close' column available for price series")

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])

        # Optional: set index for convenience
        df = df.sort_values("date")
        df = df.reset_index(drop=True)

        self._cache[key] = df.copy()
        return df
