"""
core/strategies/sl_strategies.py — 止损策略

每个策略类管理自己的参数，TradeEngine 只需调用 calculate()。

新增止损策略 = 新增一个类文件，无需修改 TradeEngine。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from core.feature_registry import FeatureRegistry


class StopLossStrategy:
    """止损策略基类。"""

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        """
        计算止损价格。

        Args:
            registry: 因子注册表（ATR 等需要）
            df: K 线 DataFrame
            idx: 入场 K 线索引
            entry: 入场价
            direction: "long" | "short"

        Returns:
            止损价格
        """
        raise NotImplementedError


# ════════════════════════════════════════════════════════════════════════════
# 具体策略
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class FixedSL(StopLossStrategy):
    """固定百分比止损。"""
    pct: float = 2.0  # 百分比，如 2 表示 2%

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        if direction == "long":
            return entry * (1.0 - self.pct / 100.0)
        else:
            return entry * (1.0 + self.pct / 100.0)


@dataclass
class ATRSL(StopLossStrategy):
    """ATR 倍数止损。"""
    period: int = 14
    multiplier: float = 1.0

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        atr_series = registry.calculate("atr", df, period=self.period)
        atr_val = atr_series[idx]
        if atr_val is None:
            atr_val = entry * 0.01
        if direction == "long":
            return entry - float(atr_val) * self.multiplier
        else:
            return entry + float(atr_val) * self.multiplier


@dataclass
class SwingSL(StopLossStrategy):
    """前 N 根摆动点止损。"""
    lookback: int = 10  # 回溯 K 线数

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        start = max(0, idx - self.lookback)
        if direction == "long":
            return float(df["low"][start:idx + 1].min())  # type: ignore[union-attr,return-value]
        else:
            return float(df["high"][start:idx + 1].max())  # type: ignore[union-attr,return-value]


@dataclass
class BarExtremeSL(StopLossStrategy):
    """入场 K 线极值百分比止损。"""
    pct: float = 2.0

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        if direction == "long":
            bar_high = float(df["high"][idx])
            return bar_high * (1.0 - self.pct / 100.0)
        else:
            bar_low = float(df["low"][idx])
            return bar_low * (1.0 + self.pct / 100.0)


@dataclass
class CustomSL(StopLossStrategy):
    """固定价格止损。"""
    price: float = 0.0

    def calculate(
        self, registry: FeatureRegistry, df: pl.DataFrame,
        idx: int, entry: float, direction: str,
    ) -> float:
        return self.price
