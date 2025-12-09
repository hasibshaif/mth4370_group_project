import axios from 'axios';

// Use relative URL - Vite proxy will forward to http://localhost:5001/api
const API_BASE_URL = '/api';

export interface BacktestMetrics {
  total_return: number;
  final_value: number;
  initial_capital: number;
  max_drawdown: number;
  max_drawdown_duration_days?: number;
  annualized_return: number | null;
  annualized_vol: number | null;
}

export interface BacktestResponse {
  success: boolean;
  metrics?: BacktestMetrics;
  plot_image?: string;
  error?: string;
}

export interface ComparisonBacktestResult {
  metrics: BacktestMetrics;
  error?: string;
}

export interface ComparisonBacktestResponse {
  success: boolean;
  comparison?: Record<string, ComparisonBacktestResult>;
  plot_image?: string;
  error?: string;
}

export const api = {
  async healthCheck(): Promise<boolean> {
    try {
      const res = await axios.get(`${API_BASE_URL}/health`);
      return res.data.status === 'healthy';
    } catch {
      return false;
    }
  },

  async getAvailableStocks(): Promise<string[]> {
    try {
      const res = await axios.get(`${API_BASE_URL}/stocks`);
      return res.data.success ? res.data.tickers : [];
    } catch {
      return [];
    }
  },

  async runBacktest(
    ticker: string,
    startDate: string,
    endDate: string,
    initialCapital: number,
    strategyCode?: string
  ): Promise<BacktestResponse> {
    try {
      const res = await axios.post<BacktestResponse>(`${API_BASE_URL}/backtest`, {
        ticker,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        strategy_code: strategyCode || '',
      });
      return res.data;
    } catch (err) {
      const error = err as { response?: { data?: { error?: string } }; message?: string };
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Unknown error',
      };
    }
  },

  async runComparisonBacktest(
    tickers: string[],
    startDate: string,
    endDate: string,
    initialCapital: number,
    strategyCode?: string
  ): Promise<ComparisonBacktestResponse> {
    try {
      const res = await axios.post<ComparisonBacktestResponse>(`${API_BASE_URL}/backtest/compare`, {
        tickers,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
        strategy_code: strategyCode || '',
      });
      return res.data;
    } catch (err) {
      const error = err as { response?: { data?: { error?: string } }; message?: string };
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Unknown error',
      };
    }
  },
};
