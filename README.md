# Trading System Validator (FactorLab)

> **一个完全离线、本地的交易规则统计验证平台。**
>
> *A fully offline, local platform for validating trading rules with statistical rigor.*

---

## What Is This?

Trading System Validator answers one question:

> **Does a trading rule have a statistical edge?**

It does NOT trade, connect to exchanges, or manage money. It replays historical data through your rules and tells you the win rate, profit factor, expectancy, and drawdown — so you know whether your idea is worth pursuing before risking a single dollar.

## Features

| Feature | Description |
|---------|-------------|
| 🔌 **Plugin Architecture** | Add new indicators as single-file plugins — zero changes to the engine |
| 📐 **Visual Rule Builder** | Build entry rules with AND/OR nesting, no coding required |
| 🔍 **Batch Scanner** | Scan thousands of candles across multiple symbols automatically |
| 📊 **Full Statistics** | Win rate, profit factor, expectancy, max drawdown, equity curve, return distribution |
| 🎯 **Dynamic SL/TP** | Bollinger midline TP, ATR trailing stops, bar-extreme SL, and more — each as a pluggable strategy |
| 🎛️ **Trade Filter** | Filter trades by any indicator value to find optimal conditions |
| 🌐 **Bilingual** | Chinese / English toggle — every label switches instantly |
| 💾 **Local-First** | Parquet + SQLite, zero dependencies on cloud services |

## Quick Start

### Prerequisites

- Python 3.11+
- Git

### Install

```bash
git clone https://github.com/Quirt-studio/Trading-System-Validator.git
cd Trading-System-Validator
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Run

```bash
streamlit run main.py
```

Open `http://localhost:8501` in your browser.

### 5-Minute Walkthrough

#### 1. Download Data

Open the **Binance** page (🌐 tab in sidebar), select a symbol (e.g. `BTCUSDT`) and interval (`4h`), click download. Data is saved to `data/raw/` as Parquet files.

#### 2. Build a Rule

Go to the **Rule Builder** (🔧 tab). Select a feature like `ema` → operator `>` → value `0` → click **Add Condition**. Add more conditions with AND/OR logic. Click **Save Rule** to store it as JSON.

#### 3. Run a Scan

Go to the **Scanner** (🔍 tab). Select your dataset, choose the rule you just built, pick SL/TP strategies (e.g. `ATRSL` + `FixedRRTP`), and click **Run Scan**.

#### 4. Read Results

You'll see:
- **Summary cards**: total trades, win rate, profit factor, expectancy, max drawdown
- **Equity curve**: cumulative R-multiple over time
- **Return distribution**: histogram of all trade outcomes
- **Trade table**: every individual trade with entry/exit/sl/tp prices
- **Trade filter**: slice by indicator values to find optimal conditions

### CLI Pipeline

```bash
# Quick test with sample data
python run_pipeline.py

# Test against real data with a saved rule
python run_pipeline.py \
  --csv data/raw/BTCUSDT_4h.parquet \
  --symbol BTCUSDT --interval 4h \
  --rule rules/macd_crossover.json \
  --sl-type atr --sl 1.5 \
  --tp-type rr --tp 2.0

# JSON output for scripting
python run_pipeline.py --csv data/raw/ETHUSDT_4h.parquet --json
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         Streamlit UI (4 Pages)               │
│   Data │ Rule Builder │ Scanner │ Binance    │
├─────────────────────────────────────────────┤
│                                               │
│   Scanner Engine  ─┬──  Rule Engine           │
│                    ├──  Trade Engine           │
│                    └──  Statistics             │
│                                               │
├──────────────────┬────────────────────────────┤
│  Feature Engine  │  Data Hub + SQLite         │
│  (12 indicators) │  (Parquet K-line storage)  │
└──────────────────┴────────────────────────────┘
```

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `core/rule_engine.py` | Compile JSON rules into boolean signal series |
| `core/trade_engine.py` | Simulate entry → SL/TP → exit for each signal |
| `core/scanner.py` | Batch scan: signals → trades → statistics |
| `core/statistics.py` | Compute win rate, expectancy, drawdown, equity curve |
| `core/feature_registry.py` | Auto-discover and register indicator plugins |
| `core/data_hub.py` | Import, cache, and manage OHLCV data |
| `core/strategies/` | Pluggable SL/TP strategies (11 total) |

### Indicator Plugins

Drop a `.py` file in `feature/` with a `calculate(df, **params) -> Series` function — it's automatically available in the Rule Builder.

Built-in: `ema`, `macd`, `rsi`, `atr`, `bollinger`, `volume`, `candle_body`, `upper_shadow`, `lower_shadow`, `volatility`, `close_from_high`, `consecutive_up`

### Strategy Pattern (SL/TP)

| Stop Loss | Take Profit |
|-----------|-------------|
| `FixedSL` — fixed % | `FixedRRTP` — fixed R:R |
| `ATRSL` — ATR multiple | `FixedPctTP` — fixed % |
| `SwingSL` — swing low/high | `TargetTP` — price target |
| `BarExtremeSL` — entry bar extreme | `BollingerMidTP` — dynamic midline reversion |
| `CustomSL` — absolute price | `CustomTP` — absolute price |

## Rule JSON Format

```json
{
  "and": [
    {"feature": "ema", "operator": ">", "value": 0, "params": {"period": 20}},
    {"feature": "volume", "operator": ">", "value": 1.5},
    {"or": [
      {"feature": "rsi", "operator": "<", "value": 30},
      {"feature": "macd", "operator": "cross_above", "value": 0,
       "params": {"component": "histogram"}}
    ]}
  ]
}
```

**Supported operators**: `>`, `<`, `>=`, `<=`, `==`, `!=`, `between`, `cross_above`, `cross_below`

## Project Structure

```
trading-system-validator/
├── main.py                     # Streamlit entry point
├── run_pipeline.py             # CLI pipeline for batch testing
├── requirements.txt
├── CLAUDE.md                   # Project rules (for Claude Code)
│
├── pages/                      # Streamlit pages
│   ├── 1_📊_Data.py            # Data management
│   ├── 2_🔧_Rule_Builder.py    # Visual rule editor
│   ├── 3_🔍_Scanner.py         # Batch scanner + results
│   └── 4_🌐_Binance.py         # Historical data download
│
├── core/                       # Core engine modules
│   ├── data_hub.py             # Data import/cache
│   ├── feature_registry.py     # Plugin discovery
│   ├── rule_engine.py          # Rule compiler & executor
│   ├── trade_engine.py         # Trade simulator
│   ├── scanner.py              # Batch scanner
│   ├── statistics.py           # Statistics calculator
│   ├── i18n.py                 # CN/EN bilingual system
│   ├── db.py                   # SQLite management
│   └── strategies/             # SL/TP plugin architecture
│       ├── sl_strategies.py    # 5 stop-loss strategies
│       └── tp_strategies.py    # 6 take-profit strategies
│
├── feature/                    # Indicator plugins (12)
│   ├── ema.py, macd.py, rsi.py, atr.py
│   ├── bollinger.py, volume.py, volatility.py
│   └── candle_body.py, upper_shadow.py, lower_shadow.py
│       close_from_high.py, consecutive_up.py
│
├── rules/                      # Saved rule templates (JSON)
├── data/                       # K-line data (Parquet) + SQLite
├── tests/                      # Test suite (107 tests)
└── docs/                       # Architecture & development docs
```

## What This Is NOT

- ❌ An automated trading platform
- ❌ A signal/copy-trading service
- ❌ An order execution system
- ❌ A real-time market terminal
- ❌ A portfolio / account manager

**It's a laboratory. You test ideas here. You trade elsewhere.**

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11+ | Data science ecosystem |
| UI | Streamlit | Fastest way to build interactive research tools |
| Data | Polars | High-performance columnar operations |
| Charts | Plotly | Interactive, exportable |
| Storage | Parquet + SQLite | Columnar compression + zero-config DB |
| Rules | Self-designed JSON AST | Serializable, auditable, language-agnostic |

## License

MIT
