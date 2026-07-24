"""
feature/close_from_high.py - 收盘价距最高价因子

分类:
    pattern

参数:
    无

返回:
    收盘价到最高价的距离占比（%）
    值越大 = 收盘离最高价越远 = 上方阻力

所需数据列:
    high, close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算收盘价到最高价的距离占比。

    1% 表示收盘价比最高价低 1%（接近最高价）。
    5% 表示收盘价比最高价低 5%（远离最高价，有上影线）。

    这个因子常用于判断：
    "收盘是否低于（插针）最高价 X%"

    Args:
        df: K 线 DataFrame，必须包含 high、close 列

    Returns:
        距离百分比 Series，[0, +∞)
    """
    return (df["high"] - df["close"]) / df["high"] * 100
