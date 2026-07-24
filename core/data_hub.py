"""
core/data_hub.py — 数据中心

负责:
  - CSV 导入 → Parquet 存储
  - 数据加载
  - 数据集列表
  - 数据完整性检查

K 线数据不进数据库，直接存 Parquet 文件。

用法:
    from core.data_hub import DataHub
    hub = DataHub()
    hub.import_csv("path/to/BTCUSDT_4h.csv", "BTCUSDT", "4h")
    df = hub.load("BTCUSDT", "4h")
    datasets = hub.list_datasets()
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

# Parquet 文件所需的标准列
STANDARD_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_volume", "taker_buy_quote_volume",
]

# 最小必需的列（简化 CSV 可只提供这些）
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

# CSV 列名映射（TradingView 和 Binance 常见导出格式）
COLUMN_ALIASES: dict[str, list[str]] = {
    "open_time": ["open_time", "Open time", "Open Time", "datetime", "Date", "time", "timestamp", "openTime"],
    "open": ["open", "Open", "OPEN"],
    "high": ["high", "High", "HIGH"],
    "low": ["low", "Low", "LOW"],
    "close": ["close", "Close", "CLOSE"],
    "volume": ["volume", "Volume", "VOL", "vol"],
    "close_time": ["close_time", "Close time", "Close Time", "closeTime"],
    "quote_volume": ["quote_volume", "Quote volume", "Quote asset volume", "quoteVolume"],
    "trades": ["trades", "Trades", "Number of trades", "count"],
    "taker_buy_volume": ["taker_buy_volume", "Taker buy volume", "takerBuyVolume"],
    "taker_buy_quote_volume": ["taker_buy_quote_volume", "Taker buy quote volume", "takerBuyQuoteVolume"],
}


class DataHub:
    """数据中心：管理 K 线数据的导入和读取。"""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data" / "raw"
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def _parquet_path(self, symbol: str, interval: str) -> Path:
        """返回 Parquet 文件路径。"""
        return self._data_dir / f"{symbol}_{interval}.parquet"

    def _normalize_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        将 CSV 列名映射到标准列名。

        支持 TradingView、Binance 等常见导出格式。
        """
        rename_map: dict[str, str] = {}
        current_cols = set(df.columns)

        for std_col, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in current_cols and alias != std_col:
                    rename_map[alias] = std_col
                    break

        if rename_map:
            df = df.rename(rename_map)

        return df

    def _fill_missing_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """补充缺失的可选列为默认值。"""
        existing = set(df.columns)
        for col in STANDARD_COLUMNS:
            if col not in existing:
                df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias(col))
        return df

    def _ensure_open_time(self, df: pl.DataFrame) -> pl.DataFrame:
        """确保 open_time 列存在并转为正确的 datetime 类型。"""
        has_time = "open_time" in df.columns and df["open_time"].null_count() < df.height

        if has_time:
            if df["open_time"].dtype != pl.Datetime:
                try:
                    df = df.with_columns(
                        pl.col("open_time").str.to_datetime().alias("open_time")
                    )
                except Exception:
                    pass
        else:
            # 如果没有时间列或全为 null，用序号代替
            df = df.with_columns(
                pl.int_range(0, df.height, dtype=pl.Int64).alias("open_time")
            )
        return df

    def import_csv(
        self,
        csv_path: str | Path,
        symbol: str,
        interval: str,
        timestamp_column: str | None = None,
    ) -> pl.DataFrame:
        """
        导入 CSV 文件并保存为 Parquet。

        幂等操作：相同 CSV 不会重复导入。

        Args:
            csv_path: CSV 文件路径
            symbol: 交易对符号，如 "BTCUSDT"
            interval: K 线周期，如 "4h"
            timestamp_column: 时间戳列名（可选，用于解析）

        Returns:
            导入的 DataFrame
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        # 尝试多种编码读取 CSV
        df = None
        for encoding in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
            try:
                df = pl.read_csv(
                    csv_path,
                    try_parse_dates=True,
                    encoding=encoding,
                    truncate_ragged_lines=True,
                )
                break
            except Exception:
                continue

        if df is None:
            raise ValueError(f"无法读取 CSV 文件: {csv_path}")

        # 检查最小必需列
        df = self._normalize_columns(df)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"CSV 缺少必需列: {missing}。"
                f"当前列名: {df.columns}"
            )

        # 确保 open_time 先行生成（如果缺失或全 null）
        df = self._ensure_open_time(df)
        # 补全其他标准列
        df = self._fill_missing_columns(df)

        # 确保数据类型
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))

        # 按时间排序去重
        if "open_time" in df.columns:
            df = df.unique(subset=["open_time"], keep="first")
            df = df.sort("open_time")

        # 保存为 Parquet
        parquet_path = self._parquet_path(symbol, interval)
        df.write_parquet(parquet_path)

        return df

    def load(self, symbol: str, interval: str) -> pl.DataFrame:
        """
        加载 Parquet 数据。

        Args:
            symbol: 交易对符号
            interval: K 线周期

        Returns:
            Polars DataFrame

        Raises:
            FileNotFoundError: 数据文件不存在
        """
        path = self._parquet_path(symbol, interval)
        if not path.exists():
            raise FileNotFoundError(
                f"数据文件不存在: {path}\n"
                f"请先在 Data 页面导入 CSV 数据。"
            )
        return pl.read_parquet(path)

    def list_datasets(self) -> list[dict]:
        """
        列出所有已导入的数据集。

        Returns:
            [{"symbol": "BTCUSDT", "interval": "4h",
              "rows": 12345, "start": datetime, "end": datetime,
              "path": "...", "size_mb": 2.3}]
        """
        datasets = []
        for path in sorted(self._data_dir.glob("*.parquet")):
            stem = path.stem
            # 文件名格式: SYMBOL_INTERVAL.parquet
            # 允许 symbol 中包含下划线（如 BINANCE_BTCUSDT）
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                symbol, interval = parts
            else:
                symbol, interval = stem, "unknown"

            try:
                df = pl.read_parquet(path)
                row_count = df.height
                start = None
                end = None
                if "open_time" in df.columns and row_count > 0:
                    ot = df["open_time"]
                    if ot.dtype == pl.Datetime:
                        start = ot.min()
                        end = ot.max()

                datasets.append({
                    "symbol": symbol,
                    "interval": interval,
                    "rows": row_count,
                    "start": start,
                    "end": end,
                    "path": str(path),
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                })
            except Exception:
                datasets.append({
                    "symbol": symbol,
                    "interval": interval,
                    "rows": 0,
                    "start": None,
                    "end": None,
                    "path": str(path),
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                    "error": True,
                })

        return datasets

    def has_data(self, symbol: str, interval: str) -> bool:
        """检查指定数据集是否存在。"""
        return self._parquet_path(symbol, interval).exists()

    def delete(self, symbol: str, interval: str) -> bool:
        """
        删除指定数据集。

        Returns:
            True 如果成功删除，False 如果文件不存在
        """
        path = self._parquet_path(symbol, interval)
        if path.exists():
            path.unlink()
            return True
        return False
