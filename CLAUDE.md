# CLAUDE.md — FactorLab 项目规则

> Claude Code 在每次会话启动时读取此文件，作为项目的"系统提示"。

---

## 项目身份

**FactorLab（因子实验室）** 是一个**完全离线、本地运行的交易系统验证平台**。

### 产品特性
- ✅ 完全离线运行
- ✅ 不连接交易所
- ✅ 不下单 / 不执行交易
- ✅ 不模拟账户
- ✅ 不需要用户系统
- ✅ 不需要实时行情

### 唯一目标

> 验证一个交易规则是否具有统计优势。

### 不是
- ❌ 自动交易平台
- ❌ 跟单系统
- ❌ 下单执行系统
- ❌ 实时行情终端

---

## 两种模式

### Mode 1：Replay（人工验证）
适合主观交易者。历史 K 线逐根回放，隐藏未来，用户手动决策买卖。
```
历史K线 → Replay Engine（隐藏未来） → 用户决策（买/卖/观望+SL+TP）
       → Trade Engine（验算结果） → Statistics
```

### Mode 2：Scanner（自动验证）
适合规则化策略。用户定义规则条件，系统自动扫描历史数据，找到所有符合的信号，自动生成交易并统计。
```
历史K线 → Scanner（自动扫描） → Rule Engine（信号匹配）
       → Trade Engine（自动执行） → Statistics
```

### 共享模块
- **Trade Engine**：Replay 和 Scanner 共用，统一计算入场/止损/止盈/结果
- **Rule Engine**：Scanner 模式下将规则条件编译为可执行的信号检测逻辑
- **Statistics**：两种模式输出相同的统计指标

---

## 核心架构

```
┌─────────────────────────────────────────────┐
│              Presentation Layer              │
│         Streamlit (3-4 Pages)                │
├─────────────────────────────────────────────┤
│   Replay Engine  │  Scanner Engine           │
│   (手工回放)      │  (自动扫描)               │
├──────────────────┴───────────────────────────┤
│            Rule Engine（规则引擎）            │
│       Feature Expression → Signal            │
├─────────────────────────────────────────────┤
│            Trade Engine（交易引擎）           │
│     Entry / SL / TP → Trade → Outcome        │
├──────────────────┬───────────────────────────┤
│  Feature Engine  │  Data Hub                  │
│  (因子计算)       │  (数据下载/缓存)           │
├──────────────────┴───────────────────────────┤
│            Data Layer                         │
│  Parquet (K线)  │  SQLite (Trade/Research)    │
└─────────────────────────────────────────────┘
```

---

## 六大核心模块

### ① Data Hub（数据中心）
- 导入历史 K 线（CSV / Parquet）
- 选择品种、周期、时间范围
- 本地缓存，完全离线

### ② Feature Engine（因子引擎）
- 所有因子统一接口：`calculate(df) -> Series`
- 插件化：新增因子 = 新增文件
- 内置因子：EMA、MACD、RSI、ATR、Bollinger、Volume、K线实体、影线、波动率等

### ③ Rule Engine（规则引擎）⭐ 核心
- 表达式引擎，将规则条件编译为可执行的信号检测
- 支持 AND / OR 嵌套组合
- 规则以 JSON 存储，可视化编辑器生成
- 不绑定具体因子，新增因子自动可用

### ④ Trade Engine（交易引擎）
- 统一处理 Replay 和 Scanner 产生的交易
- 定义 Entry / SL / TP 规则
- 自动判断先触发 TP 还是 SL
- 支持超时退出（持仓 N 根后按收盘价离场）
- 输出标准化 Trade 对象

### ⑤ Statistics（统计分析）
- 完全自动，无需手动配置
- 输出：胜率、盈亏比、Profit Factor、Expectancy、最大回撤、连续亏损、平均持仓、收益曲线
- 支持 Filter（筛选器）：按条件重新统计

### ⑥ Report（研究报告）
- 自动生成研究报告
- AI 总结关键发现
- 可导出

---

## 目标用户

**第一阶段：只有一个用户（开发者本人）**

### 坚决不做
- ❌ 用户系统 / 登录 / 注册
- ❌ 多账户
- ❌ 云同步 / 远程存储
- ❌ 权限管理
- ❌ 实时行情
- ❌ 交易所连接
- ❌ 下单执行
- ❌ 移动端

---

## 技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 数据科学生态 |
| 前端 | Streamlit | 交互式研究 UI，单用户最优 |
| 数据处理 | Polars | 快，内存效率高 |
| 可视化 | Plotly | 交互式图表 |
| K 线存储 | Parquet | 列存压缩，适合时序 |
| 元数据 | SQLite | 零配置，单文件 |
| 表达式 | 自研 JSON Rule | 轻量，可序列化，可审计 |

---

## 目录结构

```
F:\tarding\
├── CLAUDE.md
├── README.md
├── requirements.txt
├── main.py                    # Streamlit 入口
│
├── pages/                     # Streamlit 页面（自动多页路由）
│   ├── 1_📊_Data.py           # 数据中心
│   ├── 2_🔧_Rule_Builder.py   # 规则编辑器（核心）
│   └── 3_🔍_Scanner.py        # 自动扫描 + 结果
│
├── core/                      # 核心模块
│   ├── data_hub.py            # 数据中心
│   ├── feature_registry.py    # 因子注册表
│   ├── rule_engine.py         # 规则引擎（解析/编译/执行）
│   ├── trade_engine.py        # 交易引擎（模拟执行）
│   ├── statistics.py          # 统计分析
│   ├── replay_engine.py       # 回放引擎
│   ├── scanner.py             # 扫描器
│   └── db.py                  # SQLite 管理
│
├── feature/                   # 因子插件
│   ├── __init__.py
│   ├── ema.py
│   ├── macd.py
│   ├── rsi.py
│   ├── atr.py
│   ├── bollinger.py
│   ├── volume.py
│   ├── candle_body.py
│   ├── upper_shadow.py
│   ├── lower_shadow.py
│   ├── volatility.py
│   └── consecutive_up.py
│
├── rules/                     # 保存的规则模板（JSON）
│   ├── bollinger_break.json
│   └── macd_crossover.json
│
├── data/                      # 数据存储
│   ├── raw/                   # Parquet K线文件
│   └── factorlab.db           # SQLite
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT.md
│
└── tests/
```

---

## Rule Engine 设计（核心）

### 规则 JSON 格式

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
      "or": [
        {"feature": "macd_histogram", "operator": ">", "value": 0},
        {"feature": "volume_ratio", "operator": ">", "value": 1.5}
      ]
    }
  ]
}
```

### 设计原则

1. **表达式引擎，不绑定因子**：新增因子后自动可用，引擎无需修改
2. **支持嵌套**：AND / OR 可任意嵌套
3. **可序列化**：JSON 格式，可保存/加载/分享
4. **可视化编辑**：Rule Builder 页面生成 JSON，用户不写代码

---

## 插件开发规范

### Feature 插件

```python
"""
feature/bollinger_break.py - 布林带突破因子

参数:
    period: int = 20
    std_dev: float = 2.0

返回: Series[float]  突破百分比（正值=上破，负值=下破）
"""

import polars as pl

def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算价格突破布林带的百分比。

    正值表示价格在上轨之上（突破上轨），
    负值表示价格在下轨之下（跌破下轨）。

    Args:
        df: K 线 DataFrame，必须包含 close 列
        **params: period (int), std_dev (float)

    Returns:
        突破百分比 Series
    """
    period = params.get("period", 20)
    std_dev = params.get("std_dev", 2.0)

    mid = df["close"].rolling_mean(window_size=period)
    std = df["close"].rolling_std(window_size=period)
    upper = mid + std_dev * std

    return (df["close"] - upper) / upper * 100
```

### 规则
1. 函数签名：`calculate(df: pl.DataFrame, **params) -> pl.Series`
2. 纯函数：相同输入必须产生相同输出
3. 参数通过 `**params` 传递，提供默认值
4. 返回长度与输入 df 一致，前 N 行可为 null
5. 不读取文件、不访问数据库、不调用外部 API

---

## 编码规范

1. **类型注解**：所有函数必须有完整类型注解
2. **Docstring**：所有 public 函数有中文 docstring
3. **命名**：文件 `snake_case.py`，函数 `snake_case()`，类 `PascalCase`
4. **行宽**：120 字符
5. **注释**：中文注释可接受，解释"为什么"而非"做什么"
6. **纯函数优先**：因子计算必须是纯函数
7. **依赖注入**：不依赖全局状态

---

## Git 规范

- 分支：`main` → `feature/<name>` → `main`
- Commit：`type: description`（feat / fix / refactor / docs / test）
- 单人开发，不做 PR review

---

## 禁止事项

### 绝对不做
- ❌ 实时行情 / WebSocket
- ❌ 交易所 API 连接
- ❌ 下单 / 交易执行
- ❌ 用户系统 / 权限
- ❌ 云同步 / 远程存储
- ❌ Docker / 微服务 / 消息队列

### 编码禁止
- ❌ 因子代码中硬编码参数
- ❌ 因子代码中访问数据库/文件
- ❌ 全局可变状态
- ❌ 过早优化
