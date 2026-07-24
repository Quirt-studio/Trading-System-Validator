"""
feature/macd.py - MACD 因子

分类:
    momentum

参数:
    fast: int = 12    快线周期
    slow: int = 26    慢线周期
    signal: int = 9   信号线周期

返回三个子因子:
    macd_line: MACD 线 (快线 - 慢线)
    macd_signal: 信号线 (MACD 线的 EMA)
    macd_histogram: 柱状图 (MACD 线 - 信号线)

所需数据列:
    close
"""

import polars as pl


def calculate(df: pl.DataFrame, **params) -> pl.Series:
    """
    计算 MACD 柱状图（默认）。

    柱状图 > 0 = 多头，柱状图 < 0 = 空头。
    如需 MACD 线或信号线，使用 component 参数。

    Args:
        df: K 线 DataFrame，必须包含 close 列
        fast: 快线 EMA 周期，默认 12
        slow: 慢线 EMA 周期，默认 26
        signal: 信号线 EMA 周期，默认 9
        component: 返回组件
            - "histogram" (默认): MACD 柱状图
            - "line": MACD 线
            - "signal": 信号线

    Returns:
        MACD 组件值 Series
    """
    fast = int(params.get("fast", 12))
    slow = int(params.get("slow", 26))
    signal = int(params.get("signal", 9))
    component = params.get("component", "histogram")

    ema_fast = df["close"].ewm_mean(span=fast, min_samples=fast)
    ema_slow = df["close"].ewm_mean(span=slow, min_samples=slow)
    macd_line = ema_fast - ema_slow
    macd_signal = macd_line.ewm_mean(span=signal, min_samples=signal)

    if component == "line":
        return macd_line
    elif component == "signal":
        return macd_signal
    else:
        return macd_line - macd_signal
