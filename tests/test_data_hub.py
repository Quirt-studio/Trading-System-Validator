"""
tests/test_data_hub.py — 数据中心测试
"""

import polars as pl
import pytest


def test_import_csv_basic(data_hub, tmp_path) -> None:
    """基本 CSV 导入测试。"""
    csv_path = tmp_path / "test.csv"
    df = pl.DataFrame({
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [101.0, 102.0, 103.0, 104.0, 105.0],
        "low": [99.0, 100.0, 101.0, 102.0, 103.0],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
    })
    df.write_csv(csv_path)

    result = data_hub.import_csv(csv_path, "TEST", "1d")
    assert result.height == 5
    assert all(c in result.columns for c in ["open", "high", "low", "close", "volume"])


def test_load_after_import(data_hub, tmp_path) -> None:
    """导入后能正常加载。"""
    csv_path = tmp_path / "test2.csv"
    df = pl.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "volume": [1000.0, 1100.0],
    })
    df.write_csv(csv_path)

    data_hub.import_csv(csv_path, "LOAD", "1h")
    loaded = data_hub.load("LOAD", "1h")
    assert loaded.height == 2


def test_load_nonexistent(data_hub) -> None:
    """加载不存在的数据应抛出异常。"""
    with pytest.raises(FileNotFoundError):
        data_hub.load("NOPE", "1d")


def test_list_datasets(data_hub, tmp_path) -> None:
    """列表功能测试。"""
    csv_path = tmp_path / "test3.csv"
    df = pl.DataFrame({
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000.0],
    })
    df.write_csv(csv_path)
    data_hub.import_csv(csv_path, "LIST", "4h")

    datasets = data_hub.list_datasets()
    assert len(datasets) == 1
    assert datasets[0]["symbol"] == "LIST"
    assert datasets[0]["interval"] == "4h"
    assert datasets[0]["rows"] == 1


def test_has_data(data_hub, tmp_path) -> None:
    """数据存在性检查。"""
    assert not data_hub.has_data("NOPE", "1d")

    csv_path = tmp_path / "test4.csv"
    df = pl.DataFrame({
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000.0],
    })
    df.write_csv(csv_path)
    data_hub.import_csv(csv_path, "EXISTS", "1d")
    assert data_hub.has_data("EXISTS", "1d")


def test_delete(data_hub, tmp_path) -> None:
    """删除测试。"""
    csv_path = tmp_path / "test5.csv"
    df = pl.DataFrame({
        "open": [100.0], "high": [101.0], "low": [99.0],
        "close": [100.5], "volume": [1000.0],
    })
    df.write_csv(csv_path)
    data_hub.import_csv(csv_path, "DEL", "1d")
    assert data_hub.has_data("DEL", "1d")

    data_hub.delete("DEL", "1d")
    assert not data_hub.has_data("DEL", "1d")


def test_import_csv_missing_required_columns(data_hub, tmp_path) -> None:
    """缺少必需列时抛出异常。"""
    csv_path = tmp_path / "bad.csv"
    df = pl.DataFrame({"x": [1, 2, 3]})
    df.write_csv(csv_path)

    with pytest.raises(ValueError):
        data_hub.import_csv(csv_path, "BAD", "1d")


def test_import_csv_column_aliases(data_hub, tmp_path) -> None:
    """测试 TradingView 格式列名。"""
    csv_path = tmp_path / "tv.csv"
    df = pl.DataFrame({
        "Open": [100.0, 101.0],
        "High": [101.0, 102.0],
        "Low": [99.0, 100.0],
        "Close": [100.5, 101.5],
        "Volume": [1000.0, 1100.0],
    })
    df.write_csv(csv_path)

    result = data_hub.import_csv(csv_path, "TV", "1d")
    assert "open" in result.columns
    assert result.height == 2
