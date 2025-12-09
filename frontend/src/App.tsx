import { useState, useEffect } from 'react';
import { api } from './api';
import type { BacktestResponse, BacktestMetrics, ComparisonBacktestResponse } from './api';
import './App.css';

function App() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [mode, setMode] = useState<'single' | 'compare'>('single');
  const [selectedTicker, setSelectedTicker] = useState('TSLA');
  const [compareTickers, setCompareTickers] = useState(['AAPL', 'MSFT', 'GOOGL']);
  const [startDate, setStartDate] = useState('2023-01-03');
  const [endDate, setEndDate] = useState('2023-01-17');
  const [capital, setCapital] = useState(10000);
  const [strategyCode, setStrategyCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<BacktestMetrics | null>(null);
  const [comparison, setComparison] = useState<ComparisonBacktestResponse | null>(null);
  const [plotImage, setPlotImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const init = async () => {
      const isHealthy = await api.healthCheck();
      setConnected(isHealthy);
      
      if (isHealthy) {
        const available = await api.getAvailableStocks();
        setTickers(available);
        if (available.length > 0 && !available.includes(selectedTicker)) {
          setSelectedTicker(available[0]);
        }
        setCompareTickers(prev => {
          const valid = prev.filter(t => available.includes(t));
          return valid.length === 0 && available.length >= 4 
            ? available.slice(0, 4) 
            : valid.slice(0, 8);
        });
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runBacktest = async () => {
    if (mode === 'single') {
      if (!selectedTicker || !startDate || !endDate || capital <= 0) {
        setError('Please fill in all required fields');
        return;
      }

      setLoading(true);
      setError(null);
      setMetrics(null);
      setComparison(null);
      setPlotImage(null);

      try {
        const res: BacktestResponse = await api.runBacktest(
          selectedTicker,
          startDate,
          endDate,
          capital,
          strategyCode
        );

        if (res.success && res.metrics) {
          setMetrics(res.metrics);
          if (res.plot_image) {
            setPlotImage(`data:image/png;base64,${res.plot_image}`);
          }
        } else {
          setError(res.error || 'Backtest failed');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    } else {
      if (!compareTickers.length || !startDate || !endDate || capital <= 0) {
        setError('Please select at least one ticker and fill in all required fields');
        return;
      }

      setLoading(true);
      setError(null);
      setMetrics(null);
      setComparison(null);
      setPlotImage(null);

      try {
        const res: ComparisonBacktestResponse = await api.runComparisonBacktest(
          compareTickers,
          startDate,
          endDate,
          capital,
          strategyCode
        );

        if (res.success && res.comparison) {
          setComparison(res);
          if (res.plot_image) {
            setPlotImage(`data:image/png;base64,${res.plot_image}`);
          }
        } else {
          setError(res.error || 'Comparison failed');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    }
  };

  const removeTicker = (t: string) => {
    setCompareTickers(compareTickers.filter(ticker => ticker !== t));
  };

  const formatCurrency = (n: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  };

  const formatPercent = (n: number | null) => {
    if (n === null || isNaN(n)) return 'N/A';
    return `${(n * 100).toFixed(2)}%`;
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Backtesting Engine Dashboard</h1>
        <div className={`api-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '🟢 API Connected' : '🔴 API Disconnected'}
        </div>
      </header>

      <div className="dashboard-layout">
        <div className="config-panel">
          <h2>Strategy Configuration</h2>
          
          <div className="form-group">
            <label>Backtest Mode</label>
            <div className="mode-toggle">
              <button
                className={`mode-button ${mode === 'single' ? 'active' : ''}`}
                onClick={() => {
                  setMode('single');
                  setComparison(null);
                }}
              >
                Single Ticker
              </button>
              <button
                className={`mode-button ${mode === 'compare' ? 'active' : ''}`}
                onClick={() => {
                  setMode('compare');
                  setMetrics(null);
                }}
              >
                Comparison
              </button>
            </div>
          </div>

          {mode === 'single' ? (
            <div className="form-group">
              <label htmlFor="ticker">Ticker Symbol *</label>
              <select
                id="ticker"
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                disabled={!connected || tickers.length === 0}
              >
                {tickers.length === 0 ? (
                  <option>Loading...</option>
                ) : (
                  tickers.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))
                )}
              </select>
            </div>
          ) : (
            <div className="form-group">
              <label>Comparison Tickers *</label>
              <p className="helper-text">Select multiple tickers to compare (up to 8)</p>
              <div className="ticker-chips">
                {compareTickers.map(t => (
                  <div key={t} className="ticker-chip">
                    <span>{t}</span>
                    <button
                      type="button"
                      className="chip-remove"
                      onClick={() => removeTicker(t)}
                    >
                      ×
                    </button>
                  </div>
                ))}
                {compareTickers.length < 8 && (
                  <select
                    className="ticker-select-add"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        setCompareTickers([...compareTickers, e.target.value]);
                        e.target.value = '';
                      }
                    }}
                  >
                    <option value="">+ Add Ticker</option>
                    {tickers
                      .filter(t => !compareTickers.includes(t))
                      .map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                  </select>
                )}
              </div>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="startDate">Start Date *</label>
              <input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="endDate">End Date *</label>
              <input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="initialCapital">Initial Capital ($) *</label>
            <input
              id="initialCapital"
              type="number"
              min="1"
              step="100"
              value={capital}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 0)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="strategyCode">Custom Strategy Code (Optional)</label>
            <p className="helper-text">
              Define a function named <code>strategy(df, initial_capital)</code> that returns a DataFrame with columns: date, price, shares, cash, portfolio_value. Leave blank for Buy & Hold.
            </p>
            <textarea
              id="strategyCode"
              rows={10}
              value={strategyCode}
              onChange={(e) => setStrategyCode(e.target.value)}
              placeholder={`# Example: Simple Buy & Hold
def strategy(df, initial_capital):
    import math
    entry_price = df['price'].iloc[0]
    shares = math.floor(initial_capital / entry_price)
    cash = initial_capital - shares * entry_price
    
    df['shares'] = shares
    df['cash'] = cash
    df['portfolio_value'] = shares * df['price'] + cash
    df['returns_factor'] = df['portfolio_value'] / initial_capital
    
    return df`}
            />
          </div>

          <button
            className="run-button"
            onClick={runBacktest}
            disabled={loading || !connected}
          >
            {loading ? '⏳ Running...' : '▶️ Run Backtest'}
          </button>

          {error && (
            <div className="error-message">❌ {error}</div>
          )}
        </div>

        <div className="results-panel">
          {!metrics && !comparison && !loading && (
            <div className="empty-state">
              <h3>Welcome to the Backtesting Engine</h3>
              <p>Configure your strategy parameters and click "Run Backtest" to see results.</p>
            </div>
          )}

          {loading && (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Running backtest...</p>
            </div>
          )}

          {mode === 'single' && metrics && (
            <>
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-label">Initial Capital</div>
                  <div className="metric-value">{formatCurrency(metrics.initial_capital)}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Final Value</div>
                  <div className="metric-value">{formatCurrency(metrics.final_value)}</div>
                </div>
                <div className="metric-card highlight">
                  <div className="metric-label">Total Return</div>
                  <div className={`metric-value ${metrics.total_return >= 0 ? 'positive' : 'negative'}`}>
                    {formatPercent(metrics.total_return)}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Annualized Return</div>
                  <div className={`metric-value ${metrics.annualized_return && metrics.annualized_return >= 0 ? 'positive' : 'negative'}`}>
                    {formatPercent(metrics.annualized_return)}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Annualized Volatility</div>
                  <div className="metric-value">{formatPercent(metrics.annualized_vol)}</div>
                </div>
                <div className="metric-card highlight negative">
                  <div className="metric-label">Max Drawdown</div>
                  <div className="metric-value negative">{formatPercent(metrics.max_drawdown)}</div>
                </div>
                {metrics.max_drawdown_duration_days !== undefined && (
                  <div className="metric-card">
                    <div className="metric-label">Max DD Duration</div>
                    <div className="metric-value">{metrics.max_drawdown_duration_days} days</div>
                  </div>
                )}
              </div>

              {plotImage && (
                <div className="chart-container">
                  <h3>Portfolio Value Over Time</h3>
                  <div className="plot-image-container">
                    <img 
                      src={plotImage} 
                      alt={`Buy & Hold Strategy for ${selectedTicker}`}
                      className="plot-image"
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {mode === 'compare' && comparison && (
            <>
              <div className="comparison-metrics">
                <h3>Performance Comparison</h3>
                <table className="metrics-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Total Return</th>
                      <th>Final Value</th>
                      <th>Annualized Return</th>
                      <th>Annualized Vol</th>
                      <th>Max Drawdown</th>
                      <th>Max DD Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(comparison.comparison || {}).map(([ticker, result]) => {
                      if (result.error) {
                        return (
                          <tr key={ticker}>
                            <td>{ticker}</td>
                            <td colSpan={6} className="error-cell">Error: {result.error}</td>
                          </tr>
                        );
                      }
                      const m = result.metrics;
                      return (
                        <tr key={ticker}>
                          <td><strong>{ticker}</strong></td>
                          <td className={m.total_return >= 0 ? 'positive' : 'negative'}>
                            {formatPercent(m.total_return)}
                          </td>
                          <td>{formatCurrency(m.final_value)}</td>
                          <td className={m.annualized_return && m.annualized_return >= 0 ? 'positive' : 'negative'}>
                            {formatPercent(m.annualized_return)}
                          </td>
                          <td>{formatPercent(m.annualized_vol)}</td>
                          <td className="negative">{formatPercent(m.max_drawdown)}</td>
                          <td>{m.max_drawdown_duration_days || 0} days</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {plotImage && (
                <div className="chart-container">
                  <h3>Normalized Portfolio Value Comparison</h3>
                  <div className="plot-image-container">
                    <img 
                      src={plotImage} 
                      alt="Buy & Hold Comparison Across Tickers"
                      className="plot-image"
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
