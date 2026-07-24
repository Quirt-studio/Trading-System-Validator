"""
tests/test_trade_engine.py — 交易引擎测试

覆盖:
  - 入场价: open/close/high/low/custom
  - 止损: fixed/atr/swing/custom
  - 止盈: rr/fixed/target/custom
  - 方向: long/short/both
  - 结果: tp/sl/timeout
  - R 倍数: 正确性验证
  - 因子快照: 入场时记录
  - 边界: 信号末尾、零持仓、无效价格
"""

import polars as pl
import pytest

from core.trade_engine import Trade, TradeConfig, TradeEngine
from core.strategies import FixedSL, ATRSL, SwingSL, CustomSL, BarExtremeSL, FixedRRTP, FixedPctTP, TargetTP, BollingerMidTP


# ── 测试用数据 ───────────────────────────────────

def _make_bull_df(n: int = 100) -> pl.DataFrame:
    """生成上升趋势数据（利于做多 TP 触发）。"""
    rows = []
    for i in range(n):
        base = 100.0 + i * 0.5  # 每根涨 0.5
        noise = (i % 3) * 0.2
        rows.append({
            "open": base,
            "high": base + 1.0 + noise,
            "low": base - 0.5 - noise * 0.5,
            "close": base + 0.3 + noise * 0.3,
            "volume": 1000.0 + i * 10,
        })
    return pl.DataFrame(rows)


def _make_flat_df(n: int = 200) -> pl.DataFrame:
    """生成平坦数据（验证不触发 SL/TP → timeout）。"""
    rows = [{
        "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
        "volume": 1000.0,
    }] * n
    return pl.DataFrame(rows)


def _make_sharp_drop_df(n: int = 50) -> pl.DataFrame:
    """生成单边下跌数据（测试做空）。"""
    rows = []
    for i in range(n):
        base = 100.0 - i * 1.0
        rows.append({
            "open": base + 0.2,
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base,
            "volume": 1000.0,
        })
    return pl.DataFrame(rows)


# ── Boolean signal helpers ────────────────────────

def _signals_at(df: pl.DataFrame, indices: list[int]) -> pl.Series:
    """创建指定位置为 True 的布尔信号序列。"""
    vals = [i in indices for i in range(df.height)]
    return pl.Series("signal", vals)


# ── Fixtures ──────────────────────────────────────

@pytest.fixture(scope="module")
def engine(feature_registry):
    return TradeEngine(feature_registry)


@pytest.fixture(scope="module")
def bull_df():
    return _make_bull_df(100)


# ── Entry Price Tests ─────────────────────────────

def test_entry_open(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(entry_type="open", max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 1
    assert trades[0].entry_price == pytest.approx(float(bull_df["open"][10]))


def test_entry_close(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(entry_type="close", max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert trades[0].entry_price == pytest.approx(float(bull_df["close"][10]))


def test_entry_high(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(entry_type="high", max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert trades[0].entry_price == pytest.approx(float(bull_df["high"][10]))


def test_entry_low(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(entry_type="low", max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert trades[0].entry_price == pytest.approx(float(bull_df["low"][10]))


def test_entry_custom(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(entry_type="custom", entry_offset=1.0, max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    expected = float(bull_df["close"][10]) * 1.01
    assert trades[0].entry_price == pytest.approx(expected)


# ── SL Type Tests ─────────────────────────────────

def test_sl_fixed_long(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(sl_strategy=FixedSL(pct=2.0), tp_strategy=FixedRRTP(rr=10.0),
                         entry_type="close", max_holding_bars=100)
    trades = engine.execute(signals, bull_df, config)
    entry = trades[0].entry_price
    assert trades[0].sl_price == pytest.approx(entry * 0.98)


def test_sl_atr(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [30])  # 足够后面有数据计算 ATR
    config = TradeConfig(sl_strategy=ATRSL(multiplier=2.0), tp_strategy=FixedRRTP(rr=10.0),
                         max_holding_bars=100)
    trades = engine.execute(signals, bull_df, config)
    # SL 应在 entry 之下
    assert trades[0].sl_price < trades[0].entry_price


def test_sl_swing(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [30])
    config = TradeConfig(sl_strategy=SwingSL(lookback=20), tp_strategy=FixedRRTP(rr=10.0),
                         max_holding_bars=100)
    trades = engine.execute(signals, bull_df, config)
    # swing SL 应为前 20 根最低点
    assert trades[0].sl_price == pytest.approx(bull_df["low"][10:31].min())


def test_sl_custom(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(sl_strategy=CustomSL(price=95.0), tp_strategy=FixedRRTP(rr=10.0),
                         max_holding_bars=100)
    trades = engine.execute(signals, bull_df, config)
    assert trades[0].sl_price == 95.0


# ── TP Type Tests ─────────────────────────────────

def test_tp_rr(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(
        entry_type="close", sl_strategy=FixedSL(pct=2.0),
        tp_strategy=FixedRRTP(rr=3.0), max_holding_bars=100,
    )
    trades = engine.execute(signals, bull_df, config)
    entry = trades[0].entry_price
    sl = trades[0].sl_price
    expected_tp = entry + (entry - sl) * 3.0
    assert trades[0].tp_price == pytest.approx(expected_tp)


def test_tp_fixed(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(
        entry_type="close", sl_strategy=FixedSL(pct=10.0),
        tp_strategy=FixedPctTP(pct=5.0), max_holding_bars=100,
    )
    trades = engine.execute(signals, bull_df, config)
    entry = trades[0].entry_price
    assert trades[0].tp_price == pytest.approx(entry * 1.05)


def test_tp_target(engine, bull_df) -> None:
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(
        sl_strategy=CustomSL(price=90.0),
        tp_strategy=TargetTP(price=120.0), max_holding_bars=100,
    )
    trades = engine.execute(signals, bull_df, config)
    assert trades[0].tp_price == 120.0


# ── 做多: 触 TP 先于 SL ─────────────────────────

def test_long_tp_hit(engine, bull_df) -> None:
    """上升趋势 + 宽松止损 + 紧止盈 → TP 触发。"""
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(
        direction="long", entry_type="close",
        sl_strategy=FixedSL(pct=20.0),  # 很宽松
        tp_strategy=FixedPctTP(pct=3.0),   # 3% 止盈
        max_holding_bars=100,
    )
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 1
    assert trades[0].result == "tp"
    assert trades[0].r_multiple > 0


# ── 做多: 触 SL ──────────────────────────────────

def test_long_sl_hit(engine) -> None:
    """单边下跌 → SL 触发。"""
    df = _make_sharp_drop_df(50)
    signals = _signals_at(df, [5])
    config = TradeConfig(
        direction="long", entry_type="close",
        sl_strategy=FixedSL(pct=2.0),    # 2% 止损
        tp_strategy=FixedPctTP(pct=50.0),   # 50% 不太可能触发
        max_holding_bars=100,
    )
    trades = engine.execute(signals, df, config)
    assert len(trades) == 1
    assert trades[0].result == "sl"
    assert trades[0].r_multiple == pytest.approx(-1.0)


# ── 超时退出 ─────────────────────────────────────

def test_long_timeout(engine) -> None:
    """平坦行情 → 不触发 SL 也不触发 TP → 超时。"""
    df = _make_flat_df(50)
    signals = _signals_at(df, [5])
    config = TradeConfig(
        direction="long", entry_type="close",
        sl_strategy=FixedSL(pct=5.0),
        tp_strategy=FixedPctTP(pct=5.0),
        max_holding_bars=10,
    )
    trades = engine.execute(signals, df, config)
    assert len(trades) == 1
    assert trades[0].result == "timeout"
    assert trades[0].holding_bars == 10


# ── 做空交易 ─────────────────────────────────────

def test_short_tp_hit(engine) -> None:
    """下跌趋势 + 做空 → TP 触发。"""
    df = _make_sharp_drop_df(50)
    signals = _signals_at(df, [5])
    config = TradeConfig(
        direction="short", entry_type="close",
        sl_strategy=FixedSL(pct=20.0),   # 宽松
        tp_strategy=FixedPctTP(pct=5.0),    # 5% 止盈
        max_holding_bars=100,
    )
    trades = engine.execute(signals, df, config)
    assert len(trades) == 1
    assert trades[0].direction == "short"
    assert trades[0].result == "tp"
    assert trades[0].r_multiple > 0


def test_short_sl_hit(engine) -> None:
    """上升趋势 + 做空 → SL 触发。"""
    df = _make_bull_df(50)
    signals = _signals_at(df, [5])
    config = TradeConfig(
        direction="short", entry_type="close",
        sl_strategy=FixedSL(pct=2.0),
        tp_strategy=FixedPctTP(pct=50.0),
        max_holding_bars=100,
    )
    trades = engine.execute(signals, df, config)
    assert len(trades) == 1
    assert trades[0].direction == "short"
    assert trades[0].result == "sl"


# ── 双向 ─────────────────────────────────────────

def test_both_direction(engine, bull_df) -> None:
    """both 方向：每一信号产生 2 笔交易（长+空）。"""
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(direction="both", max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 2
    dirs = {t.direction for t in trades}
    assert dirs == {"long", "short"}


# ── R 倍数验证 ───────────────────────────────────

def test_r_multiple_tp() -> None:
    """手动验证 R 倍数计算。"""
    df = pl.DataFrame({
        "open":  [100.0] * 20,
        "high":  [101.0] * 20,
        "low":   [99.0] * 20,
        "close": [100.0] * 20,
        "volume":[1000.0] * 20,
    })
    # 修改第 6 根（idx=5）：最高价突破 TP
    df = df.with_columns([
        pl.Series("high", [101.0]*5 + [106.0] + [101.0]*14),
    ])

    from core.feature_registry import FeatureRegistry
    from core.trade_engine import TradeEngine
    reg = FeatureRegistry()
    eng = TradeEngine(reg)

    signals = _signals_at(df, [3])
    config = TradeConfig(
        entry_type="close",
        sl_strategy=FixedSL(pct=2.0),     # SL = 98.0
        tp_strategy=FixedRRTP(rr=2.0),         # TP = 104.0  (2R)
        max_holding_bars=10,
    )
    trades = eng.execute(signals, df, config)
    assert len(trades) == 1
    # high=106 at idx=5 → TP=104 hit → exit at 104
    # R = 100-98=2, profit=104-100=4, R-multiple=4/2=2.0
    assert trades[0].result == "tp"
    assert trades[0].r_multiple == pytest.approx(2.0)


def test_r_multiple_sl() -> None:
    """手动验证 SL 的 R 倍数 = -1.0。"""
    df = pl.DataFrame({
        "open":  [100.0] * 20,
        "high":  [101.0] * 20,
        "low":   [99.0] * 20,
        "close": [100.0] * 20,
        "volume":[1000.0] * 20,
    })
    df = df.with_columns([
        pl.Series("low", [99.0]*5 + [97.0] + [99.0]*14),
    ])

    from core.feature_registry import FeatureRegistry
    from core.trade_engine import TradeEngine
    reg = FeatureRegistry()
    eng = TradeEngine(reg)

    signals = _signals_at(df, [3])
    config = TradeConfig(
        entry_type="close",
        sl_strategy=FixedSL(pct=2.0),     # SL = 98.0
        tp_strategy=FixedRRTP(rr=100.0),       # TP 很远
        max_holding_bars=10,
    )
    trades = eng.execute(signals, df, config)
    assert len(trades) == 1
    assert trades[0].result == "sl"
    assert trades[0].r_multiple == pytest.approx(-1.0)


# ── 因子快照 ─────────────────────────────────────

def test_feature_snapshot(engine, bull_df) -> None:
    """入场时记录所有因子的值。"""
    signals = _signals_at(bull_df, [30])
    config = TradeConfig(max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) > 0
    snap = trades[0].feature_snapshot
    assert len(snap) == 12
    assert "ema" in snap
    assert "rsi" in snap
    assert "volume" in snap
    # 快照值应与单独计算一致
    ema_val = engine._registry.calculate("ema", bull_df)[30]
    assert snap["ema"] == pytest.approx(float(ema_val))


# ── execute_single ────────────────────────────────

def test_execute_single(engine, bull_df) -> None:
    trade = engine.execute_single(10, bull_df, TradeConfig(max_holding_bars=5))
    assert trade is not None
    assert trade.entry_time == 10
    assert trade.direction == "long"


# ── 边界情况 ─────────────────────────────────────

def test_last_bar_signal(engine, bull_df) -> None:
    """最后几根 K 线有信号——剩余空间不足超时限制。"""
    last_idx = bull_df.height - 2
    signals = _signals_at(bull_df, [last_idx])
    config = TradeConfig(max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    # 应该产生交易（即使很快就超时退出）
    assert len(trades) == 1


def test_zero_holding_bars(engine, bull_df) -> None:
    """max_holding_bars=0 → 不限制，但会到数据末尾。"""
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(max_holding_bars=0)  # 不限制
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 1


def test_multiple_signals(engine, bull_df) -> None:
    """多个信号各自产生独立交易。"""
    signals = _signals_at(bull_df, [10, 20, 30])
    config = TradeConfig(max_holding_bars=5)
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 3
    assert trades[0].entry_time == 10
    assert trades[1].entry_time == 20
    assert trades[2].entry_time == 30


def test_empty_signals(engine, bull_df) -> None:
    """无信号 → 无交易。"""
    signals = _signals_at(bull_df, [])
    trades = engine.execute(signals, bull_df)
    assert trades == []


# ── 无效价格跳过 ─────────────────────────────────

def test_invalid_sl_price_skipped(engine, bull_df) -> None:
    """SL 高于 entry（做多）时跳过该信号。"""
    signals = _signals_at(bull_df, [10])
    config = TradeConfig(
        sl_strategy=CustomSL(price=200.0),  # SL 高于 entry
        max_holding_bars=5,
    )
    trades = engine.execute(signals, bull_df, config)
    assert len(trades) == 0  # 应该跳过，不崩溃
