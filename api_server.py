# api_server.py
"""
Flask API Server for Trading Platform
======================================

This server provides REST API endpoints to serve stock data from pandas DataFrames
to the frontend React application.

Endpoints:
- GET /api/stock/<ticker> - Get stock data for a specific ticker
- GET /api/stock/<ticker>?start=YYYY-MM-DD&end=YYYY-MM-DD - Get filtered stock data
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from src.data_loader import DataLoader
from src.backtester import Backtester
import pandas as pd
from typing import Optional

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Initialize DataLoader and Backtester
loader = DataLoader(data_dir="data/raw")
backtester = Backtester(loader)


def dataframe_to_chart_data(df: pd.DataFrame) -> list:
    """
    Convert pandas DataFrame to JSON format compatible with Recharts.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: date, open, high, low, close, volume, etc.
    
    Returns
    -------
    list
        List of dictionaries with format: [{ date: str, price: float, ... }, ...]
    """
    if df.empty:
        return []
    
    # Convert date to string format for frontend
    df = df.copy()
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    
    # Convert DataFrame to list of dictionaries
    # Include all relevant columns for potential future use
    result = []
    for _, row in df.iterrows():
        data_point = {
            'date': row['date'],
            'price': float(row['close']) if 'close' in row else None,
            'open': float(row['open']) if 'open' in row else None,
            'high': float(row['high']) if 'high' in row else None,
            'low': float(row['low']) if 'low' in row else None,
            'volume': float(row['volume']) if 'volume' in row else None,
        }
        result.append(data_point)
    
    return result


@app.route('/api/stock/<ticker>', methods=['GET'])
def get_stock_data(ticker: str):
    """
    Get stock data for a specific ticker.
    
    Query Parameters:
    - start: Start date (YYYY-MM-DD) - optional
    - end: End date (YYYY-MM-DD) - optional
    
    Returns:
    - JSON array of stock data points
    """
    try:
        # Get optional date filters from query parameters
        start_date = request.args.get('start', None)
        end_date = request.args.get('end', None)
        
        # Load data using DataLoader
        df = loader.load(ticker, start=start_date, end=end_date)
        
        # Convert to chart-friendly format
        chart_data = dataframe_to_chart_data(df)
        
        return jsonify({
            'success': True,
            'ticker': ticker.upper(),
            'data': chart_data,
            'count': len(chart_data)
        })
    
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'message': 'API server is running'})


@app.route('/api/stocks', methods=['GET'])
def get_available_stocks():
    """Get list of available stock tickers."""
    import os
    from pathlib import Path
    
    data_dir = Path("data/raw")
    if not data_dir.exists():
        return jsonify({
            'success': False,
            'error': 'Data directory not found'
        }), 404
    
    # Get all CSV files and extract ticker names
    csv_files = list(data_dir.glob("*.csv"))
    tickers = [f.stem.upper() for f in csv_files]
    
    return jsonify({
        'success': True,
        'tickers': sorted(tickers)
    })


@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    """
    Run a backtest for a given strategy.
    
    Request Body:
    {
        "ticker": "AAPL",
        "strategy_code": "...",  # Currently ignored - uses Buy & Hold
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0
    }
    
    Returns:
    {
        "success": true,
        "results": [
            {"date": "2023-01-01", "portfolio_value": 10000.0, "price": 150.0},
            ...
        ],
        "metrics": {
            "total_return": 0.15,
            "final_value": 11500.0,
            "initial_capital": 10000.0,
            "max_drawdown": -0.05,
            ...
        }
    }
    """
    try:
        data = request.get_json()
        
        # Extract parameters
        ticker = data.get('ticker')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_capital = float(data.get('initial_capital', 10000.0))
        strategy_code = data.get('strategy_code', '')  # Currently ignored
        
        # Validate required fields
        if not ticker:
            return jsonify({
                'success': False,
                'error': 'ticker is required'
            }), 400
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date are required'
            }), 400
        
        # Note: Currently the backend only supports Buy & Hold strategy
        # The strategy_code parameter is accepted but ignored
        # In the future, this could be extended to support custom strategies
        
        # Run the backtest
        df = backtester.run_buy_and_hold(
            ticker=ticker,
            start=start_date,
            end=end_date,
            initial_capital=initial_capital
        )
        
        # Convert DataFrame to results format
        results = []
        for _, row in df.iterrows():
            results.append({
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                'portfolio_value': float(row['portfolio_value']),
                'price': float(row['price'])
            })
        
        # Get performance metrics
        metrics_dict = backtester.summarize_performance(df, initial_capital)
        
        # Generate matplotlib plot and convert to base64
        plot_image_base64 = backtester.plot_results_to_base64(df, ticker)
        
        # Format metrics for frontend
        metrics = {
            'total_return': float(metrics_dict['total_return']),
            'final_value': float(metrics_dict['final_value']),
            'initial_capital': float(initial_capital),
            'max_drawdown': float(metrics_dict['max_drawdown']),
            'max_drawdown_duration_days': int(metrics_dict.get('max_drawdown_duration_days', 0)),
            'annualized_return': float(metrics_dict['annualized_return']) if not pd.isna(metrics_dict['annualized_return']) else None,
            'annualized_vol': float(metrics_dict['annualized_vol']) if not pd.isna(metrics_dict['annualized_vol']) else None,
        }
        
        return jsonify({
            'success': True,
            'results': results,
            'metrics': metrics,
            'plot_image': plot_image_base64  # Base64-encoded matplotlib PNG
        })
    
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/compare', methods=['POST'])
def run_comparison_backtest():
    """
    Run a backtest comparison for multiple tickers.
    
    Request Body:
    {
        "tickers": ["AAPL", "MSFT", "GOOGL"],
        "strategy_code": "...",  # Currently ignored - uses Buy & Hold
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0
    }
    
    Returns:
    {
        "success": true,
        "comparison": {
            "AAPL": {
                "results": [...],
                "metrics": {...}
            },
            "MSFT": {
                "results": [...],
                "metrics": {...}
            },
            ...
        },
        "normalized_results": [
            {"date": "2023-01-01", "AAPL": 1.0, "MSFT": 1.0, ...},
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        
        # Extract parameters
        tickers = data.get('tickers', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_capital = float(data.get('initial_capital', 10000.0))
        strategy_code = data.get('strategy_code', '')  # Currently ignored
        
        # Validate required fields
        if not tickers or not isinstance(tickers, list) or len(tickers) == 0:
            return jsonify({
                'success': False,
                'error': 'tickers must be a non-empty list'
            }), 400
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'start_date and end_date are required'
            }), 400
        
        # Run backtest for each ticker and store DataFrames for plotting
        comparison_results = {}
        all_dates = set()
        results_by_ticker_for_plot = {}  # Store DataFrames to reuse for plotting
        
        for ticker in tickers:
            try:
                df = backtester.run_buy_and_hold(
                    ticker=ticker,
                    start=start_date,
                    end=end_date,
                    initial_capital=initial_capital
                )
                
                # Store DataFrame for plotting
                results_by_ticker_for_plot[ticker] = df
                
                # Convert DataFrame to results format
                results = []
                for _, row in df.iterrows():
                    date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])
                    all_dates.add(date_str)
                    results.append({
                        'date': date_str,
                        'portfolio_value': float(row['portfolio_value']),
                        'price': float(row['price']),
                        'returns_factor': float(row.get('returns_factor', row['portfolio_value'] / initial_capital))
                    })
                
                # Get performance metrics
                metrics_dict = backtester.summarize_performance(df, initial_capital)
                
                metrics = {
                    'total_return': float(metrics_dict['total_return']),
                    'final_value': float(metrics_dict['final_value']),
                    'initial_capital': float(initial_capital),
                    'max_drawdown': float(metrics_dict['max_drawdown']),
                    'max_drawdown_duration_days': int(metrics_dict.get('max_drawdown_duration_days', 0)),
                    'annualized_return': float(metrics_dict['annualized_return']) if not pd.isna(metrics_dict['annualized_return']) else None,
                    'annualized_vol': float(metrics_dict['annualized_vol']) if not pd.isna(metrics_dict['annualized_vol']) else None,
                }
                
                comparison_results[ticker] = {
                    'results': results,
                    'metrics': metrics
                }
                
            except Exception as e:
                # Log error but continue with other tickers
                comparison_results[ticker] = {
                    'error': str(e)
                }
        
        # Create normalized comparison data (all starting at 1.0)
        sorted_dates = sorted(all_dates)
        normalized_results = []
        
        for date in sorted_dates:
            point = {'date': date}
            for ticker in tickers:
                if ticker in comparison_results and 'results' in comparison_results[ticker]:
                    # Find the result for this date
                    ticker_results = comparison_results[ticker]['results']
                    matching_result = next((r for r in ticker_results if r['date'] == date), None)
                    if matching_result:
                        point[ticker] = matching_result['returns_factor']
            if len(point) > 1:  # Has at least one ticker value
                normalized_results.append(point)
        
        # Generate comparison plot using matplotlib and convert to base64
        # Use the stored DataFrames (no need to re-run backtests)
        plot_image_base64 = None
        if results_by_ticker_for_plot:
            try:
                plot_image_base64 = backtester.plot_comparison_to_base64(results_by_ticker_for_plot)
            except Exception as e:
                # Plot generation failed, but we can still return the data
                import traceback
                print(f"Error generating plot: {e}")
                traceback.print_exc()
        
        return jsonify({
            'success': True,
            'comparison': comparison_results,
            'normalized_results': normalized_results,
            'plot_image': plot_image_base64  # Base64-encoded matplotlib PNG
        })
    
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("🚀 Starting Flask API server...")
    print("📊 Available endpoints:")
    print("   - GET /api/health - Health check")
    print("   - GET /api/stocks - List available tickers")
    print("   - GET /api/stock/<ticker> - Get stock data")
    print("   - GET /api/stock/<ticker>?start=YYYY-MM-DD&end=YYYY-MM-DD - Get filtered data")
    print("   - POST /api/backtest - Run backtest (Buy & Hold strategy)")
    print("   - POST /api/backtest/compare - Run comparison backtest for multiple tickers")
    print("\n🌐 Server running on http://localhost:5001")
    app.run(debug=True, port=5001, host='127.0.0.1')

