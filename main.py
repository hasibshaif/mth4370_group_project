# main.py
import matplotlib.pyplot as plt
from src.data_loader import DataLoader
from src.backtester import Backtester


def compute_return(df):
    """Helper function: compute percentage return from first to last portfolio value."""
    if df["portfolio_value"].iloc[0] == 0:
        return 0.0
    return (df["portfolio_value"].iloc[-1] / df["portfolio_value"].iloc[0] - 1) * 100


def main():
    loader = DataLoader()
    backtester = Backtester(loader)

    # Use the same time range for all strategies
    start_date = "2024-10-28"
    end_date = "2024-12-24"
    initial_capital = 1000

    print(f"Running all strategies from {start_date} to {end_date}...\n")

    # === STRATEGY 1: Buy & Hold AAPL ===
    aapl = backtester.run_buy_and_hold("AAPL", start=start_date, end=end_date, initial_capital=initial_capital)
    print(f"Strategy 1 - AAPL Buy & Hold: {compute_return(aapl):.2f}%")

    # === STRATEGY 2: Buy & Hold MSFT ===
    msft = backtester.run_buy_and_hold("MSFT", start=start_date, end=end_date, initial_capital=initial_capital)
    print(f"Strategy 2 - MSFT Buy & Hold: {compute_return(msft):.2f}%")

    # === STRATEGY 3: 50/50 Portfolio of AAPL + MSFT ===
    min_len = min(len(aapl), len(msft))
    combined = aapl.iloc[:min_len].copy()
    combined["portfolio_value"] = (
        aapl["portfolio_value"].iloc[:min_len] / 2 + msft["portfolio_value"].iloc[:min_len] / 2
    )
    print(f"Strategy 3 - 50/50 AAPL+MSFT Portfolio: {compute_return(combined):.2f}%")

    # === STRATEGY 4: Switch from AAPL to MSFT halfway ===
    midpoint = min_len // 2
    switch = aapl.iloc[:min_len].copy()

    # align both dataframes
    aapl_aligned = aapl.iloc[:min_len].reset_index(drop=True)
    msft_aligned = msft.iloc[:min_len].reset_index(drop=True)

    switch["portfolio_value"] = 0.0
    # First half = AAPL performance
    switch.loc[:midpoint, "portfolio_value"] = aapl_aligned["portfolio_value"].iloc[:midpoint + 1].values

    # Second half = MSFT performance, scaled to AAPL value at midpoint
    if midpoint < len(msft_aligned):
        msft_slice = msft_aligned["portfolio_value"].iloc[midpoint:].reset_index(drop=True)
        msft_base = msft_aligned["portfolio_value"].iloc[midpoint]
        scale = aapl_aligned["portfolio_value"].iloc[midpoint] / msft_base
        switch.loc[midpoint:, "portfolio_value"] = msft_slice.values * scale

    switch = switch.dropna().reset_index(drop=True)
    print(f"Strategy 4 - Switch AAPL → MSFT halfway: {compute_return(switch):.2f}%")

    # === PLOT ALL STRATEGIES TOGETHER ===
    plt.figure(figsize=(10, 6))
    plt.plot(aapl["date"], aapl["portfolio_value"], label=f"AAPL Buy & Hold ({compute_return(aapl):.2f}%)")
    plt.plot(msft["date"], msft["portfolio_value"], label=f"MSFT Buy & Hold ({compute_return(msft):.2f}%)")
    plt.plot(combined["date"], combined["portfolio_value"], label=f"50/50 Portfolio ({compute_return(combined):.2f}%)")
    plt.plot(switch["date"], switch["portfolio_value"], label=f"AAPL→MSFT Switch ({compute_return(switch):.2f}%)")

    plt.title("Multi-Strategy Comparison (Aligned Dates)")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    print("\n✅ Simulation complete — all strategies aligned and plotted successfully.")


if __name__ == "__main__":
    main()
