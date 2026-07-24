"""
tests/conftest.py — 共享测试 fixtures
"""

from pathlib import Path

import polars as pl
import pytest

from core.feature_registry import FeatureRegistry
from core.data_hub import DataHub


@pytest.fixture(scope="session")
def sample_df() -> pl.DataFrame:
    """
    生成 200 行样本 K 线数据，模拟真实走势。

    包含:
    - 上升趋势（前 50 行）
    - 震荡区间（50-100 行）
    - 下降趋势（100-150 行）
    - 再次上升（150-200 行）
    """
    import numpy as np
    np.random.seed(42)

    n = 200
    close = np.zeros(n)
    close[0] = 100.0

    # 生成有趋势的价格
    for i in range(1, n):
        if i < 50:
            drift = 0.3  # 上升
        elif i < 100:
            drift = 0.0  # 震荡
        elif i < 150:
            drift = -0.3  # 下降
        else:
            drift = 0.2  # 恢复上升
        noise = np.random.randn() * 0.5
        close[i] = close[i - 1] + drift + noise
        close[i] = max(close[i], 1.0)  # 价格不能为负

    close = close.tolist()
    high = [c + abs(np.random.randn()) * 0.5 * c / 100 for c in close]
    low = [c - abs(np.random.randn()) * 0.5 * c / 100 for c in close]
    open_price = [
        low[i] + np.random.random() * (high[i] - low[i])
        for i in range(n)
    ]
    volume = [abs(np.random.randn()) * 1000 + 500 for _ in range(n)]

    # 确保 OHLC 逻辑
    for i in range(n):
        vals = [open_price[i], close[i], high[i], low[i]]
        high[i] = max(vals)
        low[i] = min(vals)

    return pl.DataFrame({
        "open_time": list(range(n)),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@pytest.fixture(scope="session")
def feature_registry() -> FeatureRegistry:
    """因子注册表实例。"""
    return FeatureRegistry()


@pytest.fixture(scope="function")
def data_hub(tmp_path) -> DataHub:
    """数据中心实例（每个测试独立临时目录）。"""
    data_dir = tmp_path / "factorlab_data"
    data_dir.mkdir()
    return DataHub(data_dir=data_dir)
