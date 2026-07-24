# 代码审查修复计划

> 来源：Standards + Spec 审查 | 日期：2026-07-19 | 状态：待执行

---

## 修复优先级

P0 = 崩溃/数据错误  
P1 = 功能缺失（用户可见）  
P2 = 代码质量（不影响运行）  
P3 = 增强（后期再做）

---

## P0 — 必须立即修复

### 1. `pages/2_🔧_Rule_Builder.py` — 函数定义在调用之后（崩溃）

**问题**：`_get_available_symbols()` 和 `_get_available_intervals()` 在 tab2 的渲染代码中被调用（~216 行），但定义在文件末尾（~269 行）。点击信号预览 tab 时触发 `NameError`。

**修复**：将两个函数移到文件最顶部（紧接 import 之后）。移除独立函数，直接在调用处内联 `hub.list_datasets()` 逻辑。

**文件**：`pages/2_🔧_Rule_Builder.py`
**行数**：216-218, 269-282

---

### 2. `feature/consecutive_up.py` — `period` 参数被静默忽略

**问题**：docstring 声明了 `period: int = 5`，`calculate(df, **params)` 接受 `**params`，但函数体内从未调用 `params.get("period")`。Rule Engine 传入的 `period` 参数没有任何效果。

**修复**：从 docstring 中移除 `period` 参数声明（该因子不需要周期参数），或实现 `period` 逻辑（用 `period` 替代固定计算）。

**文件**：`feature/consecutive_up.py`
**行数**：docstring 第 4 行，函数体

---

## P1 — 用户可见功能缺失

### 3. Rule Builder UI 缺少 `cross_above` / `cross_below` 运算符

**问题**：Rule Engine 支持 9 种运算符，但 Rule Builder 页面的下拉框只有 7 种。

**修复**：在 operator 下拉框中添加 `"cross_above"` 和 `"cross_below"`。

**文件**：`pages/2_🔧_Rule_Builder.py`
**行数**：~130

---

### 4. `Statistics.filter()` 缺少 `between` 运算符

**问题**：`Statistics.filter()` 只处理 6 种运算符，缺失 `between`、`cross_above`、`cross_below`。

**修复**：在 `filter()` 的 match-case 中添加缺失的运算符分支。

**文件**：`core/statistics.py`
**行数**：~145

---

### 5. Rule Builder 不支持嵌套规则

**问题**：`load_rule_to_editor()` 跳过嵌套 `RuleGroup`。编辑器只能构建单层条件。

**修复**：短期方案——在加载嵌套规则时显示警告"规则包含嵌套条件，编辑器仅展示顶层结构"。长期方案——重构编辑器支持嵌套 UI（Phase 2）。

**文件**：`pages/2_🔧_Rule_Builder.py`
**行数**：~81

---

## P2 — 代码质量（不影响运行）

### 6. 缺少类型注解

**位置**：
- `core/statistics.py:203` — `condition` 参数 → 加 `Callable[[Trade], bool]`
- `run_pipeline.py:72` — `main()` → 加 `-> int`
- `core/feature_registry.py:38` — `-> dict` → `-> dict[str, ...]`

**修复**：全部添加类型注解。

**文件**：上述 3 个文件，各 1 行

---

### 7. 测试函数缺少返回类型

**问题**：所有 `tests/*.py` 中的测试函数签名无 `-> None`。

**修复**：在所有 `def test_*` 后添加 `-> None`。批量操作，不改逻辑。

**文件**：`tests/test_*.py` (6 个文件，约 60 个函数)

---

### 8. `feature/volatility.py` import 顺序

**问题**：`numpy` 在 `polars` 之后，未按字母序。

**修复**：交换两行。

**文件**：`feature/volatility.py:18-19`

---

## P3 — 增强功能（后期）

### 9. Binance 数据下载
**PRD**："Binance 历史数据下载（可选）"
**现状**：`DataHub` 有方法占位，未实现
**评估**：Phase 2，需要 `python-binance` 依赖

### 10. 数据完整性检查 `check_integrity()`
**架构**：定义了但没有实现
**评估**：Phase 2 增强（检查时间戳连续性、重复等）

### 11. `Trade.entry_time` 类型
**问题**：存储为 `int` 索引而非 `datetime`
**评估**：不影响功能（可通过索引查 DataFrame），但需文档说明

### 12. 移除范围蔓延项
- `run_pipeline.py` — 保留（有用的 CLI 工具）
- 样本数据生成 — 保留（方便无数据时测试）
- `execute_single()` — 保留（Replay 会用）

---

## 修复后的验证

```bash
# 1. 单元测试
pytest tests/ -q

# 2. CLI 管线
python -X utf8 run_pipeline.py

# 3. Streamlit 启动
streamlit run main.py
# → 手动点 Rule Builder tab → 预览信号数（不崩溃）
# → Scanner → 完整扫描流程
```

---

## 修复顺序

```
Round 1: P0 (2 items, ~10 min)
Round 2: P1 (3 items, ~20 min)
Round 3: P2 (3 items, ~15 min)
Round 4: Verify all 107 tests still pass
```
