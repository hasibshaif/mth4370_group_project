from pathlib import Path

import yfinance as yf

# Core tickers we always keep up to date
CORE_TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA"]


def ask_for_extra_tickers() -> list[str]:
    """
    Ask the user if they want to download/update extra tickers.
    Returns a list of extra tickers (uppercase), possibly empty.
    """
    print("Core tickers that will be updated:", ", ".join(CORE_TICKERS))
    raw = input(
        "Enter any EXTRA tickers to download/update (comma-separated), "
        "or just press Enter to skip: "
    ).strip()

    if not raw:
        return []

    # Split by comma, strip spaces, uppercase, and remove empties
    extras = [t.strip().upper() for t in raw.split(",")]
    extras = [t for t in extras if t]  # remove empty strings

    # Remove any that are already in core list
    extras = [t for t in extras if t not in CORE_TICKERS]

    return extras


def download_and_save_ticker(ticker: str, data_dir: Path, start_date: str = "2015-01-01"):
    """
    Download daily data for a single ticker from yfinance and save to CSV.
    Always overwrites the existing file so data stays fresh.
    """
    out_path = data_dir / f"{ticker}.csv"
    print(f"\nDownloading {ticker} data starting from {start_date}...")

    data = yf.download(ticker, start=start_date)

    if data.empty:
        print(f"  ⚠ No data returned for {ticker}. Skipping.")
        return

    data.to_csv(out_path)
    print(f"  ✅ Saved {ticker} data to {out_path}")


def main():
    data_dir = Path("data/raw")
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1) Ask user for extra tickers
    extra_tickers = ask_for_extra_tickers()

    # 2) Build full list (core + extras)
    all_tickers = CORE_TICKERS + extra_tickers

    print("\nTickers that will be updated:")
    for t in all_tickers:
        print(" -", t)

    # 3) Download/update each ticker
    for ticker in all_tickers:
        try:
            download_and_save_ticker(ticker, data_dir)
        except Exception as e:
            print(f"  ❌ Error while downloading {ticker}: {e}")


if __name__ == "__main__":
    main()
