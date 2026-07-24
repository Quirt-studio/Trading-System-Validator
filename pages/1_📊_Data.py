"""
Page 1: Data Hub — 数据中心

功能:
  - 上传 CSV 文件导入数据
  - 查看已导入数据集列表
  - 删除数据集
  - 数据预览
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl
import streamlit as st

from core.data_hub import DataHub
from core.i18n import t, init_lang, lang_toggle

st.set_page_config(page_title="Data — FactorLab", page_icon="📊", layout="wide")

init_lang()

with st.sidebar:
    lang_toggle()
    st.divider()

st.title(t("data_title"))
st.caption(t("data_caption"))

# ── 初始化 ──
if "data_hub" not in st.session_state:
    st.session_state.data_hub = DataHub()

hub: DataHub = st.session_state.data_hub


# ── 已导入数据列表 ──
st.header(t("data_imported_header"))

datasets = hub.list_datasets()

if not datasets:
    st.info(t("data_no_data"))
else:
    # 构建表格
    rows = []
    for ds in datasets:
        rows.append({
            t("data_col_symbol"): ds["symbol"],
            t("data_col_interval"): ds["interval"],
            t("data_col_rows"): ds["rows"],
            t("data_col_start"): str(ds.get("start", "N/A")),
            t("data_col_end"): str(ds.get("end", "N/A")),
            t("data_col_size"): ds["size_mb"],
        })

    # 显示表格
    col1, col2 = st.columns([3, 1])
    with col1:
        selected = st.dataframe(
            rows, width='stretch',
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
        )

    with col2:
        st.caption(t("data_actions"))
        if selected and len(selected.selection.rows) > 0:
            for idx in selected.selection.rows:
                ds = datasets[idx]
                sym = ds["symbol"]
                itv = ds["interval"]

                if st.button(f"{t('data_delete_btn')} {sym} {itv}", type="secondary", key=f"del_{sym}_{itv}"):
                    hub.delete(sym, itv)
                    st.success(t("data_deleted", symbol=sym, interval=itv))
                    st.rerun()

            # 数据预览（仅单选时）
            if len(selected.selection.rows) == 1:
                idx = selected.selection.rows[0]
                ds = datasets[idx]
                sym = ds["symbol"]
                itv = ds["interval"]
                if st.button(f"{t('data_preview_btn')} {sym} {itv}", key=f"preview_{sym}_{itv}"):
                    try:
                        df = hub.load(sym, itv)
                        st.dataframe(df.head(20), width='stretch')
                        st.caption(t("data_total_rows", rows=df.height, cols=len(df.columns)))
                    except Exception as e:
                        st.error(str(e))


# ── 导入新数据 ──
st.header(t("data_import_header"))
st.caption(t("data_import_caption"))

col1, col2, col3 = st.columns(3)

with col1:
    symbol = st.text_input(t("symbol"), value="BTCUSDT", help="e.g. BTCUSDT")
with col2:
    interval = st.selectbox(t("interval"), ["1m", "5m", "15m", "1h", "4h", "1d", "1w"], index=3)
with col3:
    st.caption("")  # spacer

uploaded = st.file_uploader(
    t("data_upload_label"),
    type=["csv"],
    help=t("data_upload_help"),
)

if uploaded and symbol:
    if st.button(t("import_btn"), type="primary"):
        with st.spinner(t("importing", symbol=symbol, interval=interval)):
            # 保存临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            try:
                df = hub.import_csv(Path(tmp_path), symbol, interval)
                st.success(t("import_success", rows=df.height))
                st.dataframe(df.head(10), width='stretch')
                st.rerun()
            except Exception as e:
                st.error(t("import_failed", error=str(e)))
            finally:
                Path(tmp_path).unlink(missing_ok=True)

# ── 示例数据 ──
st.divider()
st.caption(t("data_sample_caption"))

if st.button(t("data_sample_btn")):
    import random
    random.seed(42)
    rows_data = []
    close = 100.0
    for i in range(500):
        if i < 120:
            trend = 0.3
        elif i < 200:
            trend = 0.0
        elif i < 320:
            trend = -0.3
        else:
            trend = 0.2
        noise = random.gauss(0, 0.5)
        close = close + trend + noise
        close = max(close, 10.0)
        high = close + abs(random.gauss(0, 0.3)) * close / 100
        low = close - abs(random.gauss(0, 0.3)) * close / 100
        _open = low + random.random() * (high - low)
        volume = abs(random.gauss(0, 1)) * 500 + 800
        rows_data.append({
            "open": round(_open, 2), "high": round(high, 2),
            "low": round(low, 2), "close": round(close, 2),
            "volume": round(volume, 2),
        })

    df = pl.DataFrame(rows_data)
    sample_path = Path("data/raw/SAMPLE_4h.parquet")
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(sample_path)
    st.success(t("data_sample_success", path=str(sample_path), rows=df.height))
    st.rerun()
