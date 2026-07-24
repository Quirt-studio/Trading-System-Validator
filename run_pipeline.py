#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — FactorLab 端到端验证管线

演示完整流程: 数据 → 规则 → 信号 → 交易 → 统计 → 报告

用法:
    python run_pipeline.py                           # 使用内置样本数据
    python run_pipeline.py --csv data/raw/BTCUSDT_4h.csv --symbol BTCUSDT --interval 4h
"""

import argparse
import json
import sys
from pathlib import Path

import polars as pl

from core.data_hub import DataHub
from core.feature_registry import FeatureRegistry
from core.rule_engine import RuleEngine
from core.trade_engine import TradeEngine, TradeConfig
from core.scanner import Scanner
from core.statistics import Statistics
from core.strategies.sl_strategies import FixedSL, ATRSL, SwingSL, CustomSL
from core.strategies.tp_strategies import FixedRRTP, FixedPctTP, TargetTP, CustomTP


def generate_sample_data(n: int = 500) -> pl.DataFrame:
    """
    生成模拟 K 线数据用于演示。

    包含上升、震荡、下跌、恢复四个阶段。
    """
    import random
    random.seed(42)

    rows = []
    close = 100.0

    for i in range(n):
        if i < 120:
            trend = 0.3   # 上升
        elif i < 200:
            trend = 0.0   # 震荡
        elif i < 320:
            trend = -0.3  # 下跌
        else:
            trend = 0.2   # 恢复

        noise = random.gauss(0, 0.5)
        close = close + trend + noise
        close = max(close, 10.0)

        high = close + abs(random.gauss(0, 0.3)) * close / 100
        low = close - abs(random.gauss(0, 0.3)) * close / 100
        _open = low + random.random() * (high - low)
        volume = abs(random.gauss(0, 1)) * 500 + 800

        rows.append({
            "open": round(_open, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": round(volume, 2),
        })

    return pl.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FactorLab — 交易系统验证管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_pipeline.py
  python run_pipeline.py --csv data/raw/BTCUSDT_4h.parquet --symbol BTCUSDT --interval 4h
  python run_pipeline.py --rule rules/bollinger_break.json --direction long --sl 2 --tp 2
        """,
    )
    parser.add_argument("--csv", help="K线数据文件 (CSV 或 Parquet)")
    parser.add_argument("--symbol", default="SAMPLE", help="交易对 (默认: SAMPLE)")
    parser.add_argument("--interval", default="4h", help="K线周期 (默认: 4h)")
    parser.add_argument("--rule", help="规则 JSON 文件路径")
    parser.add_argument("--direction", default="long", choices=["long", "short", "both"])
    parser.add_argument("--entry", default="close", help="入场价类型")
    parser.add_argument("--sl", type=float, default=2.0, help="止损参数")
    parser.add_argument("--tp", type=float, default=2.0, help="止盈参数")
    parser.add_argument("--sl-type", default="fixed", choices=["fixed", "atr", "swing", "bar_extreme", "custom"])
    parser.add_argument("--tp-type", default="rr", choices=["rr", "fixed_pct", "target", "custom", "bollinger_mid"])
    parser.add_argument("--max-hold", type=int, default=50, help="最大持仓 K线数")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")

    args = parser.parse_args()

    # ━━━ 1. 加载数据 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("📊 加载数据...")
    hub = DataHub()

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"❌ 文件不存在: {args.csv}")
            sys.exit(1)

        if csv_path.suffix in (".parquet",):
            # 直接复制到 data/raw 或从原地加载
            df = pl.read_parquet(csv_path)
            # 也复制到 data/raw 供后续使用
            args.symbol = args.symbol or csv_path.stem.split("_")[0]
            args.interval = args.interval or csv_path.stem.split("_")[-1]
        else:
            df = hub.import_csv(csv_path, args.symbol, args.interval)
    else:
        print("   使用内置样本数据 (500 行模拟 K 线)")
        df = generate_sample_data(500)

    print(f"   数据: {df.height} 行, {len(df.columns)} 列")
    print(f"   列: {df.columns}")

    # ━━━ 2. 初始化核心模块 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("🔧 初始化引擎...")
    registry = FeatureRegistry()
    rule_engine = RuleEngine(registry)
    trade_engine = TradeEngine(registry)
    scanner = Scanner(rule_engine, trade_engine, registry)
    print(f"   已注册 {len(registry)} 个因子: {', '.join(registry.list_all()[:6])}...")

    # ━━━ 3. 加载或构建规则 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("📐 构建规则...")
    if args.rule:
        rule_path = Path(args.rule)
        if not rule_path.exists():
            print(f"❌ 规则文件不存在: {args.rule}")
            sys.exit(1)
        with open(rule_path) as f:
            rule_json = json.load(f)
        print(f"   从文件加载: {args.rule}")
    else:
        # 默认演示规则：EMA 看涨 + 成交量正常
        rule_json = {
            "and": [
                {"feature": "ema", "operator": ">", "value": 0, "params": {"period": 20}},
                {"feature": "volume", "operator": ">", "value": 0.5},
            ]
        }
        print("   使用默认规则: EMA看涨 + 成交量>均量50%")

    if not rule_engine.validate(rule_json):
        print("❌ 规则格式无效")
        sys.exit(1)

    # 预览信号数
    preview_count = rule_engine.count_signals(rule_json, df)
    print(f"   信号预览: {preview_count} 个匹配")

    # ━━━ 4. 配置交易参数 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    sl_map = {
        "fixed": lambda: FixedSL(pct=args.sl),
        "atr": lambda: ATRSL(period=14, multiplier=args.sl),
        "swing": lambda: SwingSL(lookback=int(args.sl)),
        "bar_extreme": lambda: FixedSL(pct=args.sl),  # fallback, use BarExtremeSL if needed
        "custom": lambda: CustomSL(price=args.sl),
    }
    sl_strategy = sl_map[args.sl_type]()

    tp_map = {
        "rr": lambda: FixedRRTP(rr=args.tp),
        "fixed_pct": lambda: FixedPctTP(pct=args.tp),
        "target": lambda: TargetTP(price=args.tp),
        "custom": lambda: CustomTP(price=args.tp),
        "bollinger_mid": lambda: FixedRRTP(rr=args.tp),  # fallback
    }
    tp_strategy = tp_map[args.tp_type]()

    config = TradeConfig(
        direction=args.direction,
        entry_type=args.entry,
        sl_strategy=sl_strategy,
        tp_strategy=tp_strategy,
        max_holding_bars=args.max_hold,
    )
    print(f"   方向: {config.direction}, 入场: {config.entry_type}")
    print(f"   SL: {args.sl_type}={args.sl}, TP: {args.tp_type}={args.tp}")
    print(f"   最大持仓: {config.max_holding_bars} 根K线")

    # ━━━ 5. 执行扫描 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("🔍 执行扫描...")
    result = scanner.full_scan(
        df, rule_json, config,
        symbol=args.symbol, interval=args.interval,
    )

    if args.json:
        print(json.dumps(result.summary(), ensure_ascii=False, indent=2))
    else:
        result.print_report()

        # ━━━ 6. 额外分析 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if result.trades and result.stats:
            trades = result.trades
            stats = result.stats

            print()
            print("📈 额外分析:")
            print(f"  总 R 倍数:     {stats.total_r:.2f}R")
            print(f"  平均盈利:      {stats.avg_win_r:.3f}R")
            print(f"  平均亏损:      {stats.avg_loss_r:.3f}R")
            print(f"  盈利/亏损比:   {stats.avg_rr:.2f}")
            print(f"  盈利持仓:      {stats.avg_holding_bars_win:.1f} 根")
            print(f"  亏损持仓:      {stats.avg_holding_bars_loss:.1f} 根")

            # 结果分布
            tp_count = sum(1 for t in trades if t.result == "tp")
            sl_count = sum(1 for t in trades if t.result == "sl")
            to_count = sum(1 for t in trades if t.result == "timeout")
            print(f"  结果分布:      TP={tp_count}  SL={sl_count}  Timeout={to_count}")

            # 如果信号够多，尝试筛选
            if stats.total_trades > 10 and result.feature_snapshots is not None:
                print()
                print("📊 Filter 示例: 仅保留 ATR < 中位数的交易")
                s = Statistics()
                median_atr = float(result.feature_snapshots["atr"].median())
                filtered = s.filter(
                    trades,
                    {"feature": "atr", "operator": "<", "value": median_atr},
                )
                f_stats = s.recompute(filtered)
                print(f"   筛选后: {f_stats.total_trades} 笔")
                print(f"   胜率:   {f_stats.win_rate:.1f}%")
                print(f"   期望值: {f_stats.expectancy:.3f}R")
                print(f"   (全部:  {stats.win_rate:.1f}% / {stats.expectancy:.3f}R)")

    print()
    print("✅ 管线完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
