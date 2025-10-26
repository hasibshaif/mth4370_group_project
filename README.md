---
````markdown
# 🧠 Backtesting Engine — Quick Start Guide

This project lets you test trading strategies using real historical stock data.

---

## ⚙️ Step 1 – Fetch the Data

Before running any strategy, you need the stock data files.

Run this once in your terminal:

```bash
python test_data.py
````

✅ What it does:

* Checks if data for `AAPL`, `MSFT`, and `GOOGL` already exists under `data/raw/`
* Downloads missing files automatically from **Yahoo Finance**
* Saves them as:

  ```
  data/raw/AAPL.csv
  data/raw/MSFT.csv
  data/raw/GOOGL.csv
  ```

---

## 💡 Step 2 – Add Your Strategy

Open **`main.py`** — this is where you plug in your trading logic.

Inside the file, you can:

* Load data using the built-in `DataLoader`
* Run it through the `Backtester`
* Create and test your own strategy (for example, buy-and-hold, switch between assets, etc.)

A **strategy** is simply a Python function or code block that:

1. Chooses **what to buy/sell** and **when** using the loaded DataFrame (price data).
2. Returns or prints:

   * The **final portfolio value**
   * The **total return (%)**
   * And a **performance chart** over time (plotted automatically).

---

## 🧾 Step 3 – Run the Simulation

Once your strategy is written, just run:

```bash
python main.py
```

The program will:

* Print the strategy’s total return in the terminal
* Display a chart showing portfolio growth over the chosen period

---

## 🧩 Input & Output Summary

| Type       | Description                                                               |
| ---------- | ------------------------------------------------------------------------- |
| **Input**  | Ticker symbol(s), start/end dates, initial capital, and your custom logic |
| **Output** | Portfolio performance table and a plotted graph of value over time        |
