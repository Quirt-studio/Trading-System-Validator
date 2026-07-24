"""
feature/upper_shadow.py - 上影线比例因子

分类:
    pattern

参数:
    无

返回:
    上影线占高低振幅的百分比

所需数据列:
    high, low, close, open
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算上影线占 K 线总振幅的比例。

    上影线比例越高 = 上方压力越大 / 多头受阻。

    Args:
        df: K 线 DataFrame，必须包含 open、high、low、close 列

    Returns:
        上影线比例 Series，[0, 100]
    """
    total_range = df["high"] - df["low"]
    upper_body = pl.DataFrame({"o": df["open"], "c": df["close"]}).select(
        pl.max_horizontal(pl.all())
    ).to_series()
    upper_shadow = df["high"] - upper_body
    return upper_shadow / total_range.replace(0, None) * 100
