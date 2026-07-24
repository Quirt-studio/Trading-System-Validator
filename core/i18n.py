"""
core/i18n.py — 双语支持模块

提供中英文切换功能。所有 UI 文本集中管理，通过 t(key) 获取当前语言的文本。

用法:
    from core.i18n import t, init_lang, lang_toggle

    init_lang()
    st.title(t("scanner_title"))
    lang_toggle()

动态文本使用 Python 格式化:
    t("downloading", i=5, total=10)  # -> "下载中 (5/10): ..."
"""

from __future__ import annotations

import streamlit as st

# ══════════════════════════════════════════════════════════════════════════════
# 翻译字典 — 所有 UI 文本集中在这里
# ══════════════════════════════════════════════════════════════════════════════

TEXT: dict[str, dict[str, str]] = {
    # ── main.py ──
    "app_title": {
        "cn": "🔬 FactorLab",
        "en": "🔬 FactorLab",
    },
    "app_caption": {
        "cn": "交易系统验证平台 — 验证一个交易规则是否具有统计优势",
        "en": "Trading System Validation Platform — Verify if a trading rule has statistical edge",
    },
    "quick_start_title": {
        "cn": "### 快速开始",
        "en": "### Quick Start",
    },
    "quick_start_body": {
        "cn": """
1. **📊 Data** — 导入历史 K 线数据
2. **🔧 Rule Builder** — 可视化构建交易规则
3. **🔍 Scanner** — 自动扫描并统计结果

> 从左侧导航栏选择页面开始。
""",
        "en": """
1. **📊 Data** — Import historical K-line data
2. **🔧 Rule Builder** — Visually build trading rules
3. **🔍 Scanner** — Auto-scan and view statistics

> Select a page from the left sidebar to begin.
""",
    },

    # ── 语言切换 ──
    "lang_en": {"cn": "🌐 EN", "en": "🌐 中文"},
    "lang_label": {"cn": "语言 / Language", "en": "语言 / Language"},

    # ── 共享 ──
    "symbol": {"cn": "Symbol", "en": "Symbol"},
    "interval": {"cn": "Interval", "en": "Interval"},
    "import_btn": {"cn": "导入", "en": "Import"},
    "importing": {"cn": "正在导入 {symbol} {interval}...", "en": "Importing {symbol} {interval}..."},
    "import_success": {"cn": "导入成功: {rows} 行 K 线数据", "en": "Import successful: {rows} K-line rows"},
    "import_failed": {"cn": "导入失败: {error}", "en": "Import failed: {error}"},

    # ── Data 页面 ──
    "data_title": {"cn": "📊 数据中心", "en": "📊 Data Hub"},
    "data_caption": {"cn": "导入和管理 K 线数据", "en": "Import and manage K-line data"},
    "data_imported_header": {"cn": "已导入数据", "en": "Imported Data"},
    "data_no_data": {"cn": "还没有导入任何数据。请上传 CSV 文件开始。", "en": "No data imported yet. Upload a CSV file to start."},
    "data_col_symbol": {"cn": "Symbol", "en": "Symbol"},
    "data_col_interval": {"cn": "Interval", "en": "Interval"},
    "data_col_rows": {"cn": "K线数", "en": "K-lines"},
    "data_col_start": {"cn": "起始时间", "en": "Start"},
    "data_col_end": {"cn": "结束时间", "en": "End"},
    "data_col_size": {"cn": "大小(MB)", "en": "Size(MB)"},
    "data_actions": {"cn": "操作", "en": "Actions"},
    "data_delete_btn": {"cn": "🗑️ 删除", "en": "🗑️ Delete"},
    "data_preview_btn": {"cn": "👁️ 预览", "en": "👁️ Preview"},
    "data_deleted": {"cn": "已删除 {symbol} {interval}", "en": "Deleted {symbol} {interval}"},
    "data_import_header": {"cn": "导入数据", "en": "Import Data"},
    "data_import_caption": {"cn": "支持标准 OHLCV CSV 文件（Binance / TradingView 导出格式）", "en": "Supports standard OHLCV CSV files (Binance / TradingView export format)"},
    "data_upload_label": {"cn": "上传 CSV 文件", "en": "Upload CSV file"},
    "data_upload_help": {"cn": "支持 Binance 和 TradingView 导出的 CSV 格式", "en": "Supports Binance and TradingView exported CSV formats"},
    "data_sample_caption": {"cn": "没有数据？可以先生成 500 行样本数据用于测试:", "en": "No data? Generate 500 rows of sample data for testing:"},
    "data_sample_btn": {"cn": "🎲 生成样本数据", "en": "🎲 Generate Sample Data"},
    "data_sample_success": {"cn": "已生成 {path} ({rows} 行)", "en": "Generated {path} ({rows} rows)"},
    "data_total_rows": {"cn": "共 {rows} 行, {cols} 列", "en": "Total {rows} rows, {cols} columns"},

    # ── Rule Builder 页面 ──
    "rb_title": {"cn": "🔧 规则编辑器", "en": "🔧 Rule Builder"},
    "rb_caption": {"cn": "可视化构建交易规则条件，无需写代码", "en": "Visually build trading rule conditions, no coding required"},
    "rb_help_expander": {"cn": "📖 界面说明 — 各选项详细介绍", "en": "📖 Interface Guide — Detailed option descriptions"},
    "rb_help_content": {
        "cn": """
### 🧩 一、Feature（因子）

因子是对 K 线数据进行数学计算后得到的一个数值序列。每一根 K 线都有一个对应的因子值。选择因子 = 选择"观察什么指标"。

| 因子 | 含义 | 典型用法 |
|------|------|----------|
| **EMA** (ema) | 收盘价偏离EMA的百分比 | `EMA > 0` → 价格在均线上方，趋势偏多 |
| **MACD** (macd) | MACD 柱状图 (快慢线差值) | `MACD > 0` → 多头动能 |
| **RSI** (rsi) | 相对强弱指数 [0,100] | `RSI < 30` → 超卖反弹机会；`RSI > 70` → 超买 |
| **ATR** (atr) | 平均真实波幅 (价格绝对值) | `ATR > 50` → 波动够大，值得交易 |
| **布林带** (bollinger) | 价格突破布林带上轨的百分比 | `bollinger > 0` → 突破上轨 |
| **成交量比** (volume_ratio) | 当前量 / 均量 | `volume_ratio > 1.5` → 放量 |
| **K线实体** (candle_body) | 实体占振幅的百分比 | `candle_body > 50` → 趋势坚决 |
| **上影线** (upper_shadow) | 上影线占振幅百分比 | `upper_shadow > 60` → 上方压力大 |
| **下影线** (lower_shadow) | 下影线占振幅百分比 | `lower_shadow > 60` → 下方支撑强 |
| **收盘距高** (close_from_high) | 收盘价距离最高价的百分比 | `close_from_high > 3` → 从高点回落 ≥3% |
| **连续上涨** (consecutive_up) | 连续收阳的 K 线根数 | `consecutive_up >= 3` → 连涨 3 根 |
| **波动率** (volatility) | 年化历史波动率 | `volatility > 40` → 高波动 |

### 📐 二、Operator（运算符）

运算符定义因子值与阈值之间的比较关系。

| 运算符 | 含义 | 示例 | 说明 |
|--------|------|------|------|
| **>** | 大于 | `RSI > 70` | 因子值严格超过阈值时触发 |
| **<** | 小于 | `RSI < 30` | 因子值严格低于阈值时触发 |
| **>=** | 大于等于 | `volume_ratio >= 1.5` | 包括等于的情况 |
| **<=** | 小于等于 | `close_from_high <= 1.0` | 包括等于的情况 |
| **==** | 等于 | `consecutive_up == 3` | 精确匹配（慎用浮点数） |
| **!=** | 不等于 | `candle_body != 0` | 排除特定值 |
| **between** | 区间内 | `RSI between [30, 70]` | Low ≤ 值 ≤ High |
| **cross_above** | 上穿 | `MACD cross_above 0` | 前一根 ≤ 阈值，当前 > 阈值 |
| **cross_below** | 下穿 | `MACD cross_below 0` | 前一根 ≥ 阈值，当前 < 阈值 |

> cross_above / cross_below 是动态运算符，关注"穿越"动作，常用于金叉/死叉信号。

### 🎯 三、Value（阈值）

- RSI：30（超卖）或 70（超买）
- volume_ratio：1.5（放量）或 0.5（缩量）
- candle_body：50（趋势坚决）或 20（十字星）
- close_from_high：2-5（高点回落幅度）
- between 需要填 Low 和 High 两个值
- cross 运算符阈值通常是 0

### ⚙️ 四、参数（Params）

| 因子 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| EMA | period | 20 | 均线周期 |
| MACD | fast/slow/signal | 12/26/9 | 快慢信号线周期 |
| RSI | period | 14 | Wilder 经典值 |
| ATR | period | 14 | 周期越大越平滑 |
| 布林带 | period/std_dev | 20/2.0 | 中轨周期/标准差 |
| 成交量比 | period | 20 | 均量周期 |
| 波动率 | period | 20 | 回望窗口 ≈ 一个月 |

### 🔗 五、逻辑组合（AND / OR）

| 模式 | 含义 | 示例 |
|------|------|------|
| **AND** | 所有条件同时满足 | `RSI<30 AND vol>1.5` → 超卖+放量 |
| **OR** | 任一条件满足 | `RSI<30 OR boll<-3` → 超卖或跌破下轨 |
""",
        "en": """
### 🧩 1. Feature (Indicator)

A Feature is a numerical sequence computed from K-line data. Each K-line gets one value. Selecting a feature = choosing "what to observe."

| Feature | Meaning | Typical Use |
|---------|---------|-------------|
| **EMA** (ema) | Close price deviation from EMA (%) | `EMA > 0` → Price above MA, bullish trend |
| **MACD** (macd) | MACD histogram (fast - slow line) | `MACD > 0` → Bullish momentum |
| **RSI** (rsi) | Relative Strength Index [0,100] | `RSI < 30` → Oversold bounce; `RSI > 70` → Overbought |
| **ATR** (atr) | Average True Range (absolute price) | `ATR > 50` → Enough volatility to trade |
| **Bollinger** (bollinger) | Price breakout % above upper band | `bollinger > 0` → Upper band breakout |
| **Volume Ratio** (volume_ratio) | Current vol / avg vol | `volume_ratio > 1.5` → High volume confirmation |
| **Candle Body** (candle_body) | Body % of total range | `candle_body > 50` → Strong trend |
| **Upper Shadow** (upper_shadow) | Upper shadow % of range | `upper_shadow > 60` → Strong overhead resistance |
| **Lower Shadow** (lower_shadow) | Lower shadow % of range | `lower_shadow > 60` → Strong support |
| **Close from High** (close_from_high) | Distance from close to high (%) | `close_from_high > 3` → Pulled back ≥3% from high |
| **Consecutive Up** (consecutive_up) | Count of consecutive bullish bars | `consecutive_up >= 3` → 3+ bars up, caution chasing |
| **Volatility** (volatility) | Annualized historical volatility | `volatility > 40` → High volatility; `< 15` → Low |

### 📐 2. Operator

Operators define the comparison between feature value and threshold.

| Operator | Meaning | Example | Notes |
|----------|---------|---------|-------|
| **>** | Greater than | `RSI > 70` | Triggers when value strictly exceeds threshold |
| **<** | Less than | `RSI < 30` | Triggers when value strictly below threshold |
| **>=** | Greater or equal | `vol >= 1.5` | Includes equality |
| **<=** | Less or equal | `pullback <= 1.0` | Includes equality |
| **==** | Equal | `cons_up == 3` | Exact match (avoid with floats!) |
| **!=** | Not equal | `body != 0` | Exclude specific value |
| **between** | In range | `RSI between [30,70]` | Low ≤ value ≤ High |
| **cross_above** | Cross above | `MACD cross_above 0` | Prev ≤ threshold, current > threshold |
| **cross_below** | Cross below | `MACD cross_below 0` | Prev ≥ threshold, current < threshold |

> cross_above / cross_below are dynamic operators — they detect the crossing action, not static comparison. Used for golden cross / dead cross signals.

### 🎯 3. Value (Threshold)

- RSI: 30 (oversold) or 70 (overbought)
- volume_ratio: 1.5 (high volume) or 0.5 (low volume)
- candle_body: 50 (strong trend) or 20 (doji)
- close_from_high: 2-5 (pullback from high)
- between: requires both Low and High values
- cross: threshold is typically 0 (e.g. MACD crossing zero line)

### ⚙️ 4. Parameters

| Feature | Params | Default | Notes |
|---------|--------|---------|-------|
| EMA | period | 20 | Smaller = more sensitive |
| MACD | fast/slow/signal | 12/26/9 | Classic MACD settings |
| RSI | period | 14 | Wilder's classic value |
| ATR | period | 14 | Larger = smoother |
| Bollinger | period/std_dev | 20/2.0 | Mid band period / std multiplier |
| Volume Ratio | period | 20 | Average volume period |
| Volatility | period | 20 | Lookback window ≈ 1 month |

### 🔗 5. Logic (AND / OR)

| Mode | Meaning | Example |
|------|---------|---------|
| **AND** | All conditions must be met simultaneously | `RSI<30 AND vol>1.5` → Oversold + high vol |
| **OR** | Any condition can trigger | `RSI<30 OR boll<-3` → Oversold or below lower band |
""",
    },
    "rb_sidebar_available_features": {"cn": "可用因子", "en": "Available Features"},
    "rb_tab_edit": {"cn": "✏️ 编辑规则", "en": "✏️ Edit Rule"},
    "rb_tab_json": {"cn": "📋 JSON 预览", "en": "📋 JSON Preview"},
    "rb_tab_save": {"cn": "💾 保存/加载", "en": "💾 Save/Load"},
    "rb_add_condition": {"cn": "添加条件", "en": "Add Condition"},
    "rb_feature_label": {"cn": "Feature（因子）", "en": "Feature (Indicator)"},
    "rb_feature_help": {"cn": "选择要观察的指标。左侧边栏可查看每个因子的详细说明。", "en": "Select indicator to observe. Sidebar shows details for each feature."},
    "rb_operator_label": {"cn": "Operator（运算符）", "en": "Operator"},
    "rb_operator_help": {
        "cn": "比较运算符: > < >= <= == != 比较当前K线因子值与阈值。\nbetween: 因子值在 [Low, High] 区间内触发。\ncross_above: 上穿（金叉）。\ncross_below: 下穿（死叉）。",
        "en": "Comparison: > < >= <= == != compare current bar's factor value to threshold.\nbetween: triggers when value is in [Low, High] range.\ncross_above: cross above (golden cross).\ncross_below: cross below (dead cross).",
    },
    "rb_value_low": {"cn": "Low（下限）", "en": "Low (Lower bound)"},
    "rb_value_high": {"cn": "High（上限）", "en": "High (Upper bound)"},
    "rb_value_cross": {"cn": "Value（穿越阈值）", "en": "Value (Cross threshold)"},
    "rb_value_cross_help": {"cn": "穿越的临界值。常用 0（如 MACD 穿越零轴）。", "en": "Cross threshold. Typically 0 (e.g. MACD crossing zero)."},
    "rb_value_label": {"cn": "Value（阈值）", "en": "Value (Threshold)"},
    "rb_params_caption": {"cn": "⚙️ 参数 ({feature}) — 可调整以适配不同周期和品种:", "en": "⚙️ Params ({feature}) — Adjust for different timeframes and instruments:"},
    "rb_add_btn": {"cn": "➕ 添加条件", "en": "➕ Add Condition"},
    "rb_current_conditions": {"cn": "当前规则条件", "en": "Current Rule Conditions"},
    "rb_logic_label": {"cn": "逻辑组合方式", "en": "Logic Combination"},
    "rb_logic_and": {"cn": "AND (全部条件同时满足才触发)", "en": "AND (All conditions must be met)"},
    "rb_logic_or": {"cn": "OR (任一条件满足就触发)", "en": "OR (Any condition can trigger)"},
    "rb_logic_help": {
        "cn": "AND: 所有条件必须同时满足，信号才会触发。用于确认多重信号共振。\nOR: 只要有一个条件满足就触发。用于扩展入场场景。",
        "en": "AND: All conditions must be met simultaneously for a signal. Use for confirming multiple signals.\nOR: Any single condition triggers. Use to broaden entry scenarios.",
    },
    "rb_no_conditions": {"cn": "还没有添加条件。请在上方选择 Feature + Operator + Value 后点击「➕ 添加条件」。", "en": "No conditions yet. Select Feature + Operator + Value above and click 「➕ Add Condition」."},
    "rb_conditions_count": {"cn": "{n} 个条件", "en": "{n} condition(s)"},
    "rb_cross_count": {"cn": "{n} 个穿越信号", "en": "{n} cross signal(s)"},
    "rb_delete_btn": {"cn": "✕ 删除", "en": "✕ Delete"},
    "rb_clear_all_btn": {"cn": "🗑️ 清空全部", "en": "🗑️ Clear All"},
    "rb_json_valid": {"cn": "✅ 规则格式有效", "en": "✅ Rule format is valid"},
    "rb_json_invalid": {"cn": "❌ 规则格式无效", "en": "❌ Rule format is invalid"},
    "rb_signal_preview": {"cn": "信号预览", "en": "Signal Preview"},
    "rb_preview_btn": {"cn": "🚀 预览信号数", "en": "🚀 Preview Signal Count"},
    "rb_preview_result": {"cn": "在 **{symbol} {interval}** ({rows} 行) 中: **{count}** 个信号匹配", "en": "In **{symbol} {interval}** ({rows} rows): **{count}** matching signals"},
    "rb_preview_no_data": {"cn": "请先在 Data 页面导入数据", "en": "Please import data first on the Data page"},
    "rb_save_header": {"cn": "保存/加载规则", "en": "Save/Load Rule"},
    "rb_rule_name": {"cn": "规则名称", "en": "Rule Name"},
    "rb_save_btn": {"cn": "💾 保存到 rules/", "en": "💾 Save to rules/"},
    "rb_save_no_conditions": {"cn": "请先添加条件", "en": "Please add conditions first"},
    "rb_save_success": {"cn": "已保存到 {path}", "en": "Saved to {path}"},
    "rb_load_select": {"cn": "选择规则", "en": "Select Rule"},
    "rb_load_btn": {"cn": "📂 加载", "en": "📂 Load"},
    "rb_load_success": {"cn": "已加载 {name}", "en": "Loaded {name}"},
    "rb_load_empty": {"cn": "还没有保存的规则文件", "en": "No saved rule files yet"},
    "rb_nested_warning": {"cn": "⚠️ 规则包含嵌套条件，编辑器仅展示顶层结构。嵌套条件在扫描时仍然生效。", "en": "⚠️ Rule contains nested conditions. Editor shows top-level only. Nested conditions still work during scanning."},

    # ── Scanner 页面 ──
    "sc_title": {"cn": "🔍 策略扫描", "en": "🔍 Strategy Scanner"},
    "sc_caption": {"cn": "选择规则 → 配置交易 → 执行扫描 → 查看统计", "en": "Select Rule → Configure Trade → Run Scan → View Statistics"},
    "sc_sidebar_config": {"cn": "⚙️ 扫描配置", "en": "⚙️ Scan Config"},
    "sc_data_section": {"cn": "数据", "en": "Data"},
    "sc_dataset_label": {"cn": "数据集", "en": "Datasets"},
    "sc_rule_section": {"cn": "规则", "en": "Rule"},
    "sc_rule_source": {"cn": "规则来源", "en": "Rule Source"},
    "sc_rule_from_builder": {"cn": "从 Rule Builder", "en": "From Rule Builder"},
    "sc_rule_from_file": {"cn": "从文件", "en": "From File"},
    "sc_rule_n_conditions": {"cn": "{n} 个条件", "en": "{n} condition(s)"},
    "sc_rule_empty": {"cn": "Rule Builder 中没有条件，请先去编辑", "en": "No conditions in Rule Builder. Please edit first."},
    "sc_select_file": {"cn": "选择文件", "en": "Select File"},
    "sc_rules_empty": {"cn": "rules/ 目录为空", "en": "rules/ directory is empty"},
    "sc_trade_params": {"cn": "交易参数", "en": "Trade Parameters"},
    "sc_direction": {"cn": "方向", "en": "Direction"},
    "sc_entry_type": {"cn": "入场价", "en": "Entry Price"},
    "sc_sl_type": {"cn": "止损策略", "en": "Stop Loss Strategy"},
    "sc_sl_strategy_header": {"cn": "止损策略及参数", "en": "SL Strategy & Parameters"},
    "sc_tp_type": {"cn": "止盈策略", "en": "Take Profit Strategy"},
    "sc_tp_strategy_header": {"cn": "止盈策略及参数", "en": "TP Strategy & Parameters"},
    "sc_max_hold": {"cn": "最大持仓 (根K线)", "en": "Max Hold (bars)"},
    "sc_max_hold": {"cn": "最大持仓 (根K线)", "en": "Max Hold (bars)"},
    "sc_run_btn": {"cn": "🚀 执行扫描", "en": "🚀 Run Scan"},
    "sc_rule_invalid": {"cn": "规则无效，请先在 Rule Builder 编辑规则。", "en": "Invalid rule. Please edit in Rule Builder first."},
    "sc_loading": {"cn": "扫描 {key}...", "en": "Scanning {key}..."},
    "sc_load_failed": {"cn": "加载 {key} 失败: {error}", "en": "Load {key} failed: {error}"},
    "sc_sidebar_hint": {"cn": "👈 在左侧配置扫描参数后点击「执行扫描」", "en": "👈 Configure scan parameters on the left and click 「Run Scan」"},
    "sc_no_data_warning": {"cn": "还没有数据。请先在 📊 Data 页面导入数据或生成样本数据。", "en": "No data yet. Please import data or generate sample data on the 📊 Data page."},
    "sc_select_dataset": {"cn": "请至少选择一个数据集", "en": "Please select at least one dataset"},
    "sc_compare_title": {"cn": "📊 多品种对比", "en": "📊 Multi-Instrument Comparison"},
    "sc_no_trades": {"cn": "{label}: 没有匹配的交易信号", "en": "{label}: No matching trade signals"},
    "sc_result_title": {"cn": "📊 {label}", "en": "📊 {label}"},
    # Scanner metrics
    "sc_total_trades": {"cn": "交易总数", "en": "Total Trades"},
    "sc_win_rate": {"cn": "胜率", "en": "Win Rate"},
    "sc_profit_factor": {"cn": "Profit Factor", "en": "Profit Factor"},
    "sc_expectancy": {"cn": "Expectancy", "en": "Expectancy"},
    "sc_max_dd": {"cn": "最大回撤", "en": "Max Drawdown"},
    "sc_avg_hold": {"cn": "平均持仓", "en": "Avg Hold"},
    "sc_avg_win": {"cn": "平均盈利", "en": "Avg Win"},
    "sc_avg_loss": {"cn": "平均亏损", "en": "Avg Loss"},
    "sc_max_consec_loss": {"cn": "最大连亏", "en": "Max Consec. Loss"},
    "sc_total_r": {"cn": "总R倍数", "en": "Total R"},
    "sc_equity_curve": {"cn": "权益曲线", "en": "Equity Curve"},
    "sc_drawdown_curve": {"cn": "回撤曲线", "en": "Drawdown Curve"},
    "sc_return_dist": {"cn": "收益分布", "en": "Return Distribution"},
    "sc_trade_details": {"cn": "交易明细", "en": "Trade Details"},
    "sc_filter_section": {"cn": "🔬 Filter 筛选器 — {label}", "en": "🔬 Filter — {label}"},
    "sc_filter_feature": {"cn": "筛选因子", "en": "Filter Feature"},
    "sc_filter_op": {"cn": "运算符", "en": "Operator"},
    "sc_filter_val": {"cn": "阈值", "en": "Threshold"},
    "sc_filter_btn": {"cn": "🔍 筛选", "en": "🔍 Filter"},
    "sc_filter_before": {"cn": "筛选前", "en": "Before"},
    "sc_filter_after": {"cn": "筛选后", "en": "After"},
    "sc_filter_trades": {"cn": "交易数", "en": "Trades"},
    "sc_filter_equity": {"cn": "筛选后权益曲线", "en": "Filtered Equity Curve"},
    "sc_export_csv": {"cn": "📥 导出 CSV", "en": "📥 Export CSV"},
    "sc_compare_signal": {"cn": "信号", "en": "Signals"},
    "sc_compare_trades": {"cn": "交易", "en": "Trades"},
    "sc_compare_winrate": {"cn": "胜率%", "en": "Win%"},
    "sc_compare_pf": {"cn": "PF", "en": "PF"},
    "sc_compare_expectancy": {"cn": "期望R", "en": "Exp. R"},
    "sc_compare_dd": {"cn": "回撤%", "en": "DD%"},
    "sc_compare_totalr": {"cn": "总R", "en": "Total R"},

    # ── Binance 页面 ──
    "bn_title": {"cn": "🌐 Binance 数据下载", "en": "🌐 Binance Data Download"},
    "bn_caption": {"cn": "从 data.binance.vision 下载期货 K 线历史数据", "en": "Download futures K-line historical data from data.binance.vision"},
    "bn_symbol_label": {"cn": "交易对", "en": "Symbol"},
    "bn_symbol_help": {"cn": "如 BTCUSDT, ETHUSDT", "en": "e.g. BTCUSDT, ETHUSDT"},
    "bn_symbol_quick": {"cn": "快捷选择", "en": "Quick Select"},
    "bn_popular_caption": {"cn": "常用: ", "en": "Popular: "},
    "bn_interval_label": {"cn": "K线周期", "en": "Interval"},
    "bn_fetch_btn": {"cn": "🔍 获取文件列表", "en": "🔍 Fetch File List"},
    "bn_fetch_spinner": {"cn": "查询 {symbol} {interval}...", "en": "Querying {symbol} {interval}..."},
    "bn_no_files": {"cn": "未找到 {symbol} {interval} 的数据文件。请检查交易对和周期是否正确。", "en": "No data files found for {symbol} {interval}. Please check symbol and interval."},
    "bn_found_files": {"cn": "找到 **{count}** 个文件", "en": "Found **{count}** files"},
    "bn_quick_filter": {"cn": "快速筛选:", "en": "Quick Filter:"},
    "bn_select_all": {"cn": "全选", "en": "All"},
    "bn_select_all_btn": {"cn": "📋 全选", "en": "📋 Select All"},
    "bn_deselect_all_btn": {"cn": "🗑️ 取消全选", "en": "🗑️ Deselect All"},
    "bn_select_year_btn": {"cn": "📅 {year}年", "en": "📅 {year}"},
    "bn_file_select": {
        "cn": "选择要下载的文件 (**{total}** 个可用，可多选)",
        "en": "Select files to download (**{total}** available, multi-select)",
    },
    "bn_selected_count": {"cn": "已选 **{count}** 个文件", "en": "Selected **{count}** files"},
    "bn_download_btn": {"cn": "📥 下载选中文件", "en": "📥 Download Selected"},
    "bn_downloading": {"cn": "下载中 ({i}/{total}): {filename}", "en": "Downloading ({i}/{total}): {filename}"},
    "bn_merging": {"cn": "正在合并保存...", "en": "Merging and saving..."},
    "bn_download_success": {"cn": "✅ 下载完成: {success}/{total} 个文件 → `{path}`", "en": "✅ Download complete: {success}/{total} files → `{path}`"},
    "bn_total_klines": {"cn": "总 K 线数", "en": "Total K-lines"},
    "bn_time_range": {"cn": "时间范围", "en": "Time Range"},
    "bn_download_failed": {"cn": "所有文件下载失败", "en": "All file downloads failed"},
    "bn_download_file_failed": {"cn": "下载失败 {filename}: {error}", "en": "Download failed {filename}: {error}"},
    "bn_fetch_failed": {"cn": "获取文件列表失败: {error}", "en": "Failed to fetch file list: {error}"},
    "bn_downloaded_header": {"cn": "📂 已下载的 Binance 数据", "en": "📂 Downloaded Binance Data"},
    "bn_no_downloads": {"cn": "还没有下载过数据", "en": "No data downloaded yet"},
    "bn_col_symbol": {"cn": "交易对", "en": "Symbol"},
    "bn_col_interval": {"cn": "周期", "en": "Interval"},
    "bn_col_klines": {"cn": "K线数", "en": "K-lines"},
    "bn_col_size": {"cn": "大小MB", "en": "Size(MB)"},
    "bn_col_range": {"cn": "时间范围", "en": "Time Range"},
    "bn_import_hint": {"cn": "导入到数据中心供 Scanner 使用:", "en": "Import to Data Hub for Scanner use:"},
    "bn_import_btn": {"cn": "📤 全部导入到 DataHub", "en": "📤 Import All to DataHub"},
    "bn_import_failed": {"cn": "导入 {sym} {itv} 失败: {error}", "en": "Import {sym} {itv} failed: {error}"},
    "bn_import_success": {"cn": "已导入 {count} 个数据集到 data/raw/", "en": "Imported {count} datasets to data/raw/"},

    # ── 因子中文描述 (用于 FeatureInfo fallback) ──
    "feat_desc_ema": {"cn": "收盘价相对于 EMA 的偏离百分比。正值=看涨，负值=看跌。", "en": "Close price deviation from EMA (%). Positive = bullish, negative = bearish."},
    "feat_desc_macd": {"cn": "MACD 柱状图。>0 = 多头动能。", "en": "MACD histogram. >0 = bullish momentum."},
    "feat_desc_rsi": {"cn": "相对强弱指数 [0,100]。>70 超买，<30 超卖。", "en": "RSI [0,100]. >70 overbought, <30 oversold."},
    "feat_desc_atr": {"cn": "平均真实波幅（价格绝对值）。越大=波动越剧烈。", "en": "Average True Range (absolute price). Higher = more volatile."},
    "feat_desc_bollinger": {"cn": "布林带突破百分比。正值=突破上轨，负值=跌破下轨。", "en": "Bollinger Band breakout %. Positive = above upper band, negative = below lower band."},
    "feat_desc_volume_ratio": {"cn": "当前成交量 / 均量。1.0=正常，>1.5=放量，<0.5=缩量。", "en": "Current volume / avg volume. 1.0=normal, >1.5=high, <0.5=low."},
    "feat_desc_candle_body": {"cn": "K线实体占振幅百分比。正值=阳线，越大=趋势越坚决。", "en": "Candle body % of total range. Positive = bullish, larger = stronger trend."},
    "feat_desc_upper_shadow": {"cn": "上影线占振幅比例。越大=上方压力越大。", "en": "Upper shadow % of range. Larger = more overhead resistance."},
    "feat_desc_lower_shadow": {"cn": "下影线占振幅比例。越大=下方支撑越强。", "en": "Lower shadow % of range. Larger = stronger support."},
    "feat_desc_close_from_high": {"cn": "收盘价距最高价的百分比。值越大=收盘离高点越远。", "en": "Distance from close to high (%). Larger = further from high."},
    "feat_desc_consecutive_up": {"cn": "连续收阳的K线数。0=收阴，3=连涨3根。", "en": "Count of consecutive bullish bars. 0=bearish, 3=3 up bars."},
    "feat_desc_volatility": {"cn": "年化历史波动率。越高=价格变动越剧烈。", "en": "Annualized historical volatility. Higher = more price movement."},

    # ── 因子参数说明 ──
    "param_period": {"cn": "period: 计算周期。越小越敏感，越大越平滑。", "en": "period: Lookback window. Smaller = more sensitive, larger = smoother."},
    "param_fast": {"cn": "fast: 快线EMA周期", "en": "fast: Fast EMA period"},
    "param_slow": {"cn": "slow: 慢线EMA周期", "en": "slow: Slow EMA period"},
    "param_signal": {"cn": "signal: 信号线EMA周期", "en": "signal: Signal line EMA period"},
    "param_std_dev": {"cn": "std_dev: 标准差倍数", "en": "std_dev: Standard deviation multiplier"},
    "param_component": {"cn": "component: 返回组件 (histogram/line/signal)", "en": "component: Return component (histogram/line/signal)"},

    # ── 因子分类名 ──
    "cat_momentum": {"cn": "momentum (动量)", "en": "momentum"},
    "cat_volatility": {"cn": "volatility (波动)", "en": "volatility"},
    "cat_volume": {"cn": "volume (成交量)", "en": "volume"},
    "cat_pattern": {"cn": "pattern (形态)", "en": "pattern"},
    "cat_unknown": {"cn": "unknown", "en": "unknown"},

    # ── 运算符翻译 ──
    "op_gt": {"cn": "大于", "en": "greater than"},
    "op_lt": {"cn": "小于", "en": "less than"},
    "op_gte": {"cn": "大于等于", "en": "greater or equal"},
    "op_lte": {"cn": "小于等于", "en": "less or equal"},
    "op_eq": {"cn": "等于", "en": "equal to"},
    "op_neq": {"cn": "不等于", "en": "not equal to"},
    "op_between": {"cn": "介于", "en": "between"},
    "op_cross_above": {"cn": "上穿", "en": "cross above"},
    "op_cross_below": {"cn": "下穿", "en": "cross below"},

    # ── 因子值范围提示 ──
    "range_ema": {"cn": "典型范围 -10 ~ +10 (%)，0=价格在均线上", "en": "Typical range -10 ~ +10 (%), 0=price at MA"},
    "range_macd": {"cn": "柱状图值，0=多空平衡。BTC 4h 典型 -500 ~ +500", "en": "Histogram value, 0=neutral. BTC 4h typical -500 ~ +500"},
    "range_rsi": {"cn": "范围 0~100。30=超卖，70=超买，50=中性", "en": "Range 0~100. 30=oversold, 70=overbought, 50=neutral"},
    "range_atr": {"cn": "价格绝对值，取决于品种。BTC 4h 典型 500~5000", "en": "Absolute price value, instrument-dependent. BTC 4h typical 500~5000"},
    "range_bollinger": {"cn": "突破百分比，典型 -5 ~ +5。>0=突破上轨", "en": "Breakout %, typical -5 ~ +5. >0=above upper band"},
    "range_volume_ratio": {"cn": "1.0=正常，>1.5=放量，<0.5=缩量", "en": "1.0=normal, >1.5=high vol, <0.5=low vol"},
    "range_candle_body": {"cn": "-100 ~ +100。正值=阳线，±50=趋势坚决", "en": "-100 ~ +100. Positive=bullish, ±50=strong trend"},
    "range_upper_shadow": {"cn": "0~100 (%)。>60=上影线长（压力大）", "en": "0~100 (%). >60=long upper shadow (resistance)"},
    "range_lower_shadow": {"cn": "0~100 (%)。>60=下影线长（支撑强）", "en": "0~100 (%). >60=long lower shadow (support)"},
    "range_close_from_high": {"cn": "0~100 (%)。>3=从高点回落超过3%", "en": "0~100 (%). >3=pulled back >3% from high"},
    "range_consecutive_up": {"cn": "整数 0~N。0=收阴，3=连涨3根", "en": "Integer 0~N. 0=bearish bar, 3=3 up bars"},
    "range_volatility": {"cn": "年化波动率 %。20=正常，>40=高波动", "en": "Annualized vol %. 20=normal, >40=high vol"},

    # ── 因子分类名（侧边栏显示）──
    "feat_cat_momentum": {"cn": "📂 momentum (动量)", "en": "📂 momentum"},
    "feat_cat_volatility": {"cn": "📂 volatility (波动)", "en": "📂 volatility"},
    "feat_cat_volume": {"cn": "📂 volume (成交量)", "en": "📂 volume"},
    "feat_cat_pattern": {"cn": "📂 pattern (形态)", "en": "📂 pattern"},
    "feat_cat_unknown": {"cn": "📂 unknown", "en": "📂 unknown"},
}

# ══════════════════════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════════════════════


def t(text_key: str, **kwargs) -> str:
    """
    获取当前语言的文本。

    Args:
        text_key: 文本键
        **kwargs: 可选的格式化参数（用于动态文本）

    Returns:
        当前语言的文本字符串。如果 text_key 不存在，返回 text_key 本身。

    Examples:
        t("data_title")  # -> "📊 数据中心" (cn) / "📊 Data Hub" (en)
        t("import_success", rows=500)  # -> "导入成功: 500 行 K 线数据"
    """
    lang = st.session_state.get("lang", "cn")
    entry = TEXT.get(text_key)
    if entry is None:
        return text_key
    text = entry.get(lang, entry.get("cn", text_key))
    if kwargs:
        return text.format(**kwargs)
    return text


def init_lang() -> None:
    """初始化语言 session state。在每个页面 set_page_config 之后调用。"""
    if "lang" not in st.session_state:
        st.session_state.lang = "cn"


def lang_toggle() -> None:
    """渲染语言切换按钮。放在侧边栏顶部。"""
    lang = st.session_state.get("lang", "cn")
    label = t("lang_en")
    if st.button(label, key="lang_toggle_btn", help="Switch language / 切换语言"):
        st.session_state.lang = "en" if lang == "cn" else "cn"
        st.rerun()


def get_factor_range_hint(feature_name: str) -> str:
    """获取因子的值范围提示文本。"""
    key = f"range_{feature_name}"
    return t(key)


def get_operator_name(op: str) -> str:
    """获取运算符的当前语言名称。"""
    mapping = {
        ">": "op_gt", "<": "op_lt", ">=": "op_gte", "<=": "op_lte",
        "==": "op_eq", "!=": "op_neq", "between": "op_between",
        "cross_above": "op_cross_above", "cross_below": "op_cross_below",
    }
    key = mapping.get(op)
    return t(key) if key else op


def get_feature_desc(feature_name: str) -> str:
    """获取因子的当前语言描述。"""
    key = f"feat_desc_{feature_name}"
    text = t(key)
    return text if text != key else ""


def get_category_display(cat: str) -> str:
    """获取分类名的当前语言显示。"""
    key = f"feat_cat_{cat}"
    text = t(key)
    return text if text != key else f"📂 {cat}"
