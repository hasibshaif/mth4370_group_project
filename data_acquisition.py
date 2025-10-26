import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict, Any


class YahooFinanceDataFetcher:
    
    def __init__(self):
        self.session = None
        
    def fetch_stock_data(self, symbol: str, start_date: Union[str, datetime], 
                        end_date: Union[str, datetime], interval: str = "1d") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        data = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if data.empty:
            raise ValueError(f"No data found for {symbol}")
        
        return data
    
    def fetch_multiple_stocks(self, symbols: List[str], start_date: Union[str, datetime], 
                             end_date: Union[str, datetime], interval: str = "1d") -> Dict[str, pd.DataFrame]:
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.fetch_stock_data(symbol, start_date, end_date, interval)
            except Exception as e:
                print(f"Failed to fetch {symbol}: {e}")
        return results
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            'symbol': symbol,
            'name': info.get('longName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'market_cap': info.get('marketCap', 'N/A')
        }
    
def get_popular_stocks():
    return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'V', 'PG']
