"""
feature/volatility.py - 历史波动率因子

分类:
    volatility

参数:
    period: int = 20  计算周期

返回:
    年化波动率百分比

所需数据列:
    close
"""

import numpy as np
import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算历史波动率（年化）。

    波动率越高 = 价格变动越剧烈。

    Args:
        df: K 线 DataFrame，必须包含 close 列
        period: 波动率计算周期，默认 20

    Returns:
        年化波动率 Series，单位 %
        前 period 个值为 null
    """
    period = int(params.get("period", 20))

    # 对数收益率
    log_return = (df["close"] / df["close"].shift(1)).log()

    # 滚动标准差（须在 period+1 内计算，用 ddof=1）
    # Polars rolling_std 默认 ddof=1
    rolling_std = log_return.rolling_std(window_size=period, min_samples=period)

    # 年化 (假设 365 天，实际天数取决于 K 线周期)
    return rolling_std * np.sqrt(365) * 100
