"""
feature/ema.py - 指数移动平均偏离因子

分类:
    momentum

参数:
    period: int = 20  EMA 计算周期

所需数据列:
    close

示例:
    >>> import polars as pl
    >>> df = pl.DataFrame({"close": [100, 101, 102, 103, 104]})
    >>> result = calculate(df, period=3)
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算收盘价相对于 EMA 的偏离百分比。

    正值 = 价格高于 EMA（看涨）
    负值 = 价格低于 EMA（看跌）

    Args:
        df: K 线 DataFrame，必须包含 close 列
        period: EMA 周期，默认 20

    Returns:
        偏离百分比 Series，值域约 [-10%, +10%]
        前 period-1 个值为 null
    """
    period = int(params.get("period", 20))
    ema = df["close"].ewm_mean(span=period, min_samples=period)
    return (df["close"] - ema) / ema * 100
