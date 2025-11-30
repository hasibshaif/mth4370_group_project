from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd


class PriceStore:
    def __init__(self, db_path: str = "data/prices.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                ticker TEXT NOT NULL,
                ts     TEXT NOT NULL,
                open   REAL,
                high   REAL,
                low    REAL,
                close  REAL,
                volume REAL,
                PRIMARY KEY (ticker, ts)
            )
            """
        )
        self.conn.commit()

    def insert_from_dataframe(self, ticker: str, df: pd.DataFrame) -> None:
        """
        Take a DataFrame from yfinance and insert into the DB.

        Expected:
          - DatetimeIndex with dates
          - Columns like Open, High, Low, Close, Volume, ...
        """
        if df is None or df.empty:
            print(f"[db_store] No data for {ticker}, skipping insert")
            return

        ticker = ticker.upper()

        # --- 0) If this ticker already exists, delete its old rows ---
        # For this project, we treat each download as the "source of truth"
        print(f"[db_store] Deleting existing rows for {ticker} (if any)")
        self.conn.execute("DELETE FROM prices WHERE ticker = ?", (ticker,))
        self.conn.commit()

        # --- 1) Flatten MultiIndex columns if needed ---
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(col[0]) for col in df.columns.to_list()]

        # --- 2) Move index (dates) into a 'ts' column ---
        idx_name = df.index.name or "Date"
        df = df.reset_index().rename(columns={idx_name: "ts"})

        # --- 3) Normalize column names to lowercase strings ---
        cols_lower = {c: str(c).lower() for c in df.columns}
        df = df.rename(columns=cols_lower)

        # --- 4) Ensure price columns exist ---
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = None

        df["ticker"] = ticker

        # --- 5) Only keep the columns we care about ---
        out = df[["ticker", "ts", "open", "high", "low", "close", "volume"]]

        # --- 6) Insert into SQLite (no duplicate PKs now) ---
        out.to_sql(
            "prices",
            self.conn,
            if_exists="append",
            index=False,
        )

    def load_prices(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        query = """
            SELECT ts AS date, open, high, low, close, volume
            FROM prices
            WHERE ticker = ?
        """
        params: list[object] = [ticker.upper()]

        if start is not None:
            query += " AND ts >= ?"
            params.append(start)
        if end is not None:
            query += " AND ts <= ?"
            params.append(end)

        query += " ORDER BY ts ASC"

        df = pd.read_sql(query, self.conn, params=params, parse_dates=["date"])
        return df
