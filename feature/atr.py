"""
feature/atr.py - 平均真实波幅因子

分类:
    volatility

参数:
    period: int = 14  ATR 计算周期

返回:
    原始 ATR 值（非百分比）

所需数据列:
    high, low, close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算 ATR（平均真实波幅）。

    值越大 = 波动越剧烈。

    Args:
        df: K 线 DataFrame，必须包含 high、low、close 列
        period: ATR 周期，默认 14

    Returns:
        ATR 值 Series（价格绝对值）
        前 period 个值为 null
    """
    period = int(params.get("period", 14))

    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pl.DataFrame({"a": tr1, "b": tr2, "c": tr3}).select(
        pl.max_horizontal(pl.all())
    ).to_series()

    return tr.rolling_mean(window_size=period, min_samples=period)
