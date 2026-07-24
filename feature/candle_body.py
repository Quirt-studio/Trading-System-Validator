"""
feature/candle_body.py - K 线实体比例因子

分类:
    pattern

参数:
    无

返回:
    K 线实体占高低振幅的百分比
    正值 = 阳线，负值 = 阴线

所需数据列:
    open, high, low, close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算 K 线实体占整个振幅的比例。

    实体比例越大 = 趋势越坚决
    实体比例越小 = 多空分歧大（十字星/纺锤线）

    Args:
        df: K 线 DataFrame，必须包含 open、high、low、close 列

    Returns:
        实体比例 Series，[-100, 100]
        正值 = 阳线实体占比，负值 = 阴线实体占比
    """
    body = df["close"] - df["open"]
    total_range = df["high"] - df["low"]
    ratio = body / total_range.replace(0, None) * 100
    return ratio
