# FactorLab 开发规范

> 版本：v2.0 | 日期：2026-07-18

---

## 一、Python 编码规范

### 1.1 类型注解

**强制**：所有函数必须有完整类型注解。

```python
# ✅ 正确
def calculate(df: pl.DataFrame, period: int = 20) -> pl.Series: ...

# ❌ 错误
def calculate(df, period=20): ...
```

### 1.2 Docstring

**强制**：所有 public 函数必须有中文 docstring。

```python
def calculate(df: pl.DataFrame, period: int = 20, std_dev: float = 2.0) -> pl.Series:
    """
    计算布林带突破因子。

    返回价格相对于布林带上轨的偏离百分比。
    正值 = 突破上轨（潜在超买），负值 = 跌破下轨（潜在超卖）。

    Args:
        df: K 线 DataFrame，必须包含 close 列。
        period: 布林带周期，默认 20。
        std_dev: 标准差倍数，默认 2.0。

    Returns:
        突破百分比 Series。前 period-1 个值为 null。
        值域参考：约 [-5%, +5%]。
    """
```

### 1.3 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | `snake_case` | `bollinger_break.py` |
| 函数 | `snake_case` | `calculate_feature()` |
| 类 | `PascalCase` | `RuleEngine` |
| 常量 | `UPPER_SNAKE` | `DEFAULT_PERIOD` |
| 私有 | `_snake_case` | `_validate_params()` |

### 1.4 行宽与格式

- 120 字符
- 标准库 → 第三方库 → 项目内部，分组空行分隔

### 1.5 注释原则

解释**为什么**，不重复**做什么**。

```python
# ✅ 好的注释
# 用 midprice 而非 close，避免极端 tick 的偏差
midprice = (df["high"] + df["low"]) / 2

# ❌ 差的注释
# 计算中间价
midprice = (df["high"] + df["low"]) / 2
```

---

## 二、Feature 插件开发规范

### 2.1 文件模板

```python
"""
feature/<name>.py - <简短描述>

分类:
    momentum | volatility | volume | pattern | composite

参数:
    param1: type = default  描述
    param2: type = default  描述

所需数据列:
    close, high, low, volume  (标注实际需要的)

示例:
    >>> import polars as pl
    >>> df = pl.read_parquet("data/raw/BTCUSDT_4h.parquet")
    >>> result = calculate(df, period=20, std_dev=2.0)
"""

import polars as pl

DEFAULT_PERIOD = 20

def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """计算 XXX 因子的值。"""
    period = params.get("period", DEFAULT_PERIOD)
    # 实现...
    return result
```

### 2.2 核心规则

1. **签名**：`calculate(df: pl.DataFrame, **params) -> pl.Series`
2. **纯函数**：相同输入 = 相同输出，无副作用
3. **参数**：通过 `**params` 和 `.get()` 提供默认值，不硬编码
4. **返回值**：长度与 df 一致，前 N 行可为 null
5. **禁止**：不读文件、不访问 DB、不调 API、不用全局变量

### 2.3 检查清单

- [ ] 文件位于 `feature/` 目录
- [ ] 实现 `calculate(df, **params) -> Series`
- [ ] 完整 docstring（含参数和返回值说明）
- [ ] 提供默认参数
- [ ] 边界处理（短数据返回 null）
- [ ] 对应测试在 `tests/test_features.py`

### 2.4 新增 Feature 的步骤

```bash
# 1. 创建文件
touch feature/my_new_feature.py

# 2. 实现 calculate 函数（参考模板）

# 3. 重启 Streamlit（自动注册）
# 无需修改任何其他文件

# 4. Rule Builder 中自动出现此因子
```

---

## 三、Rule 规则文件规范

### 3.1 规则 JSON Schema

```json
{
  "and": [
    {
      "feature": "<因子名>",
      "operator": "<运算符>",
      "value": <阈值>,
      "params": {<因子参数>}
    }
  ]
}
```

### 3.2 支持的运算符

| 运算符 | 含义 | value 类型 |
|--------|------|------------|
| `>` | 大于 | float |
| `<` | 小于 | float |
| `>=` | 大于等于 | float |
| `<=` | 小于等于 | float |
| `==` | 等于 | float |
| `!=` | 不等于 | float |
| `between` | 在范围内 | [float, float] |
| `cross_above` | 上穿 | float |
| `cross_below` | 下穿 | float |

### 3.3 规则文件存储

- 目录：`rules/`
- 格式：`<name>.json`
- 编码：UTF-8
- 可版本控制（Git 友好）

### 3.4 规则编写建议

1. **先简单后复杂**：从 1-2 个条件开始验证，再叠加
2. **避免过拟合**：条件越多，样本越少
3. **保持可读性**：给规则起有意义的名字
4. **参数文档化**：在 `params` 中标明参数的含义

---

## 四、Trade 交易记录规范

### 4.1 Trade 对象

```python
@dataclass
class Trade:
    entry_time: int          # K 线索引（0-based）
    exit_time: int           # K 线索引
    entry_price: float
    exit_price: float
    direction: str           # "long" | "short"
    sl_price: float
    tp_price: float
    result: str              # "tp" | "sl" | "timeout"
    r_multiple: float        # R 倍数 = 盈亏 / 初始风险
    holding_bars: int        # 持仓 K 线数
    feature_snapshot: dict   # {feature_name: value, ...}
```

### 4.2 R 倍数计算

```
做多:
  风险 R = Entry - SL
  盈亏 = Exit - Entry
  R 倍数 = 盈亏 / R

做空:
  风险 R = SL - Entry
  盈亏 = Entry - Exit
  R 倍数 = 盈亏 / R
```

- R > 0 = 盈利
- R < 0 = 亏损
- R ≈ -1 = 触发止损
- R ≈ +2 = 触发 2R 止盈
- R 在 (-1, 0) 之间 = 超时退出但未到止损

---

## 五、Trade Engine 配置规范

### 5.1 TradeConfig

```python
@dataclass
class TradeConfig:
    direction: str = "long"          # long / short / both
    entry_type: str = "close"        # open / close / high / low / custom
    entry_offset: float = 0.0        # 自定义入场偏移

    sl_type: str = "fixed"           # fixed / atr / swing / custom
    sl_value: float = 2.0            # 含义取决于 sl_type

    tp_type: str = "rr"              # rr / fixed / target / custom
    tp_value: float = 2.0            # 含义取决于 tp_type

    max_holding_bars: int = 50       # 超时退出
    time_exit_type: str = "close"    # 超时时按什么价格退出
```

### 5.2 配置组合示例

```python
# 经典 2R 策略
TradeConfig(
    direction="long",
    entry_type="close",
    sl_type="fixed", sl_value=2.0,     # 2% 止损
    tp_type="rr", tp_value=2.0,         # 2R 止盈
    max_holding_bars=100,
)

# ATR 止损 + 固定 RR
TradeConfig(
    direction="long",
    entry_type="close",
    sl_type="atr", sl_value=2.0,       # 2x ATR 止损
    tp_type="rr", tp_value=3.0,         # 3R 止盈
    max_holding_bars=50,
)

# 摆动低点止损 + 固定百分比止盈
TradeConfig(
    direction="long",
    entry_type="close",
    sl_type="swing", sl_value=20,       # 前 20 根最低点
    tp_type="fixed", tp_value=5.0,      # 固定 5% 止盈
    max_holding_bars=0,                 # 不限时
)
```

---

## 六、测试规范

### 6.1 测试结构

```
tests/
├── conftest.py                # 共享 fixtures（样本 df）
├── test_features.py           # 每个因子至少 3 个测试
├── test_rule_engine.py        # 规则引擎测试
├── test_trade_engine.py       # 交易引擎测试
├── test_statistics.py         # 统计计算测试
└── data/
    └── sample_klines.parquet  # 1000 行样本数据
```

### 6.2 Feature 测试必须覆盖

1. **基本计算**：已知输入 → 验证输出值
2. **边界情况**：数据不足 → 返回 null
3. **长度一致**：输出长度 == 输入长度
4. **参数变化**：不同参数产生不同结果
5. **极端数据**：全相同价格、单边暴涨、单边暴跌

### 6.3 Rule Engine 测试

```python
def test_simple_rule_greater_than(): ...
def test_and_combination(): ...
def test_or_combination(): ...
def test_nested_and_or(): ...
def test_cross_above_detection(): ...
def test_empty_result_when_no_match(): ...
```

### 6.4 Trade Engine 测试

```python
def test_long_trade_hits_tp(): ...    # 先触 TP
def test_long_trade_hits_sl(): ...    # 先触 SL
def test_trade_timeout(): ...         # 超时退出
def test_r_multiple_calculation(): ... # R 倍数计算正确
def test_short_trade_hits_tp(): ...   # 做空测试
```

### 6.5 运行测试

```bash
pytest                              # 全部
pytest tests/test_features.py -v    # 只测因子
pytest --cov=core --cov=feature     # 带覆盖率
```

---

## 七、Git 工作流

### 7.1 分支策略

```
main ──────────────────────────────
  ├── feature/add-super-trend ──→ merge
  ├── fix/rule-parser-bug ──────→ merge
  └── docs/update-architecture ─→ merge
```

### 7.2 Commit 格式

```
<type>: <description>

类型: feat / fix / refactor / docs / test / chore / style

示例:
  feat: add supertrend factor
  feat: implement rule engine parser
  fix: handle null values in trade engine
  refactor: extract shared logic to TradeEngine base
  docs: update architecture with rule engine design
  test: add edge cases for statistics module
```

### 7.3 提交前检查

- [ ] `pytest` 全部通过
- [ ] 新代码有类型注解
- [ ] 新因子有测试覆盖
- [ ] 没有调试代码（print / breakpoint）
- [ ] 没有引入禁止的依赖

---

## 八、数据管道规范

### 8.1 Parquet 存储

```
data/raw/<SYMBOL>_<INTERVAL>.parquet

标准列:
  open_time, open, high, low, close, volume,
  close_time, quote_volume, trades,
  taker_buy_volume, taker_buy_quote_volume
```

### 8.2 数据导入

- CSV：自动检测列映射，支持标准 Binance/ TradingView 导出格式
- Binance API：增量下载，断点续传
- 幂等：重复导入不产生重复数据

### 8.3 数据质量

- 检查时间戳连续性
- 检查重复时间戳
- 检查 OHLC 逻辑（high >= max(open, close), low <= min(open, close)）

---

## 九、环境配置

```bash
# 创建环境
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # macOS/Linux

# 安装
pip install -r requirements.txt

# 运行
streamlit run main.py

# 测试
pytest
```

### VS Code 推荐设置

```json
{
  "python.linting.mypyEnabled": true,
  "editor.rulers": [120],
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true
  }
}
```

---

## 十、禁止事项

### 架构禁止
- ❌ 微服务 / 消息队列 / 分布式
- ❌ Docker / K8s
- ❌ Redis / MongoDB / PostgreSQL
- ❌ FastAPI / Django / React

### 功能禁止
- ❌ 用户系统 / 权限
- ❌ 实时行情 / WebSocket
- ❌ 交易所连接 / 下单
- ❌ 移动端 / 多语言

### 代码禁止
- ❌ 因子中硬编码参数
- ❌ 因子中访问 DB / 文件 / API
- ❌ 全局可变状态
- ❌ 过早优化
- ❌ 过度抽象（KISS 优先）

---

## 十一、Review 检查清单

### 新 Feature
- [ ] 纯函数，无副作用
- [ ] 参数通过 `**params` 传递
- [ ] 默认值完善
- [ ] 边界处理正确
- [ ] 有测试
- [ ] Docstring 完整

### 新 Core 模块
- [ ] 类型注解完整
- [ ] 有单元测试
- [ ] 不引入新外部依赖（除非必要）
- [ ] 与现有架构一致
