"""
core/trade_engine.py — 交易引擎

统一处理 Replay 和 Scanner 产生的交易模拟。
对每个入场信号，逐根扫描后续 K 线，判断 SL/TP/超时退出。

用法:
    from core.trade_engine import TradeEngine, TradeConfig
    from core.strategies import FixedSL, FixedRRTP, BollingerMidTP
    from core.feature_registry import FeatureRegistry

    registry = FeatureRegistry()
    engine = TradeEngine(registry)
    config = TradeConfig(
        direction="long",
        sl_strategy=FixedSL(pct=2.0),
        tp_strategy=FixedRRTP(rr=2.0),
    )
    trades = engine.execute(signals, df, config)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import polars as pl

from core.feature_registry import FeatureRegistry
from core.strategies.sl_strategies import StopLossStrategy, FixedSL
from core.strategies.tp_strategies import TakeProfitStrategy, FixedRRTP


# ── 配置 ──────────────────────────────────────────

@dataclass
class TradeConfig:
    """
    交易配置。

    策略模式：SL/TP 策略各自管理参数，新增策略无需修改 TradeConfig。

    Example:
        TradeConfig(
            direction="long",
            sl_strategy=ATRSL(period=14, multiplier=1.5),
            tp_strategy=BollingerMidTP(period=20),
        )
    """
    # 入场
    direction: str = "long"             # long / short / both
    entry_type: str = "close"           # open / close / high / low / custom
    entry_offset: float = 0.0           # 自定义入场偏移（%）

    # 止损策略（策略对象管理自己的参数）
    sl_strategy: StopLossStrategy = field(default_factory=lambda: FixedSL(pct=2.0))  # type: ignore[valid-type]

    # 止盈策略（策略对象管理自己的参数）
    tp_strategy: TakeProfitStrategy = field(default_factory=lambda: FixedRRTP(rr=2.0))  # type: ignore[valid-type]

    # 超时
    max_holding_bars: int = 50          # 最大持仓 K 线数（0 = 不限制）
    time_exit_type: str = "close"       # 超时退出价格类型

    def __post_init__(self):
        """验证配置合法性。"""
        valid_entry = {"open", "close", "high", "low", "custom"}
        valid_dir = {"long", "short", "both"}
        assert self.entry_type in valid_entry, f"无效 entry_type: {self.entry_type}"
        assert self.direction in valid_dir, f"无效 direction: {self.direction}"
        assert self.max_holding_bars >= 0, "max_holding_bars 必须 >= 0"


# ── 交易结果 ──────────────────────────────────────

@dataclass
class Trade:
    """标准化交易结果。"""
    entry_time: int             # 入场 K 线索引
    exit_time: int              # 出场 K 线索引
    entry_price: float
    exit_price: float
    direction: str              # "long" | "short"
    sl_price: float
    tp_price: float
    result: str                 # "tp" | "sl" | "timeout"
    r_multiple: float           # R 倍数
    holding_bars: int           # 持仓 K 线数
    feature_snapshot: dict = field(default_factory=dict)


# ── TradeEngine ───────────────────────────────────

class TradeEngine:
    """
    交易引擎：模拟单笔交易的入场、持仓、出场全流程。

    SL/TP 逻辑完全委托给策略对象，引擎只负责入场和逐根扫描。
    """

    def __init__(self, feature_registry: FeatureRegistry):
        self._registry = feature_registry

    # ── 公开 API ──

    def execute(
        self,
        signals: pl.Series,
        df: pl.DataFrame,
        config: TradeConfig | None = None,
    ) -> list[Trade]:
        """
        对每个信号位置，模拟执行交易直到退出。

        Args:
            signals: 布尔信号序列（True = 入场）
            df: 完整 K 线 DataFrame（含 OHLCV）
            config: 交易配置（默认 TradeConfig()）

        Returns:
            Trade 对象列表（按入场时间排序）
        """
        if config is None:
            config = TradeConfig()

        signal_indices = [
            i for i, v in enumerate(signals.to_list())
            if v is True
        ]

        trades: list[Trade] = []

        for idx in signal_indices:
            if config.direction in ("long", "both"):
                trade = self._simulate_long(idx, df, config)
                if trade:
                    trades.append(trade)

            if config.direction in ("short", "both"):
                trade = self._simulate_short(idx, df, config)
                if trade:
                    trades.append(trade)

        return trades

    def execute_single(
        self,
        signal_idx: int,
        df: pl.DataFrame,
        config: TradeConfig | None = None,
    ) -> Trade | None:
        """对单个信号位置模拟一笔交易（用于 Replay 模式）。"""
        if config is None:
            config = TradeConfig()

        if config.direction in ("long", "both"):
            return self._simulate_long(signal_idx, df, config)
        else:
            return self._simulate_short(signal_idx, df, config)

    # ── 入场价 ──────────────────────────────────

    def _get_entry_price(self, idx: int, df: pl.DataFrame, config: TradeConfig) -> float:
        row = df.row(idx, named=True)
        match config.entry_type:
            case "open":
                return float(row["open"])
            case "close":
                return float(row["close"])
            case "high":
                return float(row["high"])
            case "low":
                return float(row["low"])
            case "custom":
                return float(row["close"]) * (1.0 + config.entry_offset / 100.0)
            case _:
                raise ValueError(f"未知 entry_type: {config.entry_type}")

    # ── 止损价 ──────────────────────────────────

    def _get_sl_price(
        self, idx: int, df: pl.DataFrame, entry: float, config: TradeConfig, direction: str,
    ) -> float:
        """委托给止损策略计算。"""
        return config.sl_strategy.calculate(self._registry, df, idx, entry, direction)

    # ── 止盈价 ──────────────────────────────────

    def _get_tp_price(self, entry: float, sl: float, config: TradeConfig, direction: str) -> float:
        """委托给止盈策略计算（静态止盈）。动态止盈返回 entry 作为占位。"""
        return config.tp_strategy.get_target_price(entry, sl, direction)

    # ── 做多模拟 ────────────────────────────────

    def _simulate_long(
        self, idx: int, df: pl.DataFrame, config: TradeConfig,
    ) -> Trade | None:
        n = df.height
        entry = self._get_entry_price(idx, df, config)
        sl = self._get_sl_price(idx, df, entry, config, "long")

        tp_strategy = config.tp_strategy
        is_dynamic = tp_strategy.is_dynamic()
        dynamic_ctx = tp_strategy.precompute(df, self._registry) if is_dynamic else None
        tp = self._get_tp_price(entry, sl, config, "long")

        if sl >= entry:
            return None
        if not is_dynamic and tp <= entry:
            return None

        snapshot = self._take_snapshot(idx, df)

        max_hold = config.max_holding_bars
        if max_hold <= 0:
            max_hold = n - idx - 1
        end_idx = min(idx + max_hold, n - 1)

        tp_price_j = tp  # 初始化（timeout 或空循环时回退）
        for j in range(idx + 1, end_idx + 1):
            low_j = float(df["low"][j])
            high_j = float(df["high"][j])

            sl_hit = low_j <= sl

            if is_dynamic:
                tp_hit, tp_price_j = tp_strategy.check_bar(dynamic_ctx, j, df, "long")
            else:
                tp_hit = high_j >= tp
                tp_price_j = tp

            if sl_hit and tp_hit:
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=sl, direction="long",
                    sl_price=sl, tp_price=tp_price_j, result="sl",
                    r_multiple=-1.0, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )
            elif sl_hit:
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=sl, direction="long",
                    sl_price=sl, tp_price=tp_price_j, result="sl",
                    r_multiple=-1.0, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )
            elif tp_hit:
                exit_px = tp_price_j
                gain = exit_px - entry
                risk = entry - sl
                r = gain / risk if risk > 0 else 0.0
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=exit_px, direction="long",
                    sl_price=sl, tp_price=tp_price_j, result="tp",
                    r_multiple=r, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )

        # 超时
        exit_j = end_idx
        exit_price = float(df[config.time_exit_type][exit_j])
        risk = entry - sl
        r = (exit_price - entry) / risk if risk > 0 else 0.0
        tp_record = tp_price_j if is_dynamic else tp

        return Trade(
            entry_time=idx, exit_time=exit_j, entry_price=entry,
            exit_price=exit_price, direction="long",
            sl_price=sl, tp_price=tp_record, result="timeout",
            r_multiple=r, holding_bars=exit_j - idx,
            feature_snapshot=snapshot,
        )

    # ── 做空模拟 ────────────────────────────────

    def _simulate_short(
        self, idx: int, df: pl.DataFrame, config: TradeConfig,
    ) -> Trade | None:
        n = df.height
        entry = self._get_entry_price(idx, df, config)
        sl = self._get_sl_price(idx, df, entry, config, "short")

        tp_strategy = config.tp_strategy
        is_dynamic = tp_strategy.is_dynamic()
        dynamic_ctx = tp_strategy.precompute(df, self._registry) if is_dynamic else None
        tp = self._get_tp_price(entry, sl, config, "short")

        if sl <= entry:
            return None
        if not is_dynamic and tp >= entry:
            return None

        snapshot = self._take_snapshot(idx, df)

        max_hold = config.max_holding_bars
        if max_hold <= 0:
            max_hold = n - idx - 1
        end_idx = min(idx + max_hold, n - 1)

        tp_price_j = tp  # 初始化（timeout 或空循环时回退）
        for j in range(idx + 1, end_idx + 1):
            low_j = float(df["low"][j])
            high_j = float(df["high"][j])

            sl_hit = high_j >= sl

            if is_dynamic:
                tp_hit, tp_price_j = tp_strategy.check_bar(dynamic_ctx, j, df, "short")
            else:
                tp_hit = low_j <= tp
                tp_price_j = tp

            if sl_hit and tp_hit:
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=sl, direction="short",
                    sl_price=sl, tp_price=tp_price_j, result="sl",
                    r_multiple=-1.0, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )
            elif sl_hit:
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=sl, direction="short",
                    sl_price=sl, tp_price=tp_price_j, result="sl",
                    r_multiple=-1.0, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )
            elif tp_hit:
                exit_px = tp_price_j
                risk = sl - entry
                gain = entry - exit_px
                r = gain / risk if risk > 0 else 0.0
                return Trade(
                    entry_time=idx, exit_time=j, entry_price=entry,
                    exit_price=exit_px, direction="short",
                    sl_price=sl, tp_price=tp_price_j, result="tp",
                    r_multiple=r, holding_bars=j - idx,
                    feature_snapshot=snapshot,
                )

        # 超时
        exit_j = end_idx
        exit_price = float(df[config.time_exit_type][exit_j])
        risk = sl - entry
        r = (entry - exit_price) / risk if risk > 0 else 0.0
        tp_record = tp_price_j if is_dynamic else tp

        return Trade(
            entry_time=idx, exit_time=exit_j, entry_price=entry,
            exit_price=exit_price, direction="short",
            sl_price=sl, tp_price=tp_record, result="timeout",
            r_multiple=r, holding_bars=exit_j - idx,
            feature_snapshot=snapshot,
        )

    # ── 因子快照 ────────────────────────────────

    def _take_snapshot(self, idx: int, df: pl.DataFrame) -> dict[str, float | None]:
        snapshot: dict[str, float | None] = {}
        for name in self._registry.list_all():
            try:
                series = self._registry.calculate(name, df)
                val = series[idx]
                snapshot[name] = float(val) if val is not None else None
            except Exception:
                snapshot[name] = None
        return snapshot
