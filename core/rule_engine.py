"""
core/rule_engine.py — 规则引擎

将 JSON 规则编译为可执行的信号检测逻辑。

规则 JSON 格式:
    {
      "and": [
        {"feature": "bollinger_break", "operator": ">", "value": 2.0, "params": {"period": 20}},
        {"feature": "volume_ratio", "operator": ">", "value": 1.5},
        {"or": [
          {"feature": "macd_histogram", "operator": ">", "value": 0},
          {"feature": "rsi", "operator": "<", "value": 30}
        ]}
      ]
    }

支持的运算符: >, <, >=, <=, ==, !=, between, cross_above, cross_below
支持嵌套: AND / OR 可任意深度嵌套

用法:
    from core.rule_engine import RuleEngine
    from core.feature_registry import FeatureRegistry

    registry = FeatureRegistry()
    engine = RuleEngine(registry)

    rule_dict = {"and": [{"feature": "ema", "operator": ">", "value": 1.0}]}
    signals = engine.execute(rule_dict, df)
    print(f"找到 {signals.sum()} 个信号")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Union

import polars as pl

if TYPE_CHECKING:
    from core.feature_registry import FeatureRegistry

# ── 类型定义 ──────────────────────────────────────

FeatureOperator = Literal[
    ">", "<", ">=", "<=", "==", "!=",
    "between", "cross_above", "cross_below",
]

LogicOperator = Literal["and", "or"]


@dataclass
class FeatureCondition:
    """单个因子条件。

    feature: 因子名称
    operator: 比较运算符
    value: 阈值（between 时为 (low, high)）
    params: 传递给因子的参数
    """
    feature: str
    operator: FeatureOperator
    value: float | tuple[float, float]
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_ops = {">", "<", ">=", "<=", "==", "!=", "between", "cross_above", "cross_below"}
        if self.operator not in valid_ops:
            raise ValueError(f"无效运算符 '{self.operator}'，合法值: {sorted(valid_ops)}")
        if not self.feature or not isinstance(self.feature, str):
            raise ValueError(f"feature 必须是非空字符串，收到: {self.feature!r}")
        if self.operator == "between":
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise ValueError(
                    f"between 需要 (low, high) 二元组，收到: {self.value!r}"
                )
            if not all(isinstance(x, (int, float)) for x in self.value):
                raise ValueError(f"between 阈值必须为数字: {self.value}")
            if self.value[0] > self.value[1]:
                raise ValueError(
                    f"between low ({self.value[0]}) > high ({self.value[1]})"
                )
        else:
            if not isinstance(self.value, (int, float)):
                raise ValueError(
                    f"运算符 '{self.operator}' 的 value 必须是数字，收到: {self.value!r}"
                )


@dataclass
class RuleGroup:
    """规则组（AND / OR 组合）。

    logic: "and" 或 "or"
    conditions: 子条件列表（可以是 FeatureCondition 或嵌套 RuleGroup）
    """
    logic: LogicOperator
    conditions: list[FeatureCondition | RuleGroup]


# ── 验证 ──────────────────────────────────────────

def _validate_condition(cond: dict) -> bool:
    """验证单个条件字典的字段完整性。"""
    required = {"feature", "operator", "value"}
    if not all(k in cond for k in required):
        return False
    valid_ops = {">", "<", ">=", "<=", "==", "!=", "between", "cross_above", "cross_below"}
    if cond["operator"] not in valid_ops:
        return False
    # between 必须提供 (low, high) 且 low <= high
    if cond["operator"] == "between":
        v = cond["value"]
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            return False
        if not all(isinstance(x, (int, float)) for x in v):
            return False
        if v[0] > v[1]:
            return False
    else:
        # 非 between 运算符：value 必须是数字
        if not isinstance(cond["value"], (int, float)):
            return False
    return True


def _validate_rule(rule_dict: dict) -> bool:
    """验证规则 JSON 的结构合法性。"""
    if not isinstance(rule_dict, dict):
        return False

    has_and = "and" in rule_dict
    has_or = "or" in rule_dict

    # 必须恰好包含一个逻辑键
    if has_and and has_or:
        return False
    if not has_and and not has_or:
        return False

    items = rule_dict["and"] if has_and else rule_dict["or"]

    if not isinstance(items, list) or len(items) == 0:
        return False

    for item in items:
        if "and" in item or "or" in item:
            if not _validate_rule(item):
                return False
        else:
            if not _validate_condition(item):
                return False

    return True


# ── 解析 ──────────────────────────────────────────

def _parse_condition(cond_dict: dict) -> FeatureCondition:
    """将条件字典解析为 FeatureCondition。"""
    return FeatureCondition(
        feature=cond_dict["feature"],
        operator=cond_dict["operator"],
        value=cond_dict["value"],
        params=cond_dict.get("params", {}),
    )


def _parse_rule(rule_dict: dict) -> RuleGroup:
    """将规则 JSON 字典递归解析为 RuleGroup AST。"""
    if "and" in rule_dict:
        logic: LogicOperator = "and"
        items = rule_dict["and"]
    elif "or" in rule_dict:
        logic = "or"
        items = rule_dict["or"]
    else:
        raise ValueError(f"规则 JSON 必须包含 'and' 或 'or' 键，收到: {list(rule_dict.keys())}")

    conditions: list[FeatureCondition | RuleGroup] = []
    for item in items:
        if "and" in item or "or" in item:
            conditions.append(_parse_rule(item))
        else:
            conditions.append(_parse_condition(item))

    return RuleGroup(logic=logic, conditions=conditions)


# ── 因子收集（用于验证） ────────────────────────────

def _collect_features(rule_dict: dict) -> set[str]:
    """递归收集规则中引用的所有因子名称。"""
    features: set[str] = set()
    if "and" in rule_dict:
        items = rule_dict["and"]
    elif "or" in rule_dict:
        items = rule_dict["or"]
    else:
        return features

    for item in items:
        if "and" in item or "or" in item:
            features |= _collect_features(item)
        else:
            features.add(item["feature"])
    return features


# ── 编译 & 执行 ───────────────────────────────────

def _apply_operator(series: pl.Series, operator: str, value: float | tuple) -> pl.Series:
    """对单个 Series 应用比较运算符，返回布尔 Series。"""
    match operator:
        case ">":
            return series > value
        case "<":
            return series < value
        case ">=":
            return series >= value
        case "<=":
            return series <= value
        case "==":
            return series == value
        case "!=":
            return series != value
        case "between":
            low, high = value  # type: ignore[misc]
            return (series >= low) & (series <= high)
        case "cross_above":
            prev = series.shift(1)
            return (prev.fill_null(series) <= value) & (series > value)
        case "cross_below":
            prev = series.shift(1)
            return (prev.fill_null(series) >= value) & (series < value)
        case _:
            raise ValueError(f"不支持的运算符: {operator}")


def _execute_condition(
    cond: FeatureCondition,
    df: pl.DataFrame,
    registry: FeatureRegistry,
) -> pl.Series:
    """执行单个条件，返回布尔 Series。"""
    try:
        feature_series = registry.calculate(cond.feature, df, **cond.params)
    except Exception as e:
        raise ValueError(
            f"规则条件执行失败: feature='{cond.feature}', "
            f"operator='{cond.operator}', value={cond.value!r}, "
            f"params={cond.params} — {e}"
        ) from e

    return _apply_operator(feature_series, cond.operator, cond.value)


def _execute_group(
    group: RuleGroup,
    df: pl.DataFrame,
    registry: FeatureRegistry,
) -> pl.Series:
    """递归执行规则组，返回布尔 Series。"""
    results: list[pl.Series] = []

    for cond in group.conditions:
        if isinstance(cond, FeatureCondition):
            results.append(_execute_condition(cond, df, registry))
        elif isinstance(cond, RuleGroup):
            results.append(_execute_group(cond, df, registry))
        else:
            raise TypeError(f"未知条件类型: {type(cond)}")

    if not results:
        raise ValueError("RuleGroup 为空：至少需要一个条件")

    if group.logic == "and":
        # 全 True 才 True
        result = results[0]
        for r in results[1:]:
            result = result & r
    elif group.logic == "or":
        # 任一 True 即 True
        result = results[0]
        for r in results[1:]:
            result = result | r
    else:
        raise ValueError(f"不支持的逻辑运算符: {group.logic}")

    # 将 null 视为 False
    return result.fill_null(False)


# ── 序列化 ────────────────────────────────────────

def _condition_to_dict(cond: FeatureCondition) -> dict:
    """将 FeatureCondition 序列化为 JSON 兼容字典。"""
    d: dict = {
        "feature": cond.feature,
        "operator": cond.operator,
        "value": cond.value,
    }
    if cond.params:
        d["params"] = cond.params
    return d


def _group_to_dict(group: RuleGroup) -> dict:
    """将 RuleGroup 序列化为 JSON 兼容字典。"""
    items = []
    for c in group.conditions:
        if isinstance(c, FeatureCondition):
            items.append(_condition_to_dict(c))
        else:
            items.append(_group_to_dict(c))
    return {group.logic: items}


# ── RuleEngine 主类 ───────────────────────────────

class RuleEngine:
    """
    规则引擎：解析 → 编译 → 执行。

    不绑定具体因子。新增因子后自动可用，无需修改引擎。
    """

    def __init__(self, feature_registry: FeatureRegistry):
        self._registry = feature_registry

    @property
    def registry(self) -> FeatureRegistry:
        return self._registry

    # ── 公开 API ──

    def parse(self, rule_json: dict) -> RuleGroup:
        """
        将 JSON 规则解析为 RuleGroup AST。

        Args:
            rule_json: 规则字典（通常从 JSON 文件加载）

        Returns:
            RuleGroup 抽象语法树

        Raises:
            ValueError: 规则格式无效或引用了未注册的因子
        """
        if not _validate_rule(rule_json):
            raise ValueError(f"规则 JSON 格式无效: {rule_json}")
        unknown = [f for f in _collect_features(rule_json) if f not in self._registry]
        if unknown:
            raise ValueError(
                f"规则引用了未注册的因子: {unknown}。"
                f"可用因子: {self._registry.list_all()}"
            )
        return _parse_rule(rule_json)

    def validate(self, rule_json: dict) -> bool:
        """
        验证规则 JSON 格式是否合法。

        检查：结构合法性、运算符有效性、因子是否已注册。

        Args:
            rule_json: 规则字典

        Returns:
            True 如果格式合法
        """
        if not _validate_rule(rule_json):
            return False
        # 验证所有引用的因子都已注册
        for feature in _collect_features(rule_json):
            if feature not in self._registry:
                return False
        return True

    def execute(self, rule: dict | RuleGroup, df: pl.DataFrame) -> pl.Series:
        """
        在 DataFrame 上执行规则，返回布尔信号序列。

        True = 该 K 线满足所有条件。

        Args:
            rule: JSON 规则字典或已解析的 RuleGroup
            df: K 线 DataFrame

        Returns:
            布尔信号 Series，长度与 df 一致
        """
        if isinstance(rule, dict):
            group = self.parse(rule)
        elif isinstance(rule, RuleGroup):
            group = rule
        else:
            raise TypeError(f"rule 必须是 dict 或 RuleGroup，收到: {type(rule)}")

        return _execute_group(group, df, self._registry)

    def count_signals(self, rule: dict | RuleGroup, df: pl.DataFrame) -> int:
        """
        统计信号数量（用于规则预览）。

        Args:
            rule: JSON 规则字典或 RuleGroup
            df: K 线 DataFrame

        Returns:
            匹配的 K 线数量
        """
        signals = self.execute(rule, df)
        return signals.sum()

    def get_matched_indices(self, rule: dict | RuleGroup, df: pl.DataFrame) -> list[int]:
        """
        获取匹配信号的 K 线索引列表。

        Args:
            rule: JSON 规则字典或 RuleGroup
            df: K 线 DataFrame

        Returns:
            匹配位置的索引列表
        """
        signals = self.execute(rule, df)
        return [
            i for i, v in enumerate(signals.to_list())
            if v is True
        ]

    def to_json(self, rule: dict) -> dict:
        """
        标准化规则 JSON（解析 → 重新序列化）。

        可用于格式清洗。

        Args:
            rule: JSON 规则字典

        Returns:
            标准化的规则字典
        """
        group = self.parse(rule)
        return _group_to_dict(group)

    def list_available_features(self) -> list[str]:
        """返回所有可用于规则中的因子名称。"""
        return self._registry.list_all()
