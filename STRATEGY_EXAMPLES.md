# Custom Strategy Examples

This document provides examples of custom trading strategies you can use in the backtesting frontend.

## Required Function Signature

All custom strategies must define a function named `strategy` with the following signature:

```python
def strategy(df, initial_capital):
    # Your strategy logic here
    return df  # Must return DataFrame with required columns
```

### Input Parameters:
- `df`: pandas DataFrame with columns: `date`, `price`, `open`, `high`, `low`, `close`, `volume`
- `initial_capital`: float representing the starting capital

### Required Output Columns:
- `date`: Trading dates
- `price`: Stock prices
- `shares`: Number of shares held at each date
- `cash`: Cash remaining in portfolio
- `portfolio_value`: Total portfolio value (shares * price + cash)
- `returns_factor` (optional): Normalized returns (portfolio_value / initial_capital)

### Available Libraries:
- `pd` (pandas)
- `np` (numpy)
- `math`

---

## Example 1: Buy and Hold

```python
def strategy(df, initial_capital):
    import math
    
    # Buy on first day
    entry_price = df['price'].iloc[0]
    shares = math.floor(initial_capital / entry_price)
    cash = initial_capital - shares * entry_price
    
    # Hold throughout
    df['shares'] = shares
    df['cash'] = cash
    df['portfolio_value'] = shares * df['price'] + cash
    df['returns_factor'] = df['portfolio_value'] / initial_capital
    
    return df
```

---

## Example 2: Simple Moving Average Crossover

```python
def strategy(df, initial_capital):
    import math
    import pandas as pd
    
    # Calculate moving averages
    df['ma_short'] = df['price'].rolling(window=20).mean()
    df['ma_long'] = df['price'].rolling(window=50).mean()
    
    # Initialize tracking variables
    position = False  # Track if we're currently holding shares
    shares_held = 0
    cash = initial_capital
    
    # Lists to store values for each day
    shares_list = []
    cash_list = []
    portfolio_list = []
    
    for i in range(len(df)):
        if pd.isna(df['ma_short'].iloc[i]) or pd.isna(df['ma_long'].iloc[i]):
            # Not enough data for MAs yet - stay in cash
            shares_list.append(0)
            cash_list.append(initial_capital)
            portfolio_list.append(initial_capital)
            continue
        
        current_price = df['price'].iloc[i]
        
        # Buy signal: short MA crosses above long MA
        if not position and df['ma_short'].iloc[i] > df['ma_long'].iloc[i]:
            shares_held = math.floor(cash / current_price)
            cash = cash - shares_held * current_price
            position = True
        
        # Sell signal: short MA crosses below long MA
        elif position and df['ma_short'].iloc[i] <= df['ma_long'].iloc[i]:
            cash = cash + shares_held * current_price
            shares_held = 0
            position = False
        
        # Record current state
        shares_list.append(shares_held)
        cash_list.append(cash)
        portfolio_list.append(shares_held * current_price + cash)
    
    # Assign to dataframe
    df['shares'] = shares_list
    df['cash'] = cash_list
    df['portfolio_value'] = portfolio_list
    df['returns_factor'] = df['portfolio_value'] / initial_capital
    return df
```

---

## Example 3: RSI Mean Reversion

```python
def strategy(df, initial_capital):
    import math
    import pandas as pd
    
    # Calculate RSI
    period = 14
    delta = df['price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Initialize tracking variables
    position = False
    shares_held = 0
    cash = initial_capital
    
    # Lists to store values for each day
    shares_list = []
    cash_list = []
    portfolio_list = []
    
    for i in range(len(df)):
        if pd.isna(df['rsi'].iloc[i]):
            # Not enough data for RSI yet - stay in cash
            shares_list.append(0)
            cash_list.append(initial_capital)
            portfolio_list.append(initial_capital)
            continue
        
        current_price = df['price'].iloc[i]
        
        # Buy when oversold (RSI < 30)
        if not position and df['rsi'].iloc[i] < 30:
            shares_held = math.floor(cash / current_price)
            cash = cash - shares_held * current_price
            position = True
        
        # Sell when overbought (RSI > 70)
        elif position and df['rsi'].iloc[i] > 70:
            cash = cash + shares_held * current_price
            shares_held = 0
            position = False
        
        # Record current state
        shares_list.append(shares_held)
        cash_list.append(cash)
        portfolio_list.append(shares_held * current_price + cash)
    
    # Assign to dataframe
    df['shares'] = shares_list
    df['cash'] = cash_list
    df['portfolio_value'] = portfolio_list
    df['returns_factor'] = df['portfolio_value'] / initial_capital
    return df
```

---

## Example 4: Volatility Breakout

```python
def strategy(df, initial_capital):
    import math
    import pandas as pd
    
    # Calculate volatility (20-day standard deviation)
    df['volatility'] = df['price'].pct_change().rolling(window=20).std()
    
    # Initialize tracking variables
    position = False
    shares_held = 0
    cash = initial_capital
    entry_price = 0
    
    # Lists to store values for each day
    shares_list = []
    cash_list = []
    portfolio_list = []
    
    for i in range(len(df)):
        if pd.isna(df['volatility'].iloc[i]):
            # Not enough data for volatility yet - stay in cash
            shares_list.append(0)
            cash_list.append(initial_capital)
            portfolio_list.append(initial_capital)
            continue
        
        current_price = df['price'].iloc[i]
        
        # Enter on high volatility (>2%)
        if not position and df['volatility'].iloc[i] > 0.02:
            shares_held = math.floor(cash / current_price)
            cash = cash - shares_held * current_price
            entry_price = current_price
            position = True
        
        # Exit on 5% profit or 3% loss
        elif position:
            pct_change = (current_price - entry_price) / entry_price
            if pct_change >= 0.05 or pct_change <= -0.03:
                cash = cash + shares_held * current_price
                shares_held = 0
                position = False
        
        # Record current state
        shares_list.append(shares_held)
        cash_list.append(cash)
        portfolio_list.append(shares_held * current_price + cash)
    
    # Assign to dataframe
    df['shares'] = shares_list
    df['cash'] = cash_list
    df['portfolio_value'] = portfolio_list
    df['returns_factor'] = df['portfolio_value'] / initial_capital
    return df
```

---

## Tips for Writing Custom Strategies

1. **Always check for NaN values**: Many indicators (MA, RSI, etc.) produce NaN for initial rows
2. **Use integer shares**: `math.floor()` to avoid fractional shares
3. **Track cash separately**: Portfolio value = shares * price + cash
4. **Handle edge cases**: First/last days, no data, etc.
5. **Test incrementally**: Start with simple logic, add complexity gradually
6. **Use `.iloc[i]` for indexing**: More reliable than direct indexing in loops
7. **Set values with `.loc[df.index[i], 'column']`**: Avoid SettingWithCopyWarning

---

## Common Errors and Solutions

### Error: "Strategy must return DataFrame with columns..."
**Solution**: Make sure your strategy returns a DataFrame with all required columns: `date`, `price`, `shares`, `cash`, `portfolio_value`

### Error: "Syntax error in strategy code"
**Solution**: Check for proper indentation, missing colons, unmatched parentheses, etc.

### Error: "'NoneType' object has no attribute..."
**Solution**: Check for division by zero or operations on NaN values. Use `pd.isna()` to check.

### Error: "Can't convert NaN to integer"
**Solution**: Use `pd.isna()` to skip rows with NaN values before calculations.

---

## Advanced: Using Technical Indicators

You can implement more complex indicators like Bollinger Bands, MACD, etc. using pandas operations:

```python
def strategy(df, initial_capital):
    import math
    
    # Bollinger Bands
    window = 20
    df['ma'] = df['price'].rolling(window=window).mean()
    df['std'] = df['price'].rolling(window=window).std()
    df['upper_band'] = df['ma'] + 2 * df['std']
    df['lower_band'] = df['ma'] - 2 * df['std']
    
    # Your trading logic using the bands
    # ...
    
    return df
```

Happy backtesting! 🚀
