"""
Page 3: Scanner — 策略扫描 & 结果

功能:
  - 选择数据集 + 规则
  - 配置 TradeEngine 参数
  - 执行扫描
  - 展示统计卡片 + 图表 + 交易明细
  - Filter 筛选器
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from core.feature_registry import FeatureRegistry
from core.rule_engine import RuleEngine
from core.trade_engine import TradeEngine, TradeConfig
from core.scanner import Scanner, ScanResult
from core.statistics import Statistics
from core.data_hub import DataHub
from core.i18n import t, init_lang, lang_toggle

st.set_page_config(page_title="Scanner — FactorLab", page_icon="🔍", layout="wide")

init_lang()

st.title(t("sc_title"))
st.caption(t("sc_caption"))


# ── 结果展示函数 ──
def _show_result(label: str, result: ScanResult, registry) -> None:
    """展示单个数据集的扫描结果。"""
    stats = result.stats
    if stats is None or result.total_trades == 0:
        st.info(t("sc_no_trades", label=label))
        return

    st.subheader(t("sc_result_title", label=label))

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(t("sc_total_trades"), stats.total_trades)
    c2.metric(t("sc_win_rate"), f"{stats.win_rate:.1f}%")
    c3.metric(t("sc_profit_factor"), f"{stats.profit_factor:.2f}")
    c4.metric(t("sc_expectancy"), f"{stats.expectancy:.3f}R")
    c5.metric(t("sc_max_dd"), f"{stats.max_drawdown_pct:.1f}%")
    c6.metric(t("sc_avg_hold"), f"{stats.avg_holding_bars:.1f} bars")

    c7, c8, c9, c10 = st.columns(4)
    c7.metric(t("sc_avg_win"), f"{stats.avg_win_r:.3f}R")
    c8.metric(t("sc_avg_loss"), f"{stats.avg_loss_r:.3f}R")
    c9.metric(t("sc_max_consec_loss"), stats.max_consecutive_loss)
    c10.metric(t("sc_total_r"), f"{stats.total_r:.2f}R")

    # 图表
    chart_tab1, chart_tab2, chart_tab3 = st.tabs([
        t("sc_equity_curve"), t("sc_return_dist"), t("sc_trade_details"),
    ])

    with chart_tab1:
        if stats.equity_curve:
            eq_df = pd.DataFrame({
                "Trade #": list(range(len(stats.equity_curve))),
                "Cumulative R": stats.equity_curve,
            })
            fig_eq = px.line(eq_df, x="Trade #", y="Cumulative R",
                             title=f"{label} {t('sc_equity_curve')}")
            fig_eq.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_eq, width='stretch')

        if stats.drawdown_curve:
            dd_df = pd.DataFrame({
                "Trade #": list(range(len(stats.drawdown_curve))),
                "Drawdown (R)": stats.drawdown_curve,
            })
            st.plotly_chart(
                px.area(dd_df, x="Trade #", y="Drawdown (R)",
                        title=f"{label} {t('sc_drawdown_curve')}"),
                width='stretch',
            )

    with chart_tab2:
        r_values = [t.r_multiple for t in result.trades]
        r_df = pd.DataFrame({"R Multiple": r_values})
        fig_hist = px.histogram(r_df, x="R Multiple", nbins=40,
                                title=t("sc_return_dist"),
                                color_discrete_sequence=["#2196F3"])
        fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_hist, width='stretch')

        cat_df = pd.DataFrame([
            {"Result": t.result.upper(), "R Multiple": t.r_multiple, "Hold": t.holding_bars}
            for t in result.trades
        ])
        if len(cat_df) > 0:
            st.plotly_chart(
                px.box(cat_df, x="Result", y="R Multiple", title="By Result"),
                width='stretch',
            )

    with chart_tab3:
        trades_df = pd.DataFrame([
            {
                "#": i, "Entry": t.entry_time, "Dir": t.direction,
                "Entry$": round(t.entry_price, 2), "Exit$": round(t.exit_price, 2),
                "SL": round(t.sl_price, 2), "TP": round(t.tp_price, 2),
                "Result": t.result.upper(), "R": round(t.r_multiple, 3),
                "Hold": t.holding_bars,
            }
            for i, t in enumerate(result.trades)
        ])
        st.dataframe(trades_df, width='stretch', hide_index=True, height=400)
        csv_data = trades_df.to_csv(index=False)
        st.download_button(t("sc_export_csv"), csv_data,
                           f"trades_{label.replace(' ', '_')}.csv", "text/csv")

    # Filter 筛选器
    st.divider()
    st.caption(t("sc_filter_section", label=label))

    if result.feature_snapshots is not None and len(result.trades) > 5:
        col_f1, col_f2, col_f3, col_f4 = st.columns([3, 1, 2, 1])
        with col_f1:
            filter_feature = st.selectbox(
                t("sc_filter_feature"), registry.list_all(),
                key=f"filter_feature_{label}",
            )
        with col_f2:
            filter_op = st.selectbox(t("sc_filter_op"), [">", "<", ">=", "<="],
                                     key=f"filter_op_{label}")
        with col_f3:
            snap = result.feature_snapshots
            if filter_feature in snap.columns:
                median_val = float(snap[filter_feature].median())
                filter_val = st.number_input(
                    t("sc_filter_val"), value=round(median_val, 2),
                    key=f"filter_val_{label}", step=0.1, format="%.2f",
                )
            else:
                filter_val = st.number_input(t("sc_filter_val"), value=0.0,
                                             key=f"filter_val_{label}")
        with col_f4:
            st.caption("")
            apply_filter = st.button(t("sc_filter_btn"), type="primary",
                                     key=f"apply_filter_{label}")

        if apply_filter:
            s = Statistics()
            filtered_trades = s.filter(
                result.trades,
                {"feature": filter_feature, "operator": filter_op, "value": filter_val},
            )
            f_stats = s.recompute(filtered_trades)

            col_before, col_after = st.columns(2)
            with col_before:
                st.caption(t("sc_filter_before"))
                st.metric(t("sc_filter_trades"), stats.total_trades)
                st.metric(t("sc_win_rate"), f"{stats.win_rate:.1f}%")
                st.metric(t("sc_expectancy"), f"{stats.expectancy:.3f}R")
            with col_after:
                st.caption(t("sc_filter_after"))
                st.metric(t("sc_filter_trades"), f_stats.total_trades)
                st.metric(t("sc_win_rate"), f"{f_stats.win_rate:.1f}%",
                          delta=f"{f_stats.win_rate - stats.win_rate:+.1f}%")
                st.metric(t("sc_expectancy"), f"{f_stats.expectancy:.3f}R",
                          delta=f"{f_stats.expectancy - stats.expectancy:+.3f}R")

            if f_stats.total_trades > 0 and f_stats.equity_curve:
                eq_f = pd.DataFrame({
                    "Trade #": list(range(len(f_stats.equity_curve))),
                    "Cumulative R": f_stats.equity_curve,
                })
                fig_f = px.line(eq_f, x="Trade #", y="Cumulative R",
                                title=t("sc_filter_equity"),
                                color_discrete_sequence=["#4CAF50"])
                fig_f.add_hline(y=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_f, width='stretch')


# ── 初始化 ──
if "feature_registry" not in st.session_state:
    st.session_state.feature_registry = FeatureRegistry()
if "rule_engine" not in st.session_state:
    st.session_state.rule_engine = RuleEngine(st.session_state.feature_registry)
if "data_hub" not in st.session_state:
    st.session_state.data_hub = DataHub()

registry = st.session_state.feature_registry
engine = st.session_state.rule_engine
hub = st.session_state.data_hub

trade_engine = TradeEngine(registry)
scanner = Scanner(engine, trade_engine, registry)

# ── 获取数据列表 ──
datasets = hub.list_datasets()
if not datasets:
    st.warning(t("sc_no_data_warning"))
    st.stop()

dataset_labels = [f"{d['symbol']} {d['interval']} ({d['rows']} rows)" for d in datasets]
symbols = [d["symbol"] for d in datasets]
intervals = [d["interval"] for d in datasets]


# ── 侧边栏: 语言切换 + 配置 ──
with st.sidebar:
    lang_toggle()
    st.divider()

    st.header(t("sc_sidebar_config"))

    # 数据集
    st.subheader(t("sc_data_section"))
    selected_indices = st.multiselect(
        t("sc_dataset_label"),
        range(len(datasets)),
        format_func=lambda i: dataset_labels[i],
        default=[0] if datasets else [],
    )
    if not selected_indices:
        st.warning(t("sc_select_dataset"))
        st.stop()

    # 规则
    st.subheader(t("sc_rule_section"))

    rule_source = st.radio(
        t("sc_rule_source"),
        [t("sc_rule_from_builder"), t("sc_rule_from_file")],
        horizontal=True,
    )

    rule_json = None
    if rule_source == t("sc_rule_from_builder"):
        if st.session_state.get("conditions"):
            items = []
            for feat, op, val, params in st.session_state.conditions:
                cond = {"feature": feat, "operator": op, "value": val}
                if params:
                    cond["params"] = params
                items.append(cond)
            logic = st.session_state.get("logic_mode", "and")
            rule_json = {logic: items}

        if rule_json and st.session_state.get("conditions"):
            st.success(t("sc_rule_n_conditions", n=len(st.session_state.conditions)))
        else:
            st.warning(t("sc_rule_empty"))
    else:
        rules_dir = Path("rules")
        json_files = list(rules_dir.glob("*.json"))
        if json_files:
            selected_file = st.selectbox(
                t("sc_select_file"),
                [f.name for f in json_files],
            )
            with open(rules_dir / selected_file) as f:
                rule_json = json.load(f)
        else:
            st.warning(t("sc_rules_empty"))

    st.divider()

    # Trade Config
    st.subheader(t("sc_trade_params"))

    direction = st.selectbox(t("sc_direction"), ["long", "short", "both"], index=0)
    entry_type = st.selectbox(t("sc_entry_type"), ["close", "open", "high", "low"])

    # ── 止损策略 ──
    st.caption(t("sc_sl_strategy_header"))
    sl_strategy_name = st.selectbox(
        t("sc_sl_type"),
        ["FixedSL", "ATRSL", "SwingSL", "BarExtremeSL", "CustomSL"],
    )

    # 初始化所有 SL 参数变量
    sl_pct, sl_period, sl_mult, sl_lookback, sl_price = 2.0, 14, 1.0, 10, 0.0
    if sl_strategy_name == "FixedSL":
        sl_pct = st.number_input("pct (%)", value=2.0, step=0.5, key="sl_fixed_pct")
    elif sl_strategy_name == "ATRSL":
        col_a, col_b = st.columns(2)
        with col_a:
            sl_period = st.number_input("period", value=14, min_value=2, max_value=200, step=1, key="sl_atr_period")
        with col_b:
            sl_mult = st.number_input("multiplier", value=1.0, step=0.5, key="sl_atr_mult")
    elif sl_strategy_name == "SwingSL":
        sl_lookback = st.number_input("lookback (bars)", value=10, min_value=1, max_value=200, step=1, key="sl_swing_lb")
    elif sl_strategy_name == "BarExtremeSL":
        sl_pct = st.number_input("pct (%)", value=2.0, step=0.5, key="sl_ext_pct")
    elif sl_strategy_name == "CustomSL":
        sl_price = st.number_input("price", value=0.0, step=1.0, key="sl_custom_price")

    # ── 止盈策略 ──
    st.caption(t("sc_tp_strategy_header"))
    tp_strategy_name = st.selectbox(
        t("sc_tp_type"),
        ["FixedRRTP", "FixedPctTP", "TargetTP", "CustomTP", "BollingerMidTP"],
    )

    # 初始化所有 TP 参数变量
    tp_rr, tp_pct, tp_price, tp_bb_period, tp_bb_std = 2.0, 2.0, 0.0, 20, 2.0
    if tp_strategy_name == "FixedRRTP":
        tp_rr = st.number_input("rr", value=2.0, step=0.5, key="tp_rr")
    elif tp_strategy_name == "FixedPctTP":
        tp_pct = st.number_input("pct (%)", value=2.0, step=0.5, key="tp_pct")
    elif tp_strategy_name == "TargetTP":
        tp_price = st.number_input("price", value=0.0, step=1.0, key="tp_target_price")
    elif tp_strategy_name == "CustomTP":
        tp_price = st.number_input("price", value=0.0, step=1.0, key="tp_custom_price")
    elif tp_strategy_name == "BollingerMidTP":
        col_a, col_b = st.columns(2)
        with col_a:
            tp_bb_period = st.number_input("period", value=20, min_value=2, max_value=200, step=1, key="tp_bb_period")
        with col_b:
            tp_bb_std = st.number_input("std_dev", value=2.0, min_value=0.5, max_value=5.0, step=0.1, key="tp_bb_std")

    max_hold = st.number_input(t("sc_max_hold"), value=50, min_value=1, max_value=500)

    st.divider()

    # 执行按钮
    run_scan = st.button(t("sc_run_btn"), type="primary", width='stretch')


# ── 主区域 ──
if run_scan:
    if rule_json is None or not engine.validate(rule_json):
        st.error(t("sc_rule_invalid"))
        st.stop()

    all_results: dict[str, ScanResult] = {}

    for ds_idx in selected_indices:
        dataset = datasets[ds_idx]
        key = f"{dataset['symbol']} {dataset['interval']}"

        try:
            df = hub.load(dataset["symbol"], dataset["interval"])
        except Exception as e:
            st.error(t("sc_load_failed", key=key, error=str(e)))
            continue

        # 构建策略对象
        from core.strategies.sl_strategies import (
            FixedSL, ATRSL, SwingSL, BarExtremeSL, CustomSL,
        )
        from core.strategies.tp_strategies import (
            FixedRRTP, FixedPctTP, TargetTP, CustomTP, BollingerMidTP,
        )

        sl_map = {
            "FixedSL": lambda: FixedSL(pct=sl_pct),
            "ATRSL": lambda: ATRSL(period=sl_period, multiplier=sl_mult),
            "SwingSL": lambda: SwingSL(lookback=sl_lookback),
            "BarExtremeSL": lambda: BarExtremeSL(pct=sl_pct),
            "CustomSL": lambda: CustomSL(price=sl_price),
        }
        sl_strategy = sl_map[sl_strategy_name]()

        tp_map = {
            "FixedRRTP": lambda: FixedRRTP(rr=tp_rr),
            "FixedPctTP": lambda: FixedPctTP(pct=tp_pct),
            "TargetTP": lambda: TargetTP(price=tp_price),
            "CustomTP": lambda: CustomTP(price=tp_price),
            "BollingerMidTP": lambda: BollingerMidTP(period=tp_bb_period, std_dev=tp_bb_std),
        }
        tp_strategy = tp_map[tp_strategy_name]()

        config = TradeConfig(
            direction=direction,
            entry_type=entry_type,
            sl_strategy=sl_strategy,
            tp_strategy=tp_strategy,
            max_holding_bars=max_hold,
        )

        with st.spinner(t("sc_loading", key=key)):
            result = scanner.full_scan(
                df, rule_json, config,
                symbol=dataset["symbol"], interval=dataset["interval"],
            )
            all_results[key] = result

    st.session_state.all_results = all_results

# ── 展示结果 ──
if "all_results" not in st.session_state or not st.session_state.all_results:
    st.info(t("sc_sidebar_hint"))
    st.stop()

all_results: dict[str, ScanResult] = st.session_state.all_results
result_keys = sorted(all_results.keys())

# ── 合并统计对比表 ──
if len(result_keys) > 1:
    st.header(t("sc_compare_title"))
    compare_rows = []
    for key in result_keys:
        r = all_results[key]
        s = r.stats
        if s and s.total_trades > 0:
            compare_rows.append({
                t("sc_dataset_label"): key,
                t("sc_compare_signal"): r.signal_count,
                t("sc_compare_trades"): s.total_trades,
                t("sc_compare_winrate"): round(s.win_rate, 1),
                t("sc_compare_pf"): round(s.profit_factor, 2),
                t("sc_compare_expectancy"): round(s.expectancy, 3),
                t("sc_compare_dd"): round(s.max_drawdown_pct, 1),
                t("sc_compare_totalr"): round(s.total_r, 2),
            })
    if compare_rows:
        st.dataframe(compare_rows, width='stretch', hide_index=True)
    st.divider()

# ── 每个数据集的结果 ──
if len(result_keys) == 1:
    _selected_key = result_keys[0]
    _result = all_results[_selected_key]
    _show_result(_selected_key, _result, registry)
else:
    tabs = st.tabs(result_keys)
    for tab, key in zip(tabs, result_keys):
        with tab:
            _result = all_results[key]
            _show_result(key, _result, registry)
