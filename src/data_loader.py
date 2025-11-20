from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

# Default directory where test_data.py saves CSV files
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _read_csv_smart(file_path: Path) -> pd.DataFrame:
    """
    Read a price CSV once and try to build a sensible DataFrame.

    Goals:
    - Handle both Yahoo Finance-style CSVs and the professor's provided CSVs.
    - Normalize column names to lower-case (so we can always use 'close', 'date').
    - Build a DatetimeIndex when a date column exists.
    """

    print(f"[load_price_data] Looking for file: {file_path}")

    # Single disk read, no header
    df_raw = pd.read_csv(file_path, header=None)
    print(f"[load_price_data] Raw shape (including first row): {df_raw.shape}")

    # --- 1) Detect header row (we assume the first row is header if it has text) ---
    first_row = df_raw.iloc[0].astype(str).str.strip().tolist()

    def looks_like_header_cell(x: str) -> bool:
        # If it can't be parsed as a number, treat as header-ish text
        try:
            float(x.replace(",", ""))
            return False
        except ValueError:
            return True

    has_any_text = any(looks_like_header_cell(x) for x in first_row)

    if has_any_text:
        header = [str(x).strip() for x in first_row]
        df = df_raw.iloc[1:].copy()
        df.columns = header
        print(f"[load_price_data] Detected header row: {header}")
        print(f"[load_price_data] Preview shape: {df.shape}")
        print(f"[load_price_data] Preview columns: {list(df.columns)}")
    else:
        df = df_raw.copy()
        df.columns = [f"col_{i}" for i in range(df.shape[1])]
        print(
            "[load_price_data] No header row detected, using generic "
            f"column names: {list(df.columns)}"
        )

    # --- 2) Special-case: files where the *first* column is actually a date
    #     but is labeled 'Price' and real prices are in 'Close'.
    header_lower = [c.strip().lower() for c in df.columns]
    if (
        len(header_lower) >= 2
        and header_lower[0] == "price"
        and "close" in header_lower
        and "open" in header_lower
    ):
        # Treat the first column as a date column
        old_first = df.columns[0]
        df.rename(columns={old_first: "date"}, inplace=True)
        print(
            "[load_price_data] Heuristic: treating first column 'Price' as 'date' "
            "because file also has 'Close' and 'Open' columns."
        )

    # --- 3) Normalize column names to lower-case for consistency ---
    df.columns = [c.strip().lower() for c in df.columns]

    # --- 4) Try to build a DatetimeIndex ---
    date_col_name: Optional[str] = None

    # Prefer an explicit 'date' column if present
    if "date" in df.columns:
        date_col_name = "date"
    else:
        # Otherwise, see if the first column looks like dates
        candidate = df.columns[0]
        try:
            parsed = pd.to_datetime(df[candidate], errors="coerce")
            non_null_ratio = parsed.notna().mean()
            if non_null_ratio > 0.5:  # at least half of the rows look like dates
                date_col_name = candidate
        except Exception:
            date_col_name = None

    if date_col_name is not None:
        parsed = pd.to_datetime(df[date_col_name], errors="coerce")
        valid_mask = parsed.notna()
        if valid_mask.any():
            # Keep only rows with a valid date
            df = df.loc[valid_mask].copy()
            df[date_col_name] = parsed[valid_mask]
            df.set_index(date_col_name, inplace=True)
            df.sort_index(inplace=True)
            print(
                f"[load_price_data] Parsed '{date_col_name}' column as DatetimeIndex "
                f"({valid_mask.sum()} valid rows)."
            )
        else:
            print(
                "[load_price_data] Tried to parse a date column but no valid dates "
                "were found; keeping default index."
            )
    else:
        print(
            "[load_price_data] No suitable date column found; "
            "keeping default index (no date filtering)."
        )

    # --- 5) Guarantee a 'date' column for plotting/backtester ---
    if isinstance(df.index, pd.DatetimeIndex):
        df["date"] = df.index

    # --- 6) Guarantee a 'close' column for price-based strategies ---
    cols = set(df.columns)
    if "close" not in cols:
        # Fall back to 'adj close' or 'price' if available
        if "adj close" in cols:
            df["close"] = df["adj close"]
            print("[load_price_data] Using 'adj close' column as 'close'.")
        elif "price" in cols:
            df["close"] = df["price"]
            print("[load_price_data] Using 'price' column as 'close'.")
        else:
            raise KeyError(
                "Could not find a 'close' price column in the data. "
                f"Available columns: {list(df.columns)}"
            )

    # Ensure close is numeric
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df[df["close"].notna()]

    return df


@lru_cache(maxsize=None)
def load_price_data(ticker: str) -> pd.DataFrame:
    """
    Public helper used by the rest of the project.

    - Loads data from data/raw/{TICKER}.csv
    - Uses an in-memory cache so each ticker is only read once per run.
    """
    file_path = DATA_DIR / f"{ticker}.csv"

    if not file_path.exists():
        raise FileNotFoundError(
            f"[load_price_data] CSV for ticker '{ticker}' not found at {file_path}"
        )

    return _read_csv_smart(file_path)


class DataLoader:
    """
    Wrapper used by Backtester and main.py.

    Your existing code like:

        loader = DataLoader()
        df = loader.load(ticker, start=..., end=...)

    or

        loader = DataLoader("data/raw")

    will work with this implementation.
    """

    def __init__(self, data_dir: Optional[str | Path] = None) -> None:
        # Always store this as a Path, even if a string is passed
        if data_dir is None:
            self.data_dir = DATA_DIR
        else:
            self.data_dir = Path(data_dir)

    def load_price_data(self, ticker: str) -> pd.DataFrame:
        # If using the default directory, reuse the cached function above
        if self.data_dir == DATA_DIR:
            return load_price_data(ticker)

        # Custom directory (no cache)
        file_path = self.data_dir / f"{ticker}.csv"

        if not file_path.exists():
            raise FileNotFoundError(
                f"[DataLoader] CSV for ticker '{ticker}' not found at {file_path}"
            )

        return _read_csv_smart(file_path)

    def load(
        self,
        ticker: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load data for a ticker and optionally filter by [start, end] (inclusive).

        - If the index is a DatetimeIndex, start/end are treated as dates.
        - If not, we just return the full DataFrame.
        """
        df = self.load_price_data(ticker)

        if isinstance(df.index, pd.DatetimeIndex):
            if start is not None:
                df = df[df.index >= pd.to_datetime(start)]
            if end is not None:
                df = df[df.index <= pd.to_datetime(end)]
        else:
            print(
                "[DataLoader.load] Warning: index is not DatetimeIndex; "
                "ignoring start/end filters."
            )

        return df
    