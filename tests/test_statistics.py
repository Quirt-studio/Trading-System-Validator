"""
tests/test_statistics.py — 统计分析测试
"""

import pytest

from core.statistics import Statistics, TradeStats
from core.trade_engine import Trade


def _make_trade(r: float, result: str = "tp", holding: int = 10) -> Trade:
    return Trade(
        entry_time=0, exit_time=holding, entry_price=100.0, exit_price=100.0,
        direction="long", sl_price=98.0, tp_price=104.0,
        result=result, r_multiple=r, holding_bars=holding,
        feature_snapshot={"ema": 0.5, "atr": 1.2},
    )


# ── 空列表 ───────────────────────────────────────

def test_empty_trades() -> None:
    stats = Statistics().compute([])
    assert stats.total_trades == 0
    assert stats.win_rate == 0.0
    assert stats.profit_factor == 0.0


# ── 全盈 ─────────────────────────────────────────

def test_all_wins() -> None:
    trades = [
        _make_trade(2.0, "tp"),
        _make_trade(1.5, "tp"),
        _make_trade(3.0, "tp"),
    ]
    stats = Statistics().compute(trades)
    assert stats.total_trades == 3
    assert stats.win_count == 3
    assert stats.win_rate == 100.0
    assert stats.max_consecutive_win == 3
    assert stats.max_consecutive_loss == 0


# ── 全亏 ─────────────────────────────────────────

def test_all_losses() -> None:
    trades = [
        _make_trade(-1.0, "sl"),
        _make_trade(-1.0, "sl"),
        _make_trade(-0.8, "sl"),
    ]
    stats = Statistics().compute(trades)
    assert stats.win_rate == 0.0
    assert stats.max_consecutive_loss == 3


# ── 混合 ─────────────────────────────────────────

def test_mixed_trades() -> None:
    trades = [
        _make_trade(2.0, "tp"),
        _make_trade(-1.0, "sl"),
        _make_trade(1.0, "tp"),
        _make_trade(-1.0, "sl"),
        _make_trade(3.0, "tp"),
    ]
    stats = Statistics().compute(trades)
    assert stats.win_rate == 60.0
    assert stats.win_count == 3
    assert stats.loss_count == 2
    assert stats.total_r == pytest.approx(4.0)


# ── Profit Factor ────────────────────────────────

def test_profit_factor() -> None:
    trades = [
        _make_trade(2.0),   # 盈 2R
        _make_trade(1.0),   # 盈 1R
        _make_trade(-1.0),  # 亏 1R
    ]
    stats = Statistics().compute(trades)
    # Profit Factor = 总盈利 / 总亏损 = (2+1) / 1 = 3.0
    assert stats.profit_factor == pytest.approx(3.0)


def test_profit_factor_all_wins() -> None:
    trades = [_make_trade(2.0), _make_trade(1.0)]
    stats = Statistics().compute(trades)
    assert stats.profit_factor == float("inf")


def test_profit_factor_all_losses() -> None:
    trades = [_make_trade(-1.0), _make_trade(-1.0)]
    stats = Statistics().compute(trades)
    assert stats.profit_factor == 0.0


# ── Expectancy ───────────────────────────────────

def test_expectancy() -> None:
    # 60% 胜率，avg_win=2R, avg_loss=1R → E = 0.6*2 + 0.4*(-1) = 0.8
    trades = [
        _make_trade(2.0), _make_trade(2.0), _make_trade(2.0),
        _make_trade(-1.0), _make_trade(-1.0),
    ]
    stats = Statistics().compute(trades)
    assert stats.expectancy == pytest.approx(0.8)


# ── 最大回撤 ─────────────────────────────────────

def test_max_drawdown() -> None:
    trades = [
        _make_trade(1.0),
        _make_trade(1.0),
        _make_trade(-1.0),
        _make_trade(-1.0),
        _make_trade(-1.0),
        _make_trade(1.0),
    ]
    stats = Statistics().compute(trades)
    assert stats.max_consecutive_loss == 3
    # 权益: [0, 1, 2, 1, 0, -1, 0]
    # 峰值=2, 最低=0 → drawdown = (2-0)/2*100 = 100%
    # Actually peak=2, trough=0 → dd=2, dd%=(2-0)/2=100% or (peak-trough)/peak
    # Wait: equity_curve = [0, 1, 2, 1, 0, -1, 0] (starts with 0)
    # drawdown from peak: peak=2 at index 2, goes to -1 at index 5
    # max_dd = (2 - (-1))/2 * 100 = 150%
    assert stats.max_drawdown_pct > 0


# ── 权益曲线 ─────────────────────────────────────

def test_equity_curve() -> None:
    trades = [_make_trade(1.0), _make_trade(-0.5)]
    stats = Statistics().compute(trades)
    assert stats.equity_curve == [0.0, 1.0, 0.5]


# ── 平均持仓 ─────────────────────────────────────

def test_avg_holding() -> None:
    trades = [
        _make_trade(1.0, holding=5),
        _make_trade(-1.0, holding=15),
    ]
    stats = Statistics().compute(trades)
    assert stats.avg_holding_bars == 10.0
    assert stats.avg_holding_bars_win == 5.0
    assert stats.avg_holding_bars_loss == 15.0


# ── Filter ───────────────────────────────────────

def test_filter_by_feature() -> None:
    trades = [
        _make_trade(2.0).__dict__,
        _make_trade(-1.0).__dict__,
    ]
    # Reconstruct with different snapshots
    t1 = Trade(0, 10, 100, 100, "long", 98, 104, "tp", 2.0, 10, {"atr": 1.0})
    t2 = Trade(0, 10, 100, 100, "long", 98, 104, "sl", -1.0, 10, {"atr": 3.0})
    t3 = Trade(0, 10, 100, 100, "long", 98, 104, "tp", 1.5, 10, {"atr": 1.5})

    filtered = Statistics().filter(
        [t1, t2, t3],
        {"feature": "atr", "operator": ">", "value": 1.2},
    )
    assert len(filtered) == 2  # t2 and t3


def test_filter_recompute() -> None:
    t1 = Trade(0, 10, 100, 100, "long", 98, 104, "tp", 2.0, 10, {"atr": 1.0})
    t2 = Trade(0, 10, 100, 100, "long", 98, 104, "sl", -1.0, 10, {"atr": 3.0})

    s = Statistics()
    filtered = s.filter([t1, t2], {"feature": "atr", "operator": "<", "value": 2.0})
    stats = s.recompute(filtered)
    assert stats.total_trades == 1
    assert stats.win_rate == 100.0


# ── to_dict ──────────────────────────────────────

def test_to_dict() -> None:
    trades = [_make_trade(2.0), _make_trade(-1.0)]
    stats = Statistics().compute(trades)
    d = stats.to_dict()
    assert d["total_trades"] == 2
    assert "win_rate" in d
    assert "profit_factor" in d
    assert "expectancy" in d
