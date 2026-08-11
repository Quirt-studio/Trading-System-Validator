"""
feature/rsi.py - 相对强弱指数因子

分类:
    momentum

参数:
    period: int = 14  RSI 计算周期

所需数据列:
    close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算 RSI 指标值。

    RSI > 70 = 超买，RSI < 30 = 超卖。

    Args:
        df: K 线 DataFrame，必须包含 close 列
        period: RSI 周期，默认 14

    Returns:
        RSI 值 Series，范围 [0, 100]
        前 period 个值为 null
    """
    period = int(params.get("period", 14))

    delta = pl.col("close").diff()
    gain = delta.clip(lower_bound=0)
    loss = (-delta).clip(lower_bound=0)

    avg_gain = gain.rolling_mean(window_size=period, min_samples=period)
    avg_loss = loss.rolling_mean(window_size=period, min_samples=period)

    # RSI = 100 - 100/(1+RS), RS = avg_gain / avg_loss
    # avg_loss == 0 时的边界处理:
    #   avg_gain > 0 (纯上涨): RS→∞, RSI→100
    #   avg_gain == 0 (横盘):   无方向, RSI=50
    rsi_expr = (
        pl.when(avg_loss == 0)
        .then(
            pl.when(avg_gain == 0)
            .then(pl.lit(50.0))
            .otherwise(pl.lit(100.0))
        )
        .otherwise(100.0 - (100.0 / (1.0 + (avg_gain / avg_loss.replace(0, None)))))
    )

    return df.select(rsi_expr.alias("rsi"))["rsi"]
