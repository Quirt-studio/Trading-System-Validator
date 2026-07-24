"""
tests/test_scanner.py — 扫描器测试
"""

import polars as pl
import pytest

from core.scanner import Scanner, ScanResult
from core.rule_engine import RuleEngine
from core.trade_engine import TradeEngine, TradeConfig


@pytest.fixture(scope="module")
def scanner(feature_registry):
    return Scanner(
        RuleEngine(feature_registry),
        TradeEngine(feature_registry),
        feature_registry,
    )


def _make_trend_df(direction: str = "up", n: int = 200) -> pl.DataFrame:
    """生成趋势数据。"""
    rows = []
    for i in range(n):
        if direction == "up":
            base = 100.0 + i * 0.2
        else:
            base = 100.0 - i * 0.2
        rows.append({
            "open": base,
            "high": base + 1.0,
            "low": base - 0.5,
            "close": base + 0.3,
            "volume": 1000.0 + i * 5,
        })
    return pl.DataFrame(rows)


def test_scan_basic(scanner) -> None:
    """基本扫描流程：规则 → 信号 → 交易。"""
    df = _make_trend_df("up", 200)
    rule = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}

    result = scanner.scan(df, rule, TradeConfig(max_holding_bars=10),
                          symbol="TEST", interval="4h")

    assert isinstance(result, ScanResult)
    assert result.symbol == "TEST"
    assert result.interval == "4h"
    assert result.signal_count > 0
    assert result.total_trades == result.signal_count  # long only
    assert result.long_trades == result.total_trades


def test_scan_empty_result(scanner) -> None:
    """不可能条件 → 0 信号。"""
    df = _make_trend_df("up", 50)
    rule = {"and": [{"feature": "rsi", "operator": ">", "value": 999}]}
    result = scanner.scan(df, rule)
    assert result.signal_count == 0
    assert result.total_trades == 0


def test_full_scan_with_stats(scanner) -> None:
    """full_scan 直接带统计。"""
    df = _make_trend_df("up", 200)
    rule = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}

    result = scanner.full_scan(df, rule, TradeConfig(max_holding_bars=20),
                               symbol="TEST", interval="1h")

    assert result.stats is not None
    assert result.stats.total_trades > 0
    assert 0 <= result.stats.win_rate <= 100

    # print report 不抛异常
    result.print_report()


def test_compute_stats_separately(scanner) -> None:
    """scan + compute_stats 两步走。"""
    df = _make_trend_df("up", 100)
    rule = {"and": [{"feature": "ema", "operator": ">", "value": -999}]}

    result = scanner.scan(df, rule, TradeConfig(max_holding_bars=5))
    assert result.stats is None

    result = scanner.compute_stats(result)
    assert result.stats is not None
    assert result.stats.total_trades > 0


def test_both_direction_scan(scanner) -> None:
    """双向扫描。"""
    df = _make_trend_df("up", 100)
    rule = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}
    config = TradeConfig(direction="both", max_holding_bars=5)

    result = scanner.scan(df, rule, config)
    # 每个信号产生 2 笔交易（多+空）
    assert result.total_trades == result.signal_count * 2


def test_feature_snapshots(scanner) -> None:
    """特征快照应有数据。"""
    df = _make_trend_df("up", 100)
    rule = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}

    result = scanner.scan(df, rule, TradeConfig(max_holding_bars=5))
    if result.signal_count > 0:
        assert result.feature_snapshots is not None
        assert len(result.feature_snapshots) == result.signal_count


def test_scan_and_save(scanner, tmp_path) -> None:
    """scan_and_save 存入数据库。"""
    db_path = tmp_path / "test_scan.db"

    df = _make_trend_df("up", 80)
    rule = {"and": [{"feature": "volume", "operator": ">", "value": 0.5}]}

    result = scanner.scan_and_save(
        df, rule, TradeConfig(max_holding_bars=5),
        symbol="BTCUSDT", interval="4h",
        db_path=str(db_path),
    )

    assert result.stats is not None
    assert db_path.exists()

    # 验证数据库中有数据
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    jobs = conn.execute("SELECT COUNT(*) FROM scan_job").fetchone()[0]
    trades_count = conn.execute("SELECT COUNT(*) FROM trade").fetchone()[0]
    assert jobs == 1
    assert trades_count == result.total_trades
    conn.close()
