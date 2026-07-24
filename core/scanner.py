"""
core/scanner.py — 策略扫描器

将 Rule Engine + Trade Engine 串联：
  规则 JSON → 信号扫描 → 交易模拟 → 结果汇总

用法:
    from core.scanner import Scanner
    from core.rule_engine import RuleEngine
    from core.trade_engine import TradeEngine, TradeConfig
    from core.feature_registry import FeatureRegistry

    registry = FeatureRegistry()
    scanner = Scanner(RuleEngine(registry), TradeEngine(registry), registry)

    result = scanner.scan(df, rule_json, TradeConfig())
    print(f"信号: {result.signal_count}, 交易: {result.total_trades}")
    print(f"胜率: {result.stats.win_rate:.1f}%")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from core.rule_engine import RuleEngine
    from core.trade_engine import Trade, TradeConfig, TradeEngine
    from core.feature_registry import FeatureRegistry
    from core.statistics import TradeStats


@dataclass
class ScanResult:
    """一次扫描的完整结果。

    包含：规则、标的、信号数、交易列表、统计指标。
    """
    rule_json: dict
    symbol: str
    interval: str
    date_range: tuple[str, str]      # (start_time, end_time)
    signal_count: int                 # 匹配信号总数
    trades: list[Trade]               # 全部交易
    stats: TradeStats | None = None   # 统计指标（需调用 compute_stats）
    feature_snapshots: pl.DataFrame | None = None

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def long_trades(self) -> int:
        return sum(1 for t in self.trades if t.direction == "long")

    @property
    def short_trades(self) -> int:
        return sum(1 for t in self.trades if t.direction == "short")

    def summary(self) -> dict:
        """返回可序列化的结果摘要。"""
        d: dict = {
            "symbol": self.symbol,
            "interval": self.interval,
            "date_range": self.date_range,
            "rule": json.dumps(self.rule_json, ensure_ascii=False),
            "signal_count": self.signal_count,
            "total_trades": self.total_trades,
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
        }
        if self.stats:
            d.update({
                "win_rate": round(self.stats.win_rate, 2),
                "profit_factor": round(self.stats.profit_factor, 2),
                "expectancy": round(self.stats.expectancy, 3),
                "max_drawdown_pct": round(self.stats.max_drawdown_pct, 2),
                "avg_holding_bars": round(self.stats.avg_holding_bars, 1),
                "max_consecutive_loss": self.stats.max_consecutive_loss,
            })
        return d

    def print_report(self) -> None:
        """打印完整报告到控制台。"""
        s = self.summary()
        print("=" * 60)
        print("  FactorLab 扫描报告")
        print("=" * 60)
        print(f"  标的/周期:  {s['symbol']} {s['interval']}")
        print(f"  时间范围:  {s['date_range'][0]} ~ {s['date_range'][1]}")
        print(f"  信号数量:  {s['signal_count']}")
        print(f"  交易总数:  {s['total_trades']} (多 {s.get('long_trades', 0)} / 空 {s.get('short_trades', 0)})")
        if self.stats:
            print("-" * 60)
            print(f"  胜率:        {self.stats.win_rate:.1f}%")
            print(f"  Profit Factor: {self.stats.profit_factor:.2f}")
            print(f"  Expectancy:  {self.stats.expectancy:.3f}R")
            print(f"  最大回撤:    {self.stats.max_drawdown_pct:.1f}%")
            print(f"  最大连亏:    {self.stats.max_consecutive_loss} 笔")
            print(f"  平均持仓:    {self.stats.avg_holding_bars:.1f} 根K线")
        print("=" * 60)


class Scanner:
    """策略扫描器：规则 → 信号 → 交易 → 结果。"""

    def __init__(
        self,
        rule_engine: RuleEngine,
        trade_engine: TradeEngine,
        feature_registry: FeatureRegistry,
    ):
        self._rule_engine = rule_engine
        self._trade_engine = trade_engine
        self._registry = feature_registry

    def scan(
        self,
        df: pl.DataFrame,
        rule_json: dict,
        trade_config: TradeConfig | None = None,
        *,
        symbol: str = "",
        interval: str = "",
    ) -> ScanResult:
        """
        执行完整扫描流程。

        1. Rule Engine 匹配信号
        2. Trade Engine 模拟交易
        3. 收集特征快照
        4. 返回 ScanResult

        Args:
            df: K 线 DataFrame
            rule_json: 规则字典
            trade_config: 交易配置（默认 TradeConfig()）
            symbol: 标的名称（用于报告）
            interval: K 线周期（用于报告）

        Returns:
            ScanResult 对象
        """
        from core.trade_engine import TradeConfig

        if trade_config is None:
            trade_config = TradeConfig()

        # Step 1: 执行规则 → 获取信号
        signals = self._rule_engine.execute(rule_json, df)
        signal_count = signals.sum()

        # Step 2: 对每个信号模拟交易
        trades = self._trade_engine.execute(signals, df, trade_config)

        # Step 3: 收集特征快照（所有信号位置的因子值）
        snapshots = self._collect_snapshots(signals, df)

        # Step 4: 提取时间范围
        date_range = self._get_date_range(df)

        return ScanResult(
            rule_json=rule_json,
            symbol=symbol,
            interval=interval,
            date_range=date_range,
            signal_count=signal_count,
            trades=trades,
            feature_snapshots=snapshots,
        )

    def compute_stats(self, result: ScanResult) -> ScanResult:
        """
        为 ScanResult 附加统计指标。

        Args:
            result: 扫描结果

        Returns:
            同个 ScanResult（已附加 stats 字段）
        """
        from core.statistics import Statistics
        result.stats = Statistics().compute(result.trades)
        return result

    def full_scan(
        self,
        df: pl.DataFrame,
        rule_json: dict,
        trade_config: TradeConfig | None = None,
        *,
        symbol: str = "",
        interval: str = "",
    ) -> ScanResult:
        """
        scan + compute_stats 一步完成。

        Args:
            df: K 线 DataFrame
            rule_json: 规则字典
            trade_config: 交易配置
            symbol: 标的名称
            interval: K 线周期

        Returns:
            带统计指标的 ScanResult
        """
        result = self.scan(df, rule_json, trade_config, symbol=symbol, interval=interval)
        return self.compute_stats(result)

    def _collect_signals(self, signals: pl.Series) -> list[int]:
        """收集信号索引列表。"""
        return [i for i, v in enumerate(signals.to_list()) if v is True]

    def _collect_snapshots(self, signals: pl.Series, df: pl.DataFrame) -> pl.DataFrame | None:
        """收集所有信号位置的因子快照为 DataFrame。"""
        indices = self._collect_signals(signals)
        if not indices:
            return None

        rows: list[dict] = []
        for idx in indices:
            row: dict = {"signal_index": idx}
            for name in self._registry.list_all():
                try:
                    series = self._registry.calculate(name, df)
                    val = series[idx]
                    row[name] = float(val) if val is not None else None
                except Exception:
                    row[name] = None
            rows.append(row)

        if not rows:
            return None
        return pl.DataFrame(rows)

    def _get_date_range(self, df: pl.DataFrame) -> tuple[str, str]:
        """从 DataFrame 提取时间范围字符串。"""
        if "open_time" not in df.columns:
            return ("N/A", "N/A")

        col = df["open_time"]
        if col.dtype == pl.Datetime:
            start = str(col.min())
            end = str(col.max())
            return (start, end)

        return ("N/A", "N/A")

    def scan_and_save(
        self,
        df: pl.DataFrame,
        rule_json: dict,
        trade_config: TradeConfig | None = None,
        *,
        symbol: str = "",
        interval: str = "",
        db_path: str = "data/factorlab.db",
    ) -> ScanResult:
        """
        执行扫描并将结果存入 SQLite 数据库。

        Args:
            df: K 线 DataFrame
            rule_json: 规则字典
            trade_config: 交易配置
            symbol: 标的名称
            interval: K 线周期
            db_path: 数据库路径

        Returns:
            带统计指标的 ScanResult
        """
        from core.db import get_connection

        result = self.full_scan(df, rule_json, trade_config, symbol=symbol, interval=interval)

        conn = get_connection(db_path)

        # 保存 scan_job
        cur = conn.execute(
            """INSERT INTO scan_job (rule_json, symbol, interval, start_time, end_time)
               VALUES (?, ?, ?, ?, ?)""",
            (
                json.dumps(rule_json),
                symbol,
                interval,
                result.date_range[0],
                result.date_range[1],
            ),
        )
        job_id = cur.lastrowid

        # 保存 trades
        for t in result.trades:
            cur = conn.execute(
                """INSERT INTO trade
                   (scan_job_id, direction, entry_time, entry_price, exit_time,
                    exit_price, sl_price, tp_price, result, r_multiple, holding_bars)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id, t.direction, str(t.entry_time), t.entry_price,
                    str(t.exit_time), t.exit_price, t.sl_price, t.tp_price,
                    t.result, t.r_multiple, t.holding_bars,
                ),
            )
            trade_id = cur.lastrowid

            # 保存 feature snapshots
            for fname, fval in t.feature_snapshot.items():
                if fval is not None:
                    conn.execute(
                        """INSERT OR IGNORE INTO trade_feature (trade_id, feature_name, value)
                           VALUES (?, ?, ?)""",
                        (trade_id, fname, fval),
                    )

        conn.commit()
        conn.close()

        return result
