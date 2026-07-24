"""
feature/lower_shadow.py - 下影线比例因子

分类:
    pattern

参数:
    无

返回:
    下影线占高低振幅的百分比

所需数据列:
    high, low, close, open
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算下影线占 K 线总振幅的比例。

    下影线比例越高 = 下方支撑越强 / 空头受阻。

    Args:
        df: K 线 DataFrame，必须包含 open、high、low、close 列

    Returns:
        下影线比例 Series，[0, 100]
    """
    total_range = df["high"] - df["low"]
    lower_body = pl.DataFrame({"o": df["open"], "c": df["close"]}).select(
        pl.min_horizontal(pl.all())
    ).to_series()
    lower_shadow = lower_body - df["low"]
    return lower_shadow / total_range.replace(0, None) * 100
