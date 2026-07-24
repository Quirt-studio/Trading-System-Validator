# FactorLab 产品需求文档（PRD）

> 版本：v2.0 | 日期：2026-07-18 | 状态：Draft

---

## 一、产品定位（重新定义）

### 一句话

> **一个完全离线、本地运行的交易系统验证平台。**

### 特点

| 特性 | 说明 |
|------|------|
| ✅ 完全离线 | 不需要网络连接（除了下载数据） |
| ✅ 不连接交易所 | 不调用任何交易所 API |
| ✅ 不下单 | 不执行真实交易 |
| ✅ 不模拟账户 | 不跟踪虚拟资金 |
| ✅ 不需要用户系统 | 单用户本地运行 |
| ✅ 不需要实时行情 | 基于历史数据工作 |

### 唯一目标

> **验证一个交易规则是否具有统计优势。**

### 产品边界

这个产品只做一件事：**给定规则 → 扫描历史 → 输出统计结果**。

边界外的功能一概不做。

---

## 二、两种模式

### Mode 1：Replay（人工验证）

**适用场景**：主观交易者，想验证自己的盘感判断。

```
历史K线
    │
Replay Engine
（隐藏未来K线，随机跳转，逐根播放）
    │
    ├──→ 用户决策（买/卖/观望、设置 SL、TP）
    │
    └──→ 自动计算因子（MACD、ATR、布林等，作为决策快照）
    │
Trade Engine
（计算是否先止盈/止损、持仓时长、R倍数）
    │
Research Database
（Trade + Feature Snapshot + Outcome）
    │
Analyzer
（胜率、盈亏比、因子分析、AI总结）
```

**核心体验**：
- 看不见未来 K 线（防止 hindsight bias）
- 随机跳转到历史任意位置（避免按顺序记忆）
- 每次决策记录完整的因子快照
- 事后分析：哪些因子条件下你做得更好/更差

---

### Mode 2：Scanner（自动验证）

**适用场景**：有明确规则，想批量验证统计优势。

```
用户定义规则
    │
Scanner
（扫描历史K线，匹配规则条件）
    │
找到 N 个信号（如 438 个）
    │
Trade Engine
（自动为每个信号生成 Trade）
    │
Statistics
（自动统计全部结果）
    │
Filter（可选）
（按条件筛选后重新统计）
    │
Report
（自动生成研究报告）
```

---

## 三、六大核心模块

### ① Data Hub（数据中心）

**职责**：数据导入、管理、缓存

**功能**：
- 导入历史 K 线（CSV / Parquet）
- 选择交易品种（BTC、ETH 等）
- 选择周期（1m / 5m / 15m / 1h / 4h / 1d）
- 选择时间范围（如 2022-01-01 ~ 2025-12-31）
- 数据完整性检查
- 完全本地存储

**MVP 范围**：支持 CSV 导入 + Binance 历史数据下载（可选）

---

### ② Feature Engine（因子引擎）

**职责**：计算所有技术指标和自定义因子

**设计原则**：
- 所有因子统一接口：`calculate(df: DataFrame, **params) -> Series`
- 插件化：新增因子 = 新增 `.py` 文件，不修改系统
- 自动注册：启动时扫描 `feature/` 目录

**MVP 因子列表**：

| 分类 | 因子 | 说明 |
|------|------|------|
| 趋势 | EMA | 指数移动平均偏离 |
| 趋势 | MACD | MACD 线、信号线、柱状图 |
| 震荡 | RSI | 相对强弱指数 |
| 波动 | ATR | 平均真实波幅 |
| 波动 | Bollinger | 布林带（上轨/中轨/下轨/带宽） |
| 量价 | Volume Ratio | 成交量相对均量比 |
| 形态 | Candle Body | K 线实体占比 |
| 形态 | Upper Shadow | 上影线占比 |
| 形态 | Lower Shadow | 下影线占比 |
| 形态 | Close From High | 收盘价距最高价比例 |
| 统计 | Volatility | 历史波动率 |
| 统计 | Consecutive Up | 连续上涨天数 |

---

### ③ Rule Engine（规则引擎）⭐ 产品核心

**职责**：将用户定义的规则条件编译为可执行的信号检测逻辑

**设计理念**：
- 表达式引擎，不绑定具体因子
- 新增因子后自动可用，引擎无需修改
- 支持 AND / OR 任意嵌套

**规则 JSON 格式**：

```json
{
  "and": [
    {
      "feature": "bollinger_break",
      "operator": ">",
      "value": 2.0,
      "params": {"period": 20, "std_dev": 2.0}
    },
    {
      "feature": "close_from_high",
      "operator": "<",
      "value": 1.0
    },
    {
      "feature": "macd_histogram",
      "operator": ">",
      "value": 0
    },
    {
      "feature": "volume_ratio",
      "operator": ">",
      "value": 1.5
    }
  ]
}
```

**支持的运算符**：`>`, `<`, `>=`, `<=`, `==`, `!=`, `between`, `cross_above`, `cross_below`

**规则模板**：保存/加载 JSON 文件，可分享、可迭代。

---

### ④ Rule Builder（规则编辑器）

**职责**：可视化编辑规则，用户不写代码

**交互模型**：

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Feature   │   │  Operator   │   │    Value    │
├─────────────┤   ├─────────────┤   ├─────────────┤
│ Bollinger   │   │     >       │   │    2%       │
│ MACD        │   │     <       │   │    1%       │
│ EMA         │   │     >=      │   │    20       │
│ RSI         │   │     <=      │   │             │
│ ATR         │   │  Between    │   │             │
│ Volume      │   │ CrossAbove  │   │             │
│ ...         │   │ CrossBelow  │   │             │
└─────────────┘   └─────────────┘   └─────────────┘

[BollingerBreak > 2%]  [×]
[Close < UpperShadow 1%]  [×]
[MACD Histogram > 0]  [×]
[Volume > MA20]  [×]

[+ Add Rule]  [AND ▼]  [Save]  [Load]
```

**最终输出**：JSON 规则文件，交给 Rule Engine 执行。

---

### ⑤ Trade Engine（交易引擎）

**职责**：统一的交易模拟执行引擎（Replay 和 Scanner 共用）

**功能**：

| 配置项 | 选项 |
|--------|------|
| Entry（入场价） | Open / Close / High / Low / 自定义 |
| SL（止损） | 固定% / ATR倍数 / 前高前低 / 自定义价格 |
| TP（止盈） | 固定 RR / 固定% / 目标价 / 自定义价格 |
| Timeout（超时） | 持仓 N 根 K 线后按收盘价退出 |
| Direction | 仅做多 / 仅做空 / 双向 |

**输出**：每笔交易标准化为 Trade 对象

```python
@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: str          # "long" | "short"
    sl_price: float
    tp_price: float
    result: str             # "tp" | "sl" | "timeout"
    r_multiple: float       # R 倍数（盈亏比）
    holding_bars: int       # 持仓 K 线数
    feature_snapshot: dict  # 入场时的因子快照
```

---

### ⑥ Statistics（统计分析）

**职责**：自动统计所有交易结果

**输出指标**：

| 指标 | 说明 |
|------|------|
| Total Trades | 总交易笔数 |
| Win Rate | 胜率（%） |
| Average RR | 平均盈亏比 |
| Profit Factor | 盈利因子（总盈利/总亏损） |
| Expectancy | 期望值（R） |
| Max Drawdown | 最大回撤（%） |
| Max Consecutive Loss | 最大连续亏损笔数 |
| Avg Holding Bars | 平均持仓 K 线数 |
| Equity Curve | 权益曲线 |

**Filter（筛选器）**：
- 扫描后可继续按条件筛选（如 ATR < 2%）
- 筛选后自动重新统计
- 支持多轮筛选，观察结果变化

---

## 七、数据模型

### SQLite 表结构

```sql
-- 规则模板
CREATE TABLE rule_template (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    config    TEXT NOT NULL,       -- JSON 规则
    created   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 扫描任务
CREATE TABLE scan_job (
    id          INTEGER PRIMARY KEY,
    rule_json   TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    interval    TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 交易记录
CREATE TABLE trade (
    id            INTEGER PRIMARY KEY,
    scan_job_id   INTEGER REFERENCES scan_job(id),
    direction     TEXT NOT NULL,
    entry_time    TEXT NOT NULL,
    entry_price   REAL NOT NULL,
    exit_time     TEXT NOT NULL,
    exit_price    REAL NOT NULL,
    sl_price      REAL NOT NULL,
    tp_price      REAL NOT NULL,
    result        TEXT NOT NULL,   -- tp / sl / timeout
    r_multiple    REAL NOT NULL,
    holding_bars  INTEGER NOT NULL
);

-- 入场时的因子快照
CREATE TABLE trade_feature (
    trade_id    INTEGER REFERENCES trade(id),
    feature_name TEXT NOT NULL,
    value       REAL NOT NULL,
    PRIMARY KEY (trade_id, feature_name)
);
```

**关键**：K 线数据不进数据库，直接读 Parquet。

---

## 八、MVP 页面

### 页面一：📊 数据中心（Data）
- 已下载数据列表
- 导入 CSV / 下载历史数据
- 数据概览（品种、周期、时间范围、K线数）

### 页面二：🔧 规则编辑器（Rule Builder）
- 可视化组建规则
- 保存/加载规则模板
- 规则预览（匹配信号数估算）

### 页面三：🔍 策略扫描（Scanner）
- 选择规则模板
- 选择品种/周期/时间范围
- 配置 Trade Engine 参数（Entry/SL/TP）
- 执行扫描
- 展示统计结果 + 图表

### 页面四：▶️ 人工回放（Replay）—— 第二优先级
- 隐藏未来 K 线
- 用户手动决策
- 与 Scanner 共享 Trade Engine + Statistics

---

## 九、第二阶段路线图

1. **Replay Mode**（人工回放，第一版可暂缓）
2. **Advanced Filters**（多维度筛选器）
3. **Walk-Forward Analysis**（前向验证）
4. **Monte Carlo Simulation**（蒙特卡洛模拟）
5. **AI Report Generator**（AI 自动生成研究报告）
6. **Multi-Symbol Scanner**（跨品种扫描）

---

## 十、成功标准（MVP）

> 导入 BTC 4H 数据 → 用 Rule Builder 定义规则 → 扫描 2022~2025 → 3 秒内看到胜率、盈亏比、权益曲线。

不需要更多。
