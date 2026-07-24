"""
FactorLab — 交易系统验证平台

一个完全离线、本地运行的交易系统验证平台。
支持两种模式：
  Mode 1: Replay  — 人工回放验证（Phase 2）
  Mode 2: Scanner — 自动规则扫描（Phase 1 MVP）

入口: streamlit run main.py
"""

import streamlit as st

from core.i18n import t, init_lang, lang_toggle

st.set_page_config(
    page_title="FactorLab",
    page_icon="🔬",
    layout="wide",
)

init_lang()

with st.sidebar:
    lang_toggle()
    st.divider()

st.title(t("app_title"))
st.caption(t("app_caption"))

st.markdown("---")
st.markdown(t("quick_start_title"))
st.markdown(t("quick_start_body"))
