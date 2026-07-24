"""
core/strategies/tp_strategies.py — 止盈策略

支持两类：
  - 静态止盈：入场时计算目标价，逐根检查是否触及
  - 动态止盈：每根 bar 重新计算止盈条件（如布林带中轨回归）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from core.feature_registry import FeatureRegistry


class TakeProfitStrategy:
    """止盈策略基类。"""

    def is_dynamic(self) -> bool:
        """是否为动态止盈（需要逐根 bar 重新计算）。"""
        return False

    def get_target_price(self, entry: float, sl: float, direction: str) -> float:
        """
        获取止盈目标价（静态止盈）。
        动态止盈返回 entry 作为占位。
        """
        return entry

    def precompute(self, df: pl.DataFrame, registry: FeatureRegistry) -> object | None:
        """
        预计算动态止盈所需的序列（如布林带中轨）。
        静态止盈返回 None。
        """
        return None

    def check_bar(
        self, precomputed: object, bar_idx: int, df: pl.DataFrame, direction: str,
    ) -> tuple[bool, float]:
        """
        逐根检查动态止盈条件。

        Returns:
            (是否触发止盈, 止盈价格)
        """
        return False, 0.0


# ════════════════════════════════════════════════════════════════════════════
# 静态止盈策略
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class FixedRRTP(TakeProfitStrategy):
    """固定 R:R 止盈。"""
    rr: float = 2.0

    def get_target_price(self, entry: float, sl: float, direction: str) -> float:
        risk = abs(entry - sl)
        if direction == "long":
            return entry + risk * self.rr
        else:
            return entry - risk * self.rr


@dataclass
class FixedPctTP(TakeProfitStrategy):
    """固定百分比止盈。"""
    pct: float = 2.0  # 如 2 表示入场价的 2%

    def get_target_price(self, entry: float, sl: float, direction: str) -> float:
        if direction == "long":
            return entry * (1.0 + self.pct / 100.0)
        else:
            return entry * (1.0 - self.pct / 100.0)


@dataclass
class TargetTP(TakeProfitStrategy):
    """目标价止盈。"""
    price: float = 0.0

    def get_target_price(self, entry: float, sl: float, direction: str) -> float:
        return self.price


@dataclass
class CustomTP(TakeProfitStrategy):
    """固定价格止盈（同 TargetTP，别名）。"""
    price: float = 0.0

    def get_target_price(self, entry: float, sl: float, direction: str) -> float:
        return self.price


# ════════════════════════════════════════════════════════════════════════════
# 动态止盈策略
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class BollingerMidTP(TakeProfitStrategy):
    """布林带中轨回归止盈。价格回到 SMA 中轨时止盈离场。"""
    period: int = 20
    std_dev: float = 2.0

    def is_dynamic(self) -> bool:
        return True

    def precompute(self, df: pl.DataFrame, registry: FeatureRegistry) -> object | None:
        """预计算布林带中轨（SMA）序列。"""
        return df["close"].rolling_mean(
            window_size=self.period, min_samples=self.period,
        )

    def check_bar(
        self, precomputed: object, bar_idx: int, df: pl.DataFrame, direction: str,
    ) -> tuple[bool, float]:
        """检查当前 bar 是否触及中轨。"""
        mid_raw = precomputed[bar_idx]
        if mid_raw is None:
            return False, 0.0
        mid = float(mid_raw)  # type: ignore[arg-type]
        if mid != mid:  # NaN check
            return False, 0.0

        if direction == "long":
            # 做多：价格回落到中轨 → 止盈
            low = float(df["low"][bar_idx])
            if low <= mid:
                return True, mid
        else:
            # 做空：价格回升到中轨 → 止盈
            high = float(df["high"][bar_idx])
            if high >= mid:
                return True, mid

        return False, 0.0
