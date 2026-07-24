"""
feature/consecutive_up.py - 连续上涨天数因子

分类:
    momentum

返回:
    当前连续上涨的 K 线数（从最近一次收阴算起）

所需数据列:
    close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算最近连续上涨的 K 线数。

    0 = 当前收阴
    1 = 当前收阳但昨天收阴
    2 = 连续 2 根阳线
    ...

    Args:
        df: K 线 DataFrame，必须包含 close 列

    Returns:
        连续上涨天数 Series（整数）
    """
    is_up = (df["close"] > df["close"].shift(1)).cast(pl.Int32)

    # 计算连续上涨：当 is_up=0 时归零，否则累加
    result = []
    count = 0
    for v in is_up.to_list():
        if v is None:
            count = 0
            result.append(0)
        elif v == 1:
            count += 1
            result.append(count)
        else:
            count = 0
            result.append(0)

    return pl.Series("consecutive_up", result, dtype=pl.Int32)
