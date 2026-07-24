"""
core/statistics.py — 统计分析

自动计算所有关键交易统计指标。

用法:
    from core.statistics import Statistics
    stats = Statistics().compute(trades)
    print(f"胜率: {stats.win_rate:.1f}%")
    print(f"Profit Factor: {stats.profit_factor:.2f}")
    print(f"Expectancy: {stats.expectancy:.3f}R")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from core.trade_engine import Trade


@dataclass
class TradeStats:
    """交易统计指标。"""

    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0              # 胜率 %

    # 收益指标
    avg_win_r: float = 0.0             # 平均盈利 R
    avg_loss_r: float = 0.0            # 平均亏损 R
    avg_rr: float = 0.0                # 平均盈亏比
    avg_r_multiple: float = 0.0        # 平均 R 倍数

    profit_factor: float = 0.0         # 盈利因子 (总盈利/总亏损)
    expectancy: float = 0.0            # 期望值 R
    total_r: float = 0.0               # 总 R 倍数

    # 风险指标
    max_drawdown_pct: float = 0.0      # 最大回撤 %
    max_consecutive_loss: int = 0      # 最大连续亏损笔数
    max_consecutive_win: int = 0       # 最大连续盈利笔数

    # 持仓指标
    avg_holding_bars: float = 0.0      # 平均持仓 K 线数
    avg_holding_bars_win: float = 0.0  # 盈利单平均持仓
    avg_holding_bars_loss: float = 0.0 # 亏损单平均持仓

    # 曲线数据
    equity_curve: list[float] = field(default_factory=list)   # 权益曲线
    drawdown_curve: list[float] = field(default_factory=list)  # 回撤曲线

    def to_dict(self) -> dict:
        """转为可序列化字典。"""
        return {
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_rate, 2),
            "avg_win_r": round(self.avg_win_r, 3),
            "avg_loss_r": round(self.avg_loss_r, 3),
            "avg_rr": round(self.avg_rr, 2),
            "avg_r_multiple": round(self.avg_r_multiple, 3),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 3),
            "total_r": round(self.total_r, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "max_consecutive_loss": self.max_consecutive_loss,
            "max_consecutive_win": self.max_consecutive_win,
            "avg_holding_bars": round(self.avg_holding_bars, 1),
        }


class Statistics:
    """统计分析器：从 Trade 列表生成统计指标。"""

    def compute(self, trades: list[Trade]) -> TradeStats:
        """
        计算所有统计指标。

        Args:
            trades: Trade 对象列表

        Returns:
            TradeStats 对象
        """
        if not trades:
            return TradeStats()

        n = len(trades)

        wins = [t for t in trades if t.r_multiple > 0]
        losses = [t for t in trades if t.r_multiple <= 0]

        stats = TradeStats()
        stats.total_trades = n
        stats.win_count = len(wins)
        stats.loss_count = len(losses)
        stats.win_rate = len(wins) / n * 100 if n > 0 else 0.0

        # R 倍数统计
        r_values = [t.r_multiple for t in trades]
        win_r = [t.r_multiple for t in wins]
        loss_r = [abs(t.r_multiple) for t in losses]

        stats.avg_win_r = sum(win_r) / len(win_r) if win_r else 0.0
        stats.avg_loss_r = sum(loss_r) / len(loss_r) if loss_r else 0.0
        stats.avg_rr = stats.avg_win_r / stats.avg_loss_r if stats.avg_loss_r > 0 else float("inf")
        stats.avg_r_multiple = sum(r_values) / n
        stats.total_r = sum(r_values)

        # Profit Factor
        total_gain = sum(t.r_multiple for t in wins)
        total_loss = abs(sum(t.r_multiple for t in losses))
        stats.profit_factor = total_gain / total_loss if total_loss > 0 else float("inf")

        # Expectancy
        stats.expectancy = stats.avg_r_multiple

        # 持仓统计
        stats.avg_holding_bars = sum(t.holding_bars for t in trades) / n
        stats.avg_holding_bars_win = (
            sum(t.holding_bars for t in wins) / len(wins) if wins else 0.0
        )
        stats.avg_holding_bars_loss = (
            sum(t.holding_bars for t in losses) / len(losses) if losses else 0.0
        )

        # 最大连续
        stats.max_consecutive_loss = self._max_consecutive(trades, lambda t: t.r_multiple <= 0)
        stats.max_consecutive_win = self._max_consecutive(trades, lambda t: t.r_multiple > 0)

        # 权益曲线 & 回撤
        stats.equity_curve = self._compute_equity_curve(trades)
        stats.drawdown_curve = self._compute_drawdown_curve(stats.equity_curve)
        stats.max_drawdown_pct = self._max_drawdown(stats.equity_curve)

        return stats

    def filter(
        self,
        trades: list[Trade],
        condition: dict,  # {"feature": "atr", "operator": "<", "value": 2.0}
    ) -> list[Trade]:
        """
        按入场时因子快照值筛选 Trade。

        Args:
            trades: 全部交易列表
            condition: 筛选条件 {"feature": "...", "operator": "...", "value": ...}

        Returns:
            筛选后的 Trade 列表
        """
        feature = condition["feature"]
        operator = condition.get("operator", ">")
        value = condition.get("value", 0)

        result = []
        for t in trades:
            if feature not in t.feature_snapshot:
                continue
            fv = t.feature_snapshot[feature]
            if fv is None:
                continue

            match operator:
                case ">":
                    if fv > value:
                        result.append(t)
                case "<":
                    if fv < value:
                        result.append(t)
                case ">=":
                    if fv >= value:
                        result.append(t)
                case "<=":
                    if fv <= value:
                        result.append(t)
                case "==":
                    if fv == value:
                        result.append(t)
                case "!=":
                    if fv != value:
                        result.append(t)
                case "between":
                    if isinstance(value, list) and len(value) == 2:
                        if value[0] <= fv <= value[1]:
                            result.append(t)
                case "cross_above" | "cross_below":
                    # cross_above/cross_below 在 signal 层面使用，filter 对静态快照不适用
                    # 跳过（不筛选）
                    result.append(t)
                case _:
                    result.append(t)

        return result

    def recompute(self, trades: list[Trade]) -> TradeStats:
        """对筛选后的 Trade 列表重新统计。"""
        return self.compute(trades)

    # ── 内部计算 ──────────────────────────────

    @staticmethod
    def _max_consecutive(trades: list[Trade], condition: Callable[[Trade], bool]) -> int:
        """计算满足条件的最大连续出现次数。"""
        max_count = 0
        current = 0
        for t in trades:
            if condition(t):
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count

    @staticmethod
    def _compute_equity_curve(trades: list[Trade]) -> list[float]:
        """计算以 R 为单位的权益曲线。"""
        curve = [0.0]
        for t in trades:
            curve.append(curve[-1] + t.r_multiple)
        return curve

    @staticmethod
    def _compute_drawdown_curve(equity: list[float]) -> list[float]:
        """计算回撤曲线。"""
        dd = [0.0]
        peak = equity[0]
        for v in equity[1:]:
            if v > peak:
                peak = v
            dd.append(peak - v)  # 绝对回撤
        return dd

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        """计算最大回撤百分比（相对于峰值）。"""
        peak = equity[0]
        max_dd = 0.0
        for v in equity[1:]:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak != 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd
