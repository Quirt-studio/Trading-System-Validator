"""策略模块 — 止损/止盈策略的插件化实现。"""

from core.strategies.sl_strategies import (
    StopLossStrategy,
    FixedSL,
    ATRSL,
    SwingSL,
    BarExtremeSL,
    CustomSL,
)
from core.strategies.tp_strategies import (
    TakeProfitStrategy,
    FixedRRTP,
    FixedPctTP,
    TargetTP,
    CustomTP,
    BollingerMidTP,
)

__all__ = [
    "StopLossStrategy", "FixedSL", "ATRSL", "SwingSL", "BarExtremeSL", "CustomSL",
    "TakeProfitStrategy", "FixedRRTP", "FixedPctTP", "TargetTP", "CustomTP", "BollingerMidTP",
]
