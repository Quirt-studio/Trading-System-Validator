# FactorLab 开发计划

> 版本：v1.0 | 日期：2026-07-18 | 状态：待执行

---

## 一、MVP 范围确认

第一版只做以下事情，其他一律不做：

| 做 | 不做 |
|----|------|
| 导入 CSV 历史数据 | 实时行情 |
| Parquet 本地存储 | 交易所连接 |
| Feature 插件系统 + 12 个内置因子 | 用户系统 |
| Rule Engine（AND/OR 表达式） | 账户模拟 |
| Trade Engine（SL/TP/超时） | 多品种同时扫描 |
| Scanner 自动扫描 | Replay 人工回放 |
| Statistics 自动统计 | AI 报告生成 |
| Streamlit UI（3 页） | 云端部署 |

**目标**：导入 BTC 4H CSV → 在 Rule Builder 里定义规则 → 扫描 → 3 秒内看到统计结果。

---

## 二、开发阶段

### Phase 1：项目骨架 + 数据层 ✅ 最优先

> 目标：有数据、能加载、因子能算。

```
工作项：
├── requirements.txt              依赖清单
├── main.py                       Streamlit 入口
├── data/raw/                     数据目录（.gitkeep）
│
├── core/
│   ├── __init__.py
│   ├── data_hub.py               数据中心
│   │   ├── class DataHub
│   │   ├── import_csv(path, symbol, interval) → DataFrame
│   │   ├── list_datasets() → list[dict]
│   │   ├── load(symbol, interval) → DataFrame
│   │   └── delete(symbol, interval)
│   │
│   ├── feature_registry.py       因子注册表
│   │   ├── class FeatureRegistry
│   │   ├── _scan(plugin_dir)      自动发现
│   │   ├── list_all()             列出所有因子
│   │   ├── get_info(name)         获取因子元信息
│   │   └── calculate(name, df, **params)
│   │
│   └── db.py                     SQLite 初始化
│       ├── init_db()
│       ├── get_connection()
│       └── 建表 SQL (rule_template, scan_job, trade, trade_feature)
│
├── feature/
│   ├── __init__.py
│   ├── ema.py                    趋势：EMA 偏离
│   ├── macd.py                   趋势：MACD 线/柱
│   ├── rsi.py                    震荡：RSI
│   ├── atr.py                    波动：ATR
│   ├── bollinger.py              波动：布林带
│   ├── volume.py                 量价：成交量比率
│   ├── candle_body.py            形态：K线实体
│   ├── upper_shadow.py           形态：上影线
│   ├── lower_shadow.py           形态：下影线
│   ├── volatility.py             统计：波动率
│   ├── consecutive_up.py         统计：连续上涨
│   └── close_from_high.py        统计：收盘距最高价
│
└── tests/
    ├── __init__.py
    ├── conftest.py               共享 fixtures
    ├── test_features.py
    └── data/
        └── sample_klines.parquet 样本数据
```

**验收标准**：
- [ ] `DataHub.import_csv()` 能正确导入 Binance/ TradingView 格式的 CSV
- [ ] `DataHub.load()` 能正确读取 Parquet 并返回 Polars DataFrame
- [ ] `FeatureRegistry.list_all()` 返回 12 个因子的列表
- [ ] `FeatureRegistry.calculate("ema", df, period=20)` 返回正确 Series
- [ ] 每个 Feature 有基本测试通过

---

### Phase 2：Rule Engine ⭐ 核心

> 目标：JSON 规则能编译执行，输出布尔信号序列。

```
工作项：
├── core/rule_engine.py
│   ├── Operator 类型定义
│   ├── @dataclass FeatureCondition
│   ├── @dataclass RuleGroup
│   ├── class RuleEngine
│   │   ├── parse(rule_dict) → RuleGroup
│   │   │   └── 递归解析 JSON → AST
│   │   ├── execute(rule, df) → pl.Series[bool]
│   │   │   ├── _compile_condition(cond, df) → pl.Series[bool]
│   │   │   └── _compile_group(group, df) → pl.Series[bool]
│   │   ├── count_signals(rule, df) → int
│   │   ├── validate(rule_dict) → bool
│   │   └── to_json(rule_group) → dict
│   │
│   └── 支持的运算符:
│       >  <  >=  <=  ==  !=  between  cross_above  cross_below
│
├── rules/
│   └── example_bollinger.json    示例规则
│
└── tests/
    └── test_rule_engine.py
        ├── test_simple_comparison
        ├── test_and_combination
        ├── test_or_combination
        ├── test_nested_and_or
        ├── test_between
        ├── test_cross_above
        └── test_empty_match
```

**验收标准**：
- [ ] `parse()` 能正确解析带嵌套 AND/OR 的 JSON 规则
- [ ] `execute()` 对已知数据返回预期匹配的 K 线索引
- [ ] `between` 运算符正确
- [ ] `cross_above` / `cross_below` 检测金叉/死叉
- [ ] 所有 Rule Engine 测试通过

---

### Phase 3：Trade Engine

> 目标：给定信号列表，模拟执行交易，输出 Trade 对象。

```
工作项：
├── core/trade_engine.py
│   ├── @dataclass TradeConfig
│   │   direction / entry_type / sl_type / sl_value
│   │   tp_type / tp_value / max_holding_bars / time_exit_type
│   │
│   ├── @dataclass Trade
│   │   entry_time / exit_time / entry_price / exit_price
│   │   direction / sl_price / tp_price
│   │   result / r_multiple / holding_bars / feature_snapshot
│   │
│   └── class TradeEngine
│       ├── execute(signals, df, config, feature_registry) → list[Trade]
│       ├── _calculate_entry(df, idx, config) → float
│       ├── _calculate_sl(df, idx, config, entry) → float
│       ├── _calculate_tp(df, idx, config, entry, sl) → float
│       ├── _simulate_trade(df, idx, entry, sl, tp, config) → Trade
│       └── _take_feature_snapshot(df, idx, feature_registry) → dict
│
└── tests/
    └── test_trade_engine.py
        ├── test_entry_price_open
        ├── test_entry_price_close
        ├── test_sl_fixed_percent
        ├── test_sl_atr_multiple
        ├── test_tp_rr
        ├── test_tp_fixed_percent
        ├── test_trade_hits_tp_first
        ├── test_trade_hits_sl_first
        ├── test_trade_timeout
        ├── test_r_multiple_correct
        └── test_feature_snapshot_taken
```

**验收标准**：
- [ ] SL/TP 判断正确（逐根遍历，谁先碰到谁触发）
- [ ] 超时退出正确
- [ ] R 倍数计算正确（做多和做空）
- [ ] 入场时因子快照完整
- [ ] 所有 Trade Engine 测试通过

---

### Phase 4：Scanner + Statistics

> 目标：端到端扫描流程打通。

```
工作项：
├── core/scanner.py
│   ├── @dataclass ScanResult
│   │   rule_json / symbol / interval / date_range
│   │   signal_count / trades / feature_snapshots
│   │
│   └── class Scanner
│       ├── __init__(rule_engine, trade_engine, feature_registry)
│       └── scan(df, rule, trade_config) → ScanResult
│
├── core/statistics.py
│   ├── @dataclass TradeStats
│   │   total_trades / win_count / loss_count / win_rate
│   │   avg_win_r / avg_loss_r / avg_rr
│   │   profit_factor / expectancy
│   │   max_drawdown_pct / max_consecutive_loss
│   │   avg_holding_bars / equity_curve
│   │
│   └── class Statistics
│       ├── compute(trades) → TradeStats
│       ├── _calc_equity_curve(trades) → list[float]
│       ├── _calc_drawdown(equity) → float
│       └── _calc_consecutive_loss(trades) → int
│
└── tests/
    ├── test_scanner.py
    │   ├── test_scan_with_sample_rule
    │   ├── test_scan_empty_result
    │   └── test_scan_result_structure
    │
    └── test_statistics.py
        ├── test_compute_all_win
        ├── test_compute_all_loss
        ├── test_compute_mixed
        ├── test_profit_factor
        ├── test_max_drawdown
        └── test_equity_curve_length
```

**验收标准**：
- [ ] Scanner 端到端：规则 → 信号 → Trade → ScanResult
- [ ] Statistics 对已知 Trade 列表计算出正确指标
- [ ] 全部模块测试通过
- [ ] 可以用 CLI 脚本验证（不依赖 UI）

---

### Phase 5：Streamlit UI

> 目标：三页 Web 界面可用。

```
工作项：
├── main.py                       Streamlit 入口（页面路由）
│
├── app/
│   ├── __init__.py
│   │
│   ├── 1_📊_Data.py              页面一：数据中心
│   │   ├── 侧边栏：已导入数据列表
│   │   ├── 上传 CSV 组件
│   │   ├── 数据概览表格
│   │   └── 删除按钮
│   │
│   ├── 2_🔧_Rule_Builder.py      页面二：规则编辑器
│   │   ├── Feature 选择器（分类下拉）
│   │   ├── Operator 选择器
│   │   ├── Value 输入框
│   │   ├── AND/OR 切换
│   │   ├── 已添加条件列表（可删除）
│   │   ├── JSON 预览
│   │   ├── 保存到 rules/
│   │   └── 加载已有规则
│   │
│   └── 3_🔍_Scanner.py           页面三：扫描结果
│       ├── 选择规则模板
│       ├── 选择 Symbol / Interval
│       ├── Trade Config 面板
│       │   ├── Entry Type
│       │   ├── SL Type + Value
│       │   ├── TP Type + Value
│       │   └── Max Holding Bars
│       ├── 执行扫描按钮
│       ├── 统计摘要卡片（st.metric × 6）
│       ├── 权益曲线（Plotly）
│       ├── 收益分布直方图（Plotly）
│       ├── 交易明细表（st.dataframe）
│       └── Filter 面板（可选：按因子值筛选）
│
└── assets/
    └── style.css                  Streamlit 样式微调
```

**验收标准**：
- [ ] 三页均可正常导航
- [ ] 页面一：能上传 CSV、显示数据列表
- [ ] 页面二：能可视化构建规则、保存 JSON
- [ ] 页面三：能完整执行扫描、看到图表和统计

---

## 三、依赖关系图

```
Phase 1 (数据层 + 因子)
    │
    ▼
Phase 2 (Rule Engine)  ← 依赖 Phase 1 的 Feature Registry
    │
    ▼
Phase 3 (Trade Engine) ← 依赖 Phase 1 的 Feature Registry
    │
    ▼
Phase 4 (Scanner + Statistics) ← 依赖 Phase 2 + Phase 3
    │
    ▼
Phase 5 (Streamlit UI) ← 依赖 Phase 4
```

**必须串行**，因为每个 Phase 都依赖前一个 Phase 的输出。

---

## 四、时间估算

| Phase | 内容 | 文件数 | 预估 |
|-------|------|--------|------|
| 1 | 项目骨架 + 数据层 + 12 因子 | ~20 | 先做核心 |
| 2 | Rule Engine | ~3 | 核心 |
| 3 | Trade Engine | ~2 | 核心 |
| 4 | Scanner + Statistics | ~4 | 打通闭环 |
| 5 | Streamlit UI | ~4 | 可视化 |

**策略**：先跑通 CLI 验证（Phase 1-4），再加 UI（Phase 5）。

---

## 五、Phase 1 启动清单（立即可做）

### 第一步：创建项目骨架

```bash
# 目录
mkdir -p feature core app rules data/raw tests/data docs

# 空文件
touch feature/__init__.py core/__init__.py app/__init__.py tests/__init__.py
touch data/raw/.gitkeep

# requirements.txt
echo "streamlit>=1.28
polars>=0.19
plotly>=5.17
pyarrow>=14.0
numpy>=1.26
scipy>=1.11
pytest>=7.4" > requirements.txt

# 虚拟环境
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 第二步：实现模块

**实现顺序（每个完成后立即写测试）**：

1. `core/db.py` — SQLite 初始化（最简单，无依赖）
2. `core/feature_registry.py` — 因子注册表（无依赖）
3. `feature/ema.py` — 第一个因子（验证注册表工作）
4. 剩余 11 个因子
5. `core/data_hub.py` — 数据中心
6. `tests/conftest.py` — 共享 fixture（生成样本数据）

---

## 六、不做什么（防止跑偏）

这些功能在第一版**明确不做**：

- ❌ Replay 模式（Phase 6+）
- ❌ Filter 筛选器（Phase 6+）
- ❌ AI 报告生成
- ❌ Walk-Forward / Monte Carlo
- ❌ Binance API 下载（先支持 CSV 导入）
- ❌ 多品种并行扫描
- ❌ 实时 K 线图
- ❌ 规则可视化预览图

**记住**：MVP 成功的唯一标准是——

> 导入 CSV → 定义规则 → 扫描 → 看到统计。3 秒内完成。
