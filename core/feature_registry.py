"""
core/feature_registry.py — 因子注册表

启动时自动扫描 feature/ 目录，注册所有包含 calculate() 函数的模块。
新增因子无需修改此文件或任何其他系统代码。

用法:
    from core.feature_registry import FeatureRegistry
    registry = FeatureRegistry()
    registry.list_all()          # ['ema', 'macd', 'rsi', ...]
    registry.get_info('ema')     # {name, category, params, description}
    registry.calculate('ema', df, period=20)
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import polars as pl


@dataclass
class FeatureInfo:
    """因子元信息。"""
    name: str
    category: str = "unknown"
    params: dict[str, str] = field(default_factory=dict)
    description: str = ""
    depends: list[str] = field(default_factory=list)


def _parse_docstring(doc: str) -> dict[str, str | dict | list]:
    """从模块 docstring 中提取元信息。"""
    info: dict = {"category": "unknown", "params": {}, "description": "", "depends": []}

    if not doc:
        return info

    # 提取分类
    cat_match = re.search(r'分类:\s*(\w+)', doc)
    if cat_match:
        info["category"] = cat_match.group(1)

    # 提取参数
    for m in re.finditer(r'(\w+):\s*(\w+)\s*=\s*([^\s]+)\s*(.*)', doc):
        info["params"][m.group(1)] = m.group(3)

    # 提取所需列
    dep_match = re.search(r'所需数据列:\s*(.+)', doc)
    if dep_match:
        info["depends"] = [c.strip() for c in dep_match.group(1).split(",")]

    # 提取简短描述（第一行）
    lines = doc.strip().split("\n")
    if lines:
        info["description"] = lines[0].strip()

    return info


class FeatureRegistry:
    """因子注册表。"""

    def __init__(self, plugin_dir: str | Path | None = None):
        self._features: dict[str, FeatureInfo] = {}
        self._callables: dict[str, Callable] = {}

        if plugin_dir is None:
            plugin_dir = Path(__file__).parent.parent / "feature"
        self._plugin_dir = Path(plugin_dir)
        self._scan()

    def _scan(self) -> None:
        """扫描 feature/ 目录，注册所有有效因子插件。"""
        if not self._plugin_dir.exists():
            return

        # 确保 feature 目录在 Python path 中
        feature_pkg = str(self._plugin_dir.parent)
        if feature_pkg not in sys.path:
            sys.path.insert(0, feature_pkg)

        for file_path in sorted(self._plugin_dir.glob("*.py")):
            if file_path.name.startswith("_"):
                continue

            module_name = file_path.stem
            try:
                # 使用 importlib 动态加载
                spec = importlib.util.spec_from_file_location(
                    f"feature.{module_name}", str(file_path)
                )
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if not hasattr(module, "calculate"):
                    continue

                # 解析 docstring
                doc = module.__doc__ or ""
                meta = _parse_docstring(doc)

                info = FeatureInfo(
                    name=module_name,
                    category=meta["category"],
                    params=meta["params"],
                    description=meta["description"],
                    depends=meta["depends"],
                )

                self._features[module_name] = info
                self._callables[module_name] = module.calculate

            except Exception as e:
                # 跳过无法加载的模块（但记录错误便于调试）
                print(f"[FeatureRegistry] 跳过 {module_name}: {e}")

    def list_all(self) -> list[str]:
        """返回所有已注册因子的名称列表。"""
        return sorted(self._features.keys())

    def list_by_category(self) -> dict[str, list[str]]:
        """按分类返回因子列表。"""
        result: dict[str, list[str]] = {}
        for name, info in self._features.items():
            result.setdefault(info.category, []).append(name)
        return result

    def get_info(self, name: str) -> FeatureInfo | None:
        """
        获取因子的元信息。

        Args:
            name: 因子名称

        Returns:
            FeatureInfo 对象，不存在则返回 None
        """
        return self._features.get(name)

    def calculate(self, name: str, df: pl.DataFrame, **params) -> pl.Series:
        """
        调用指定因子的 calculate 函数。

        Args:
            name: 因子名称
            df: K 线 DataFrame
            **params: 传递给因子的参数

        Returns:
            因子值 Series

        Raises:
            KeyError: 因子不存在
        """
        if name not in self._callables:
            registered = self.list_all()
            raise KeyError(
                f"因子 '{name}' 未注册。"
                f"可用因子: {registered}"
            )
        return self._callables[name](df, **params)

    def required_columns(self, name: str) -> list[str]:
        """返回因子所需的 OHLCV 列名。"""
        info = self.get_info(name)
        if info and info.depends:
            return info.depends
        return ["open", "high", "low", "close", "volume"]

    def __len__(self) -> int:
        return len(self._features)

    def __contains__(self, name: str) -> bool:
        return name in self._features
