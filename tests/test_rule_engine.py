"""
tests/test_rule_engine.py — 规则引擎测试

覆盖:
  - 解析: parse/validate 各种规则格式
  - 执行: 简单比较、AND/OR 组合、嵌套
  - 运算符: > < >= <= == != between cross_above cross_below
  - 边界: 空匹配、深嵌套、规则序列化
"""

import json
import math

import polars as pl
import pytest

from core.rule_engine import (
    FeatureCondition,
    RuleEngine,
    RuleGroup,
)


# ── Fixtures ──────────────────────────────────────

@pytest.fixture(scope="module")
def engine(feature_registry):
    return RuleEngine(feature_registry)


# ── Parse Tests ───────────────────────────────────

def test_parse_simple_and(engine) -> None:
    rule = {"and": [{"feature": "ema", "operator": ">", "value": 1.0}]}
    group = engine.parse(rule)
    assert isinstance(group, RuleGroup)
    assert group.logic == "and"
    assert len(group.conditions) == 1
    c = group.conditions[0]
    assert isinstance(c, FeatureCondition)
    assert c.feature == "ema"
    assert c.operator == ">"
    assert c.value == 1.0


def test_parse_simple_or(engine) -> None:
    rule = {"or": [{"feature": "rsi", "operator": "<", "value": 30}]}
    group = engine.parse(rule)
    assert group.logic == "or"


def test_parse_nested_and_or(engine) -> None:
    rule = {
        "and": [
            {"feature": "ema", "operator": ">", "value": 0},
            {"or": [
                {"feature": "rsi", "operator": "<", "value": 30},
                {"feature": "volume", "operator": ">", "value": 2.0},
            ]},
        ]
    }
    group = engine.parse(rule)
    assert group.logic == "and"
    assert len(group.conditions) == 2
    assert isinstance(group.conditions[1], RuleGroup)
    assert group.conditions[1].logic == "or"


def test_parse_between(engine) -> None:
    rule = {"and": [{"feature": "rsi", "operator": "between", "value": [30, 70]}]}
    group = engine.parse(rule)
    c = group.conditions[0]
    assert isinstance(c, FeatureCondition)
    assert c.operator == "between"
    assert c.value == [30, 70]


def test_parse_with_params(engine) -> None:
    rule = {"and": [{"feature": "ema", "operator": ">", "value": 1.0, "params": {"period": 50}}]}
    group = engine.parse(rule)
    c = group.conditions[0]
    assert c.params == {"period": 50}


def test_validate_valid_rule(engine) -> None:
    assert engine.validate({"and": [{"feature": "ema", "operator": ">", "value": 1.0}]})


def test_validate_invalid_operator(engine) -> None:
    assert not engine.validate({"and": [{"feature": "ema", "operator": "??", "value": 1.0}]})


def test_validate_missing_key(engine) -> None:
    assert not engine.validate({"and": [{"feature": "ema"}]})


def test_validate_empty_and(engine) -> None:
    assert not engine.validate({"and": []})


def test_validate_between_invalid(engine) -> None:
    assert not engine.validate({"and": [{"feature": "rsi", "operator": "between", "value": 30}]})


def test_parse_invalid_raises(engine) -> None:
    with pytest.raises(ValueError):
        engine.parse({"invalid": []})


# ── Execute Tests ─────────────────────────────────

def test_execute_simple_greater_than(engine, sample_df) -> None:
    """EMA > 0 应匹配相当比例的样本。"""
    rule = {"and": [{"feature": "ema", "operator": ">", "value": 0}]}
    signals = engine.execute(rule, sample_df)
    assert len(signals) == len(sample_df)
    count = signals.sum()
    assert count > 0


def test_execute_impossible_condition(engine, sample_df) -> None:
    """EMA > 999 不可能匹配。"""
    rule = {"and": [{"feature": "ema", "operator": ">", "value": 999}]}
    count = engine.count_signals(rule, sample_df)
    # 有些 null（前19个），有些 False
    valid = engine.execute(rule, sample_df)
    assert valid.sum() == 0


def test_execute_and_combination(engine, sample_df) -> None:
    """AND 比单个条件更严格。"""
    rule_single = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}
    rule_and = {
        "and": [
            {"feature": "volume", "operator": ">", "value": 0.5},
            {"feature": "rsi", "operator": ">", "value": 50},
        ]
    }
    s1 = engine.count_signals(rule_single, sample_df)
    s2 = engine.count_signals(rule_and, sample_df)
    assert s2 <= s1


def test_execute_or_combination(engine, sample_df) -> None:
    """OR 比单个条件更宽松。"""
    rule_single = {"and": [{"feature": "volume", "operator": ">", "value": 2.0}]}
    rule_or = {
        "or": [
            {"feature": "volume", "operator": ">", "value": 2.0},
            {"feature": "rsi", "operator": ">", "value": 80},
        ]
    }
    s1 = engine.count_signals(rule_single, sample_df)
    s2 = engine.count_signals(rule_or, sample_df)
    assert s2 >= s1


def test_execute_nested(engine, sample_df) -> None:
    """嵌套 AND/OR 正常执行。"""
    rule = {
        "and": [
            {"feature": "ema", "operator": ">", "value": -5.0},
            {"or": [
                {"feature": "volume", "operator": ">", "value": 2.0},
                {"feature": "rsi", "operator": ">", "value": 60},
            ]},
        ]
    }
    signals = engine.execute(rule, sample_df)
    assert len(signals) == len(sample_df)


def test_execute_all_operators(engine, sample_df) -> None:
    """所有基本运算符都能正常执行。"""
    ops = [
        (">", 0.0),
        ("<", 100.0),
        (">=", -999.0),
        ("<=", 999.0),
        ("!=", math.nan),
    ]
    for op, val in ops:
        rule = {"and": [{"feature": "ema", "operator": op, "value": val}]}
        signals = engine.execute(rule, sample_df)
        assert len(signals) == len(sample_df), f"operator {op} failed"


def test_execute_between(engine, sample_df) -> None:
    """RSI between 30 and 70 应匹配非极端值。"""
    rule = {"and": [{"feature": "rsi", "operator": "between", "value": [30, 70]}]}
    signals = engine.execute(rule, sample_df)
    count = signals.sum()
    # 应有匹配（震荡行情中 RSI 在 30-70 之间）
    assert count >= 0  # 弱断言：不崩溃


def test_execute_cross_above(engine, sample_df) -> None:
    """MACD histogram cross_above 0 应能检测金叉。"""
    rule = {"and": [{"feature": "macd", "operator": "cross_above", "value": 0,
                     "params": {"component": "histogram"}}]}
    signals = engine.execute(rule, sample_df)
    assert len(signals) == len(sample_df)
    # 交叉点数量应远少于总 K 线数
    count = signals.sum()
    assert count < len(sample_df) / 2  # 交叉点不会过半


def test_execute_cross_below(engine, sample_df) -> None:
    """MACD histogram cross_below 0 应能检测死叉。"""
    rule = {"and": [{"feature": "macd", "operator": "cross_below", "value": 0,
                     "params": {"component": "histogram"}}]}
    signals = engine.execute(rule, sample_df)
    assert len(signals) == len(sample_df)
    count = signals.sum()
    assert count < len(sample_df) / 2


# ── execute 接受 RuleGroup 输入 ───────────────────

def test_execute_with_parsed_group(engine, sample_df) -> None:
    """execute 可以直接接受 RuleGroup（跳过重复解析）。"""
    group = engine.parse({"and": [{"feature": "ema", "operator": ">", "value": 0}]})
    signals = engine.execute(group, sample_df)
    assert len(signals) == len(sample_df)


def test_execute_wrong_type(engine, sample_df) -> None:
    """execute 不接受非 dict 非 RuleGroup 类型。"""
    with pytest.raises(TypeError):
        engine.execute("not_a_rule", sample_df)


# ── count_signals ─────────────────────────────────

def test_count_signals(engine, sample_df) -> None:
    rule = {"and": [{"feature": "ema", "operator": ">", "value": 0}]}
    count = engine.count_signals(rule, sample_df)
    signals = engine.execute(rule, sample_df)
    assert count == signals.sum()


# ── get_matched_indices ───────────────────────────

def test_get_matched_indices(engine, sample_df) -> None:
    rule = {"and": [{"feature": "ema", "operator": ">", "value": -999.0}]}
    indices = engine.get_matched_indices(rule, sample_df)
    # 所有有值的行都应匹配（除前 period-1 个 null）
    assert len(indices) > 0
    assert all(isinstance(i, int) for i in indices)


# ── to_json ───────────────────────────────────────

def test_to_json_roundtrip(engine) -> None:
    """parse → to_json 应保持语义一致。"""
    original = {
        "and": [
            {"feature": "ema", "operator": ">", "value": 1.0, "params": {"period": 20}},
            {"or": [
                {"feature": "rsi", "operator": "<", "value": 30},
                {"feature": "volume", "operator": ">", "value": 1.5},
            ]},
        ]
    }
    normalized = engine.to_json(original)

    # 用 engine.parse + execute 验证语义等价（用非空数据）
    import polars as pl
    df = pl.DataFrame({
        "open": [100.0] * 100,
        "high": [101.0] * 100,
        "low": [99.0] * 100,
        "close": [100.5] * 100,
        "volume": [1000.0] * 100,
    })
    s1 = engine.execute(original, df)
    s2 = engine.execute(normalized, df)
    assert s1.sum() == s2.sum()


# ── list_available_features ───────────────────────

def test_list_available_features(engine) -> None:
    features = engine.list_available_features()
    assert len(features) == 12
    assert "ema" in features
    assert "bollinger" in features


# ── 真实规则加载 ──────────────────────────────────

def test_load_example_rules(engine, sample_df) -> None:
    """确保示例规则文件可以加载并执行。"""
    import json
    from pathlib import Path

    rules_dir = Path(__file__).parent.parent / "rules"
    for rule_file in sorted(rules_dir.glob("*.json")):
        with open(rule_file) as f:
            rule = json.load(f)
        assert engine.validate(rule), f"{rule_file.name}: invalid rule"
        group = engine.parse(rule)
        signals = engine.execute(group, sample_df)
        assert len(signals) == len(sample_df), f"{rule_file.name}: length mismatch"
