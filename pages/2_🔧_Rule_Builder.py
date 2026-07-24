"""
Page 2: Rule Builder — 规则编辑器

功能:
  - 可视化构建规则（Feature | Operator | Value）
  - AND / OR 嵌套组合
  - JSON 实时预览
  - 保存 / 加载规则模板
  - 规则信号数预览
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import streamlit as st

from core.feature_registry import FeatureRegistry
from core.rule_engine import RuleEngine
from core.data_hub import DataHub
from core.i18n import (
    t, init_lang, lang_toggle,
    get_factor_range_hint, get_operator_name, get_feature_desc,
    get_category_display,
)

st.set_page_config(page_title="Rule Builder — FactorLab", page_icon="🔧", layout="wide")

init_lang()

with st.sidebar:
    lang_toggle()
    st.divider()

st.title(t("rb_title"))
st.caption(t("rb_caption"))

# ── 界面说明（可折叠）──
with st.expander(t("rb_help_expander"), expanded=False):
    st.markdown(t("rb_help_content"))


# ── 获取可用数据列表（必须在调用前定义）──
def _get_available_symbols() -> list[str]:
    try:
        hub = st.session_state.get("data_hub", DataHub())
        return [d["symbol"] for d in hub.list_datasets()]
    except Exception:
        return []


def _get_available_intervals() -> list[str]:
    try:
        hub = st.session_state.get("data_hub", DataHub())
        return [d["interval"] for d in hub.list_datasets()]
    except Exception:
        return []

# ── 初始化 ──
if "feature_registry" not in st.session_state:
    st.session_state.feature_registry = FeatureRegistry()

registry: FeatureRegistry = st.session_state.feature_registry

if "rule_engine" not in st.session_state:
    st.session_state.rule_engine = RuleEngine(registry)

engine: RuleEngine = st.session_state.rule_engine

# ── Session State: 当前规则条件列表 ──
if "conditions" not in st.session_state:
    st.session_state.conditions = []  # list of (feature, operator, value, params)

if "logic_mode" not in st.session_state:
    st.session_state.logic_mode = "and"  # "and" | "or"


# ── 辅助函数 ──
def add_condition(feature: str, operator: str, value: float | tuple, params: dict):
    """添加条件到当前规则。"""
    st.session_state.conditions.append((feature, operator, value, params))


def remove_condition(idx: int) -> None:
    """从当前规则中移除指定索引的条件。"""
    st.session_state.conditions.pop(idx)


def build_rule_json() -> dict:
    """从 conditions 构建规则 JSON。"""
    items = []
    for feat, op, val, params in st.session_state.conditions:
        cond = {"feature": feat, "operator": op, "value": val}
        if params:
            cond["params"] = params
        items.append(cond)

    if st.session_state.logic_mode == "and":
        return {"and": items} if items else {"and": []}
    else:
        return {"or": items} if items else {"or": []}


def load_rule_to_editor(rule_dict: dict):
    """将 JSON 规则加载到编辑器（仅支持单层 AND/OR）。"""
    logic = "and" if "and" in rule_dict else "or"
    items = rule_dict.get("and", rule_dict.get("or", []))

    st.session_state.conditions = []
    has_nested = False
    for item in items:
        if "and" in item or "or" in item:
            has_nested = True
            continue
        st.session_state.conditions.append((
            item["feature"],
            item["operator"],
            item["value"],
            item.get("params", {}),
        ))
    st.session_state.logic_mode = logic
    if has_nested:
        st.warning(t("rb_nested_warning"))


# ── 侧边栏: 因子信息 ──
with st.sidebar:
    st.header(t("rb_sidebar_available_features"))
    by_cat = registry.list_by_category()
    for cat, names in sorted(by_cat.items()):
        st.subheader(get_category_display(cat))
        for name in names:
            info = registry.get_info(name)
            if info:
                with st.expander(name.upper()):
                    # 显示双语描述
                    bilingual_desc = get_feature_desc(name)
                    if bilingual_desc:
                        st.caption(bilingual_desc)
                    else:
                        st.caption(info.description)
                    if info.params:
                        st.caption(f"{t('rb_params_caption', feature='')}: {info.params}")
                    if info.depends:
                        st.caption(f"Columns: {', '.join(info.depends)}")


# ── 主区域 ──
tab1, tab2, tab3 = st.tabs([t("rb_tab_edit"), t("rb_tab_json"), t("rb_tab_save")])

with tab1:
    st.subheader(t("rb_add_condition"))

    # 三列选择
    left, mid, right = st.columns([3, 2, 2])

    with left:
        feature_names = registry.list_all()
        display_names = []
        for name in feature_names:
            info = registry.get_info(name)
            cat = info.category if info else "unknown"
            display_names.append(f"[{cat}] {name}")

        selected_display = st.selectbox(
            t("rb_feature_label"),
            display_names,
            help=t("rb_feature_help"),
        )
        selected_feature = feature_names[display_names.index(selected_display)]

    with mid:
        operator = st.selectbox(
            t("rb_operator_label"),
            [">", "<", ">=", "<=", "==", "!=", "between", "cross_above", "cross_below"],
            help=t("rb_operator_help"),
        )

    with right:
        range_hint = get_factor_range_hint(selected_feature)
        if operator == "between":
            col_a, col_b = st.columns(2)
            with col_a:
                val_low = st.number_input(t("rb_value_low"), value=0.0, step=0.1, format="%.2f",
                                          help=range_hint)
            with col_b:
                val_high = st.number_input(t("rb_value_high"), value=100.0, step=0.1, format="%.2f",
                                           help=range_hint)
            value = [val_low, val_high]
        elif operator in ("cross_above", "cross_below"):
            value = st.number_input(
                t("rb_value_cross"), value=0.0, step=0.1, format="%.2f",
                help=t("rb_value_cross_help") + " " + range_hint,
            )
        else:
            value = st.number_input(
                t("rb_value_label"), value=0.0, step=0.1, format="%.2f",
                help=range_hint,
            )

    # 因子参数
    info = registry.get_info(selected_feature)
    extra_params = {}
    if info and info.params:
        st.caption(t("rb_params_caption", feature=selected_feature))
        param_cols = st.columns(len(info.params))
        for i, (pname, pdefault) in enumerate(info.params.items()):
            with param_cols[i]:
                if pdefault.replace(".", "").isdigit():
                    param_key = f"param_{pname}"
                    param_help_text = t(param_key)
                    if param_help_text == param_key:
                        param_help_text = f"{selected_feature} {pname}, default: {pdefault}"
                    extra_params[pname] = st.number_input(
                        pname,
                        value=float(pdefault) if "." in pdefault else int(pdefault),
                        step=1 if "." not in pdefault else 0.1,
                        help=param_help_text,
                    )
                else:
                    extra_params[pname] = st.text_input(
                        pname, value=pdefault,
                        help=f"{selected_feature} {pname}, default: {pdefault}",
                    )

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button(t("rb_add_btn"), type="primary", width='stretch'):
            add_condition(selected_feature, operator, value, extra_params)
            st.rerun()

    st.divider()

    # 当前规则列表
    st.subheader(t("rb_current_conditions"))

    logic_mode = st.radio(
        t("rb_logic_label"),
        [t("rb_logic_and"), t("rb_logic_or")],
        index=0 if st.session_state.logic_mode == "and" else 1,
        horizontal=True,
        help=t("rb_logic_help"),
    )
    st.session_state.logic_mode = "and" if "AND" in logic_mode else "or"

    if not st.session_state.conditions:
        st.info(t("rb_no_conditions"))
    else:
        # 条件统计
        cross_count = sum(1 for _, op, _, _ in st.session_state.conditions if op in ("cross_above", "cross_below"))
        stats_parts = [t("rb_conditions_count", n=len(st.session_state.conditions))]
        if cross_count > 0:
            stats_parts.append(t("rb_cross_count", n=cross_count))
        st.caption(" · ".join(stats_parts))

        for i, (feat, op, val, params) in enumerate(st.session_state.conditions):
            cols = st.columns([3.5, 0.5])
            param_str = ", ".join(f"{k}={v}" for k, v in params.items()) if params else ""
            val_str = f"[{val[0]}, {val[1]}]" if isinstance(val, list) else f"{val}"
            op_desc = get_operator_name(op)

            desc = get_feature_desc(feat)
            with cols[0]:
                st.write(f"**{feat.upper()}** {op_desc} {val_str}  {param_str}")
                if desc:
                    st.caption(f"↳ {desc}")
            with cols[1]:
                if st.button(t("rb_delete_btn"), key=f"del_{i}"):
                    remove_condition(i)
                    st.rerun()

        if st.button(t("rb_clear_all_btn"), type="secondary"):
            st.session_state.conditions = []
            st.rerun()

with tab2:
    st.subheader("Rule JSON")

    rule_json = build_rule_json()
    st.json(rule_json, expanded=True)

    is_valid = engine.validate(rule_json)
    if is_valid:
        st.success(t("rb_json_valid"))
    else:
        st.error(t("rb_json_invalid"))

    # 信号预览
    if is_valid and st.session_state.conditions:
        st.divider()
        st.subheader(t("rb_signal_preview"))

        col1, col2 = st.columns(2)
        with col1:
            symbol = st.selectbox(t("symbol"), _get_available_symbols(), key="preview_symbol")
        with col2:
            interval = st.selectbox(t("interval"), _get_available_intervals(), key="preview_interval")

        if st.button(t("rb_preview_btn"), type="primary"):
            try:
                hub = st.session_state.get("data_hub", DataHub())
                df = hub.load(symbol, interval)
                count = engine.count_signals(rule_json, df)
                st.info(t("rb_preview_result", symbol=symbol, interval=interval, rows=df.height, count=count))
            except FileNotFoundError:
                st.warning(t("rb_preview_no_data"))
            except Exception as e:
                st.error(str(e))

with tab3:
    st.subheader(t("rb_save_header"))

    col_save, col_load = st.columns(2)

    with col_save:
        rule_name = st.text_input(t("rb_rule_name"), value="my_rule")
        if st.button(t("rb_save_btn"), type="primary"):
            if not st.session_state.conditions:
                st.warning(t("rb_save_no_conditions"))
            else:
                rule_json = build_rule_json()
                rules_dir = Path("rules")
                rules_dir.mkdir(exist_ok=True)
                path = rules_dir / f"{rule_name}.json"
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(rule_json, f, indent=2, ensure_ascii=False)
                st.success(t("rb_save_success", path=str(path)))

    with col_load:
        rules_dir = Path("rules")
        json_files = list(rules_dir.glob("*.json"))
        if json_files:
            selected_rule = st.selectbox(
                t("rb_load_select"),
                [f.name for f in json_files],
            )
            if st.button(t("rb_load_btn"), type="primary"):
                with open(rules_dir / selected_rule) as f:
                    rule_dict = json.load(f)
                load_rule_to_editor(rule_dict)
                st.success(t("rb_load_success", name=selected_rule))
                st.rerun()
        else:
            st.caption(t("rb_load_empty"))
