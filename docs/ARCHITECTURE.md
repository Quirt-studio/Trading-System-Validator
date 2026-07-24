# FactorLab 技术架构文档

> 版本：v2.0 | 日期：2026-07-18

---

## 一、架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    Presentation Layer                         │
│                   Streamlit (4 Pages)                         │
│   Data │ Rule Builder │ Scanner │ Replay                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │   Replay    │  │   Scanner   │                            │
│  │   Engine    │  │   Engine    │                            │
│  │ (人工回放)   │  │ (自动扫描)   │                            │
│  └──────┬──────┘  └──────┬──────┘                            │
│         │                │                                   │
│         │     ┌──────────┘                                   │
│         │     │                                              │
│         ▼     ▼                                              │
│  ┌─────────────────────┐                                     │
│  │    Rule Engine      │  ← 规则编译 & 信号检测               │
│  │  (表达式引擎)        │                                     │
│  └─────────┬───────────┘                                     │
│            │                                                 │
│            ▼                                                 │
│  ┌─────────────────────┐                                     │
│  │    Trade Engine     │  ← 入场/止损/止盈/超时              │
│  │  (交易模拟引擎)      │                                     │
│  └─────────┬───────────┘                                     │
│            │                                                 │
│            ▼                                                 │
│  ┌─────────────────────┐                                     │
│  │    Statistics       │  ← 统计指标 + Filter + Report       │
│  │    + Filter         │                                     │
│  └─────────────────────┘                                     │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────┐                       │
│  │ Feature Engine  │  │  Data Hub    │                       │
│  │ (因子计算)       │  │ (数据管理)    │                       │
│  └─────────────────┘  └──────────────┘                       │
├──────────────────────────────────────────────────────────────┤
│                    Data Layer                                 │
│  Parquet Files (K线)  │  SQLite (Trade/Research/Rule)         │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、核心模块设计

### 2.1 Feature Engine（因子引擎）

#### 插件架构

```
core/feature_registry.py
    ↓ 启动时扫描 feature/ 目录
    ├── *.py 文件
    ├── 检查是否有 calculate 函数
    ├── 读取 docstring 提取元数据
    └── 注册到注册表
```

#### 注册表

```python
class FeatureRegistry:
    """因子注册表，启动时自动扫描并注册所有因子。"""

    def __init__(self, plugin_dir: Path):
        self._features: dict[str, FeatureMeta] = {}
        self._scan(plugin_dir)

    def _scan(self, dir: Path) -> None: ...
    def list_all(self) -> list[str]: ...
    def get(self, name: str) -> FeatureMeta: ...
    def calculate(self, name: str, df: pl.DataFrame, **params) -> pl.Series: ...
```

#### 接口契约

```python
def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    所有 Feature 的统一接口。

    Args:
        df: Polars DataFrame，包含 OHLCV 列
        **params: 因子参数（如 period=20, threshold=0.02）

    Returns:
        因子值 Series，长度与 df 一致，前 N 行可为 null
    """
```

---

### 2.2 Rule Engine（规则引擎）⭐

#### 架构

```
JSON Rule (用户定义)
    │
    ▼
RuleParser.parse(json_str) → RuleNode (AST)
    │
    ▼
RuleCompiler.compile(rule_node) → ExecutableRule
    │
    ▼
ExecutableRule.execute(df, feature_registry) → pl.Series[bool] (信号序列)
```

#### 数据结构

```python
from dataclasses import dataclass, field
from typing import Literal

Operator = Literal[">", "<", ">=", "<=", "==", "!=", "between", "cross_above", "cross_below"]
LogicOp = Literal["and", "or"]

@dataclass
class FeatureCondition:
    """单个特征条件"""
    feature: str           # 因子名称
    operator: Operator     # 比较运算符
    value: float | tuple[float, float]  # 阈值（between 时为元组）
    params: dict = field(default_factory=dict)  # 因子参数

@dataclass
class RuleGroup:
    """规则组（AND / OR 组合）"""
    logic: LogicOp
    conditions: list[FeatureCondition | "RuleGroup"]

# 顶层规则
Rule = RuleGroup
```

#### 执行逻辑

```python
class RuleEngine:
    def __init__(self, feature_registry: FeatureRegistry):
        self.registry = feature_registry

    def parse(self, rule_json: dict) -> RuleGroup:
        """解析 JSON 规则为 RuleGroup AST。"""
        ...

    def execute(self, rule: RuleGroup, df: pl.DataFrame) -> pl.Series:
        """
        在 DataFrame 上执行规则，返回布尔信号序列。
        True = 该 K 线满足所有条件，触发信号。
        """
        ...

    def count_signals(self, rule: RuleGroup, df: pl.DataFrame) -> int:
        """快速统计信号数量（用于规则预览）。"""
        ...
```

#### 规则编译为 Polars 表达式

```python
def _compile_condition(cond: FeatureCondition, df: pl.DataFrame, registry) -> pl.Series:
    """将单个条件编译为 Polars 布尔表达式并求值。"""
    series = registry.calculate(cond.feature, df, **cond.params)

    match cond.operator:
        case ">":
            return series > cond.value
        case "<":
            return series < cond.value
        case ">=":
            return series >= cond.value
        case "<=":
            return series <= cond.value
        case "==":
            return series == cond.value
        case "!=":
            return series != cond.value
        case "between":
            low, high = cond.value
            return (series >= low) & (series <= high)
        case "cross_above":
            return (series.shift(1) <= cond.value) & (series > cond.value)
        case "cross_below":
            return (series.shift(1) >= cond.value) & (series < cond.value)

def _compile_group(group: RuleGroup, df, registry) -> pl.Series:
    """递归编译规则组。"""
    results = []
    for item in group.conditions:
        if isinstance(item, FeatureCondition):
            results.append(_compile_condition(item, df, registry))
        else:
            results.append(_compile_group(item, df, registry))

    if group.logic == "and":
        result = results[0]
        for r in results[1:]:
            result = result & r
    else:  # "or"
        result = results[0]
        for r in results[1:]:
            result = result | r

    return result.fill_null(False)
```

---

### 2.3 Trade Engine（交易引擎）

#### 职责

Replay 和 Scanner 共享。输入信号列表 → 输出 Trade 列表。

```python
@dataclass
class TradeConfig:
    """交易配置 — 策略模式：SL/TP 各自由策略类管理参数"""

    direction: str = "long"         # long / short / both
    entry_type: str = "close"       # open / close / high / low / custom
    entry_offset: float = 0.0       # 自定义入场偏移（%）

    # 止损策略对象（管理自己的参数）
    sl_strategy: StopLossStrategy   # FixedSL(pct=2.0) | ATRSL(period=14, multiplier=1.0) | ...

    # 止盈策略对象（管理自己的参数，支持动态止盈）
    tp_strategy: TakeProfitStrategy # FixedRRTP(rr=2.0) | BollingerMidTP(period=20) | ...

    max_holding_bars: int = 50      # 超时退出（0 = 不限）
    time_exit_type: str = "close"   # 超时退出价格类型

# 策略插件：新增策略 = 新增类文件，无需修改 TradeConfig 和 TradeEngine
# 止损策略: FixedSL, ATRSL, SwingSL, BarExtremeSL, CustomSL
# 止盈策略: FixedRRTP, FixedPctTP, TargetTP, CustomTP, BollingerMidTP (动态)

@dataclass
class Trade:
    entry_time: int         # 入场 K 线索引
    exit_time: int          # 出场 K 线索引
    entry_price: float
    exit_price: float
    direction: str
    sl_price: float
    tp_price: float
    result: str             # "tp" | "sl" | "timeout"
    r_multiple: float
    holding_bars: int
    feature_snapshot: dict  # 入场时各因子值
```

#### 执行逻辑

```python
class TradeEngine:
    def __init__(self, feature_registry: FeatureRegistry): ...

    def execute(
        self,
        signals: pl.Series,        # 布尔信号序列
        df: pl.DataFrame,          # 完整 K 线数据
        config: TradeConfig,       # 包含 sl_strategy + tp_strategy
    ) -> list[Trade]:
        """
        对每个信号位置，模拟执行交易直到退出。
        SL/TP 逻辑委托给策略对象，引擎只负责入场和逐根扫描。

        对每个 True 信号：
        1. 计算 Entry Price
        2. config.sl_strategy.calculate() → SL Price
        3. config.tp_strategy.get_target_price() → TP Price（静态）
           或 config.tp_strategy.precompute() → 动态上下文
        4. 逐根扫描后续 K 线：
           a. 先触及 SL → 记录 SL 退出
           b. 静态 TP：先触及 TP → 记录 TP 退出
              动态 TP：tp_strategy.check_bar() 逐根重算
           c. 超过 max_holding_bars → 超时退出
        5. 记录入场时的因子快照
        """
        ...
```

#### 入场/出场规则（策略模式）

```
Entry Price:
  open   → 信号 K 线的开盘价
  close  → 信号 K 线的收盘价
  high   → 信号 K 线的最高价
  low    → 信号 K 线的最低价
  custom → 信号 K 线收盘价 × (1 + offset%)

SL 策略（StopLossStrategy.calculate()）:
  FixedSL      → Entry × (1 ± pct%)           # 固定百分比
  ATRSL        → Entry ± ATR × multiplier     # ATR 倍数
  SwingSL      → 前 N 根最低/最高点             # 摆动点
  BarExtremeSL → Entry bar high/low × (1 ± pct%)  # 入场 K 线极值
  CustomSL     → 自定义价格                     # 绝对值

TP 策略（静态 TakeProfitStrategy.get_target_price()）:
  FixedRRTP    → Entry ± (Entry - SL) × rr     # 固定 R:R
  FixedPctTP   → Entry × (1 ± pct%)            # 固定百分比
  TargetTP     → 目标价                         # 绝对值
  CustomTP     → 自定义价格                     # 绝对值

动态 TP（TakeProfitStrategy.check_bar() 逐根重算）:
  BollingerMidTP → 价格回到布林带中轨时止盈       # 每根 bar 重算条件

新增策略 = 新增类文件，TradeEngine 和 TradeConfig 零改动。
```

---

### 2.4 Scanner（扫描器）

```python
class Scanner:
    def __init__(
        self,
        rule_engine: RuleEngine,
        trade_engine: TradeEngine,
        feature_registry: FeatureRegistry,
    ): ...

    def scan(
        self,
        df: pl.DataFrame,
        rule: dict,          # JSON 规则
        trade_config: TradeConfig,
    ) -> ScanResult:
        """
        1. Rule Engine 执行规则 → 获取信号序列
        2. 过滤出 True 位置的索引列表
        3. 对每个信号，调用 Trade Engine 执行交易
        4. 收集所有 Trade
        5. 返回 ScanResult
        """
        ...

@dataclass
class ScanResult:
    rule_json: dict
    symbol: str
    interval: str
    date_range: tuple[str, str]
    signal_count: int
    trades: list[Trade]
    feature_snapshots: pl.DataFrame  # 所有信号点的因子值
```

---

### 2.5 Statistics（统计分析）

```python
@dataclass
class TradeStats:
    """交易统计结果"""
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float             # 胜率 %
    avg_win_r: float            # 平均盈利 R
    avg_loss_r: float           # 平均亏损 R
    avg_rr: float               # 平均盈亏比
    profit_factor: float        # 盈利因子
    expectancy: float           # 期望值 R
    max_drawdown_pct: float     # 最大回撤 %
    max_consecutive_loss: int   # 最大连续亏损
    avg_holding_bars: float     # 平均持仓 K 线数
    equity_curve: list[float]   # 权益曲线数据

class Statistics:
    def compute(self, trades: list[Trade]) -> TradeStats: ...

    def filter(
        self,
        trades: list[Trade],
        filter_rule: dict,       # JSON 规则（与 Rule Engine 通用）
        feature_snapshots: pl.DataFrame,
    ) -> list[Trade]:
        """按条件筛选 Trade，返回筛选后的子集。"""
        ...

    def recompute(self, filtered_trades: list[Trade]) -> TradeStats:
        """对筛选后的 Trade 重新统计。"""
        ...
```

---

### 2.6 Data Hub（数据中心）

```python
class DataHub:
    def import_csv(self, path: Path, symbol: str, interval: str) -> pl.DataFrame: ...
    def download_binance(self, symbol: str, interval: str, start: str, end: str) -> pl.DataFrame: ...
    def load(self, symbol: str, interval: str) -> pl.DataFrame: ...
    def list_datasets(self) -> list[dict]: ...
    def check_integrity(self, symbol: str, interval: str) -> dict: ...
```

---

## 三、数据流

### Scanner 完整流程

```
1. 数据准备
   DataHub.load("BTCUSDT", "4h") → pl.DataFrame (50,000 rows)

2. 规则编译
   RuleEngine.parse(json_rule) → RuleGroup AST

3. 信号扫描
   RuleEngine.execute(rule, df) → pl.Series[bool] (50,000 rows)
   统计: 438 个 True

4. 交易模拟
   TradeEngine.execute(signals, df, config, registry)
   → 438 笔 Trade 对象

5. 统计分析
   Statistics.compute(trades) → TradeStats
   Win Rate: 63.2%, Expectancy: 0.42R, Profit Factor: 1.84

6. 可选筛选
   Statistics.filter(trades, {"feature": "atr", "op": "<", "value": 2.0}, snapshots)
   → 215 笔 Trade
   Statistics.recompute(filtered_trades) → TradeStats

7. 结果缓存
   SQLite: scan_job + trade + trade_feature 表
```

### Replay 流程

```
1. 数据准备（同上）

2. Replay Engine 初始化
   - 随机选择起始位置
   - 隐藏该位置之后的所有 K 线

3. 用户看到当前 K 线 + 已计算因子 → 决策

4. 用户决策 → Trade 对象（手动 Entry/SL/TP）

5. Trade Engine 模拟执行 → 结果

6. 记录到 Research Database

7. 跳转到下一个随机位置 → 重复

8. 积累足够 Trade 后 → Statistics 分析
```

---

## 四、页面设计

### 页面 1：📊 Data
- `st.dataframe` 展示已有数据
- 下载按钮（Binance）
- CSV 上传组件
- 数据完整性指示

### 页面 2：🔧 Rule Builder
- 三栏布局：Feature | Operator | Value
- 已选规则列表（可删除）
- AND/OR 切换
- 保存到 `rules/*.json`
- 规则预览（快速统计信号数）

### 页面 3：🔍 Scanner
- 选择规则模板
- 选择品种/周期/时间范围
- Trade Config 面板（Entry/SL/TP 设置）
- 执行按钮
- 结果摘要卡片 + Plotly 图表
- Filter 面板

### 页面 4：▶️ Replay（第二优先级）
- K 线图（Plotly，隐藏未来）
- 因子指标叠加
- 决策面板（Buy/Sell/Pass + SL/TP）
- 统计面板（实时更新）

---

## 五、数据库设计

### SQLite（`data/factorlab.db`）

```
rule_template
├── id, name, config(JSON), created

scan_job
├── id, rule_json, symbol, interval, start_time, end_time, created

trade
├── id, scan_job_id(FK), direction, entry_time, entry_price,
│   exit_time, exit_price, sl_price, tp_price, result, r_multiple, holding_bars

trade_feature
├── trade_id(FK), feature_name, value   (联合主键)
```

### Parquet（`data/raw/`）

```
<SYMBOL>_<INTERVAL>.parquet
例: BTCUSDT_4h.parquet, ETHUSDT_1d.parquet
```

---

## 六、依赖

```
# requirements.txt
streamlit>=1.28
polars>=0.19
plotly>=5.17
pyarrow>=14.0
numpy>=1.26
scipy>=1.11
python-binance>=1.0.19   # 可选：下载历史数据
pytest>=7.4
```

---

## 七、性能目标

| 操作 | 目标 | 数据量 |
|------|------|--------|
| 因子计算 | < 50ms | 10 万行 |
| 规则扫描 | < 200ms | 10 万行 |
| 交易模拟 | < 500ms | 500 笔 Trade |
| 统计计算 | < 100ms | 500 笔 Trade |
| 端到端扫描 | < 3s | BTC 4H 3 年数据 |
