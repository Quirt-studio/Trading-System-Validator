"""
feature/bollinger.py - 布林带因子

分类:
    volatility

参数:
    period: int = 20     布林带周期
    std_dev: float = 2.0  标准差倍数

返回:
    布林带突破百分比
    正值 = 突破上轨（%），负值 = 跌破下轨（%），0 = 在带内
    值域约 [-5%, +5%]，超出域外代表极端行情

所需数据列:
    close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算布林带突破百分比。

    正值表示价格在上轨之上（潜在超买），
    负值表示价格在下轨之下（潜在超卖）。

    Args:
        df: K 线 DataFrame，必须包含 close 列
        period: 布林带周期，默认 20
        std_dev: 标准差倍数，默认 2.0

    Returns:
        突破百分比 Series
        值域约 [-5%, +5%]
        前 period-1 个值为 null
    """
    period = int(params.get("period", 20))
    std_dev = float(params.get("std_dev", 2.0))

    mid = pl.col("close").rolling_mean(window_size=period, min_samples=period)
    std = pl.col("close").rolling_std(window_size=period, min_samples=period)
    upper = mid + std_dev * std
    lower = mid - std_dev * std

    upper_pct = (pl.col("close") - upper) / upper * 100
    lower_pct = (pl.col("close") - lower) / lower * 100

    # 突破上轨 → 正值；跌破下轨 → 负值；区间内 → 0
    result = (
        pl.when(pl.col("close") > upper)
        .then(upper_pct)
        .otherwise(
            pl.when(pl.col("close") < lower)
            .then(lower_pct)
            .otherwise(pl.lit(0.0))
        )
    )

    return df.select(result.alias("result"))["result"]
