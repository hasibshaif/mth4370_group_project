from data_acquisition import YahooFinanceDataFetcher
from datetime import datetime, timedelta
import pandas as pd


def main():
    fetcher = YahooFinanceDataFetcher()
    
    # Fetch AAPL data for last year
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    print("Fetching AAPL data...")
    data = fetcher.fetch_stock_data('AAPL', start_date, end_date)
    print(f"Got {len(data)} records")
    print(data.head())
    
    # Save to CSV
    data.to_csv('aapl_data.csv')
    print("Saved to aapl_data.csv")
    
    # Fetch multiple stocks
    symbols = ['AAPL', 'MSFT', 'GOOGL']
    print(f"\nFetching data for {symbols}...")
    multi_data = fetcher.fetch_multiple_stocks(symbols, start_date, end_date)
    
    for symbol, df in multi_data.items():
        print(f"{symbol}: {len(df)} records, latest close: ${df['Close'].iloc[-1]:.2f}")
        df.to_csv(f'{symbol.lower()}_data.csv')


if __name__ == "__main__":
    main()
