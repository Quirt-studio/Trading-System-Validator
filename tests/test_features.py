"""
tests/test_features.py — 所有 Feature 插件的单元测试

每个因子至少测试:
  1. 基本计算
  2. 输出长度与输入一致
  3. 边界情况（短数据）
  4. 参数变化产生不同结果
"""

import polars as pl
import pytest


# ── EMA ─────────────────────────────────────────

def test_ema_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("ema", sample_df, period=20)
    assert len(result) == len(sample_df)
    # 前 period-1 个值应为 null
    assert result[:19].null_count() > 0
    # 后面应有值
    assert result[20:].null_count() == 0


def test_ema_different_periods(sample_df, feature_registry) -> None:
    r1 = feature_registry.calculate("ema", sample_df, period=10)
    r2 = feature_registry.calculate("ema", sample_df, period=30)
    # 不同周期应产生不同结果
    assert not (r1[30:].to_list() == r2[30:].to_list())


def test_ema_short_data(feature_registry) -> None:
    df = pl.DataFrame({"close": [100.0, 101.0]})
    result = feature_registry.calculate("ema", df, period=20)
    assert len(result) == 2
    # 数据不足周期，全部为 null
    assert result.null_count() == 2


# ── MACD ────────────────────────────────────────

def test_macd_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("macd", sample_df)
    assert len(result) == len(sample_df)


def test_macd_components(sample_df, feature_registry) -> None:
    line = feature_registry.calculate("macd", sample_df, component="line")
    signal = feature_registry.calculate("macd", sample_df, component="signal")
    hist = feature_registry.calculate("macd", sample_df, component="histogram")
    assert len(line) == len(sample_df)
    assert len(signal) == len(sample_df)
    assert len(hist) == len(sample_df)


# ── RSI ─────────────────────────────────────────

def test_rsi_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("rsi", sample_df, period=14)
    assert len(result) == len(sample_df)
    # RSI 应在 [0, 100] 范围
    valid = result.drop_nulls()
    assert valid.min() >= 0
    assert valid.max() <= 100


def test_rsi_short_data(feature_registry) -> None:
    df = pl.DataFrame({"close": [100.0, 101.0, 102.0]})
    result = feature_registry.calculate("rsi", df, period=14)
    assert result.null_count() == 3


# ── ATR ─────────────────────────────────────────

def test_atr_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("atr", sample_df, period=14)
    assert len(result) == len(sample_df)
    # ATR 永远非负
    valid = result.drop_nulls()
    assert valid.min() >= 0


def test_atr_constant_price(feature_registry) -> None:
    """全相同价格时 ATR 应为 0。"""
    df = pl.DataFrame({
        "high": [10.0] * 50,
        "low": [10.0] * 50,
        "close": [10.0] * 50,
    })
    result = feature_registry.calculate("atr", df, period=14)
    valid = result.drop_nulls()
    assert valid.max() == 0.0


# ── Bollinger ───────────────────────────────────

def test_bollinger_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("bollinger", sample_df, period=20, std_dev=2.0)
    assert len(result) == len(sample_df)


def test_bollinger_different_std(sample_df, feature_registry) -> None:
    r1 = feature_registry.calculate("bollinger", sample_df, period=20, std_dev=1.0)
    r2 = feature_registry.calculate("bollinger", sample_df, period=20, std_dev=3.0)
    # 更大的标准差 → 突破更少（所有值更负）
    v1 = r1.drop_nulls().mean()
    v2 = r2.drop_nulls().mean()
    assert v2 is not None and v1 is not None
    assert v2 < v1  # 更宽的带 → 更难突破 → 更负


# ── Volume ──────────────────────────────────────

def test_volume_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("volume", sample_df, period=20)
    assert len(result) == len(sample_df)


def test_volume_constant_volume(feature_registry) -> None:
    df = pl.DataFrame({"volume": [1000.0] * 50})
    result = feature_registry.calculate("volume", df, period=10)
    valid = result.drop_nulls()
    # 近似 1.0
    assert abs(valid.mean() - 1.0) < 0.01


# ── Candle Body ─────────────────────────────────

def test_candle_body_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("candle_body", sample_df)
    assert len(result) == len(sample_df)


# ── Upper Shadow ────────────────────────────────

def test_upper_shadow_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("upper_shadow", sample_df)
    assert len(result) == len(sample_df)
    valid = result.drop_nulls()
    assert valid.min() >= 0
    assert valid.max() <= 100


# ── Lower Shadow ────────────────────────────────

def test_lower_shadow_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("lower_shadow", sample_df)
    assert len(result) == len(sample_df)
    valid = result.drop_nulls()
    assert valid.min() >= 0
    assert valid.max() <= 100


# ── Volatility ──────────────────────────────────

def test_volatility_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("volatility", sample_df, period=20)
    assert len(result) == len(sample_df)
    valid = result.drop_nulls()
    assert valid.min() >= 0


# ── Consecutive Up ──────────────────────────────

def test_consecutive_up_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("consecutive_up", sample_df)
    assert len(result) == len(sample_df)
    valid = result.drop_nulls()
    # 都是非负整数
    assert valid.min() >= 0


def test_consecutive_up_known() -> None:
    """手动构造已知场景。"""
    from feature.consecutive_up import calculate
    df = pl.DataFrame({"close": [10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 15.0]})
    result = calculate(df)
    # 连续上涨: 0(第一根), 1, 2, 0(下跌), 1, 2, 3
    expected = [0, 1, 2, 0, 1, 2, 3]
    vals = result.to_list()
    for v, e in zip(vals, expected):
        assert v == e


# ── Close From High ─────────────────────────────

def test_close_from_high_basic(sample_df, feature_registry) -> None:
    result = feature_registry.calculate("close_from_high", sample_df)
    assert len(result) == len(sample_df)
    valid = result.drop_nulls()
    assert valid.min() >= 0


def test_close_from_high_known() -> None:
    """收盘=最高时比例为 0。"""
    from feature.close_from_high import calculate
    df = pl.DataFrame({
        "high": [110.0, 105.0],
        "close": [110.0, 100.0],
    })
    result = calculate(df)
    assert result[0] == 0.0
    assert abs(result[1] - (5.0 / 105.0 * 100)) < 0.01


# ── Feature Info ────────────────────────────────

def test_all_features_have_info(feature_registry) -> None:
    """所有因子都有元信息。"""
    for name in feature_registry.list_all():
        info = feature_registry.get_info(name)
        assert info is not None, f"{name} 缺少元信息"
        assert info.name == name
        assert info.category != "unknown", f"{name} 缺少分类"


def test_all_features_calculate(feature_registry, sample_df) -> None:
    """所有因子在样本数据上都能正常计算。"""
    for name in feature_registry.list_all():
        result = feature_registry.calculate(name, sample_df)
        assert len(result) == len(sample_df), f"{name}: 长度不匹配"
        assert result.dtype is not None, f"{name}: dtype is None"


def test_feature_count(feature_registry) -> None:
    """应有 12 个因子。"""
    assert len(feature_registry) == 12
