"""
feature/volume.py - 成交量比率因子

分类:
    volume

参数:
    period: int = 20  成交量均线周期

返回:
    当前成交量相对于均量的比值

所需数据列:
    volume
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算当前成交量相对于移动平均成交量的比值。

    1.0 = 正常成交量
    > 1.5 = 放量
    < 0.5 = 缩量

    Args:
        df: K 线 DataFrame，必须包含 volume 列
        period: 均量周期，默认 20

    Returns:
        成交量比率 Series
        前 period-1 个值为 null
    """
    period = int(params.get("period", 20))
    avg_volume = df["volume"].rolling_mean(window_size=period, min_samples=period)
    return df["volume"] / avg_volume
