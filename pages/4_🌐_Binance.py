"""
Page 4: Binance Data — 币安历史数据下载

从 Binance 公开数据中心下载期货 K 线数据。
文件来源: https://data.binance.vision
"""

from __future__ import annotations

import datetime
import io
import tempfile
import zipfile
from pathlib import Path

import polars as pl
import requests
import streamlit as st
import xml.etree.ElementTree as ET

from core.i18n import t, init_lang, lang_toggle

st.set_page_config(page_title="Binance — FactorLab", page_icon="🌐", layout="wide")

init_lang()

with st.sidebar:
    lang_toggle()
    st.divider()

st.title(t("bn_title"))
st.caption(t("bn_caption"))

# ── 常量 ──
BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
DOWNLOAD_DIR = Path("data/binance")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

POPULAR_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "TAOUSDT",
]

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1mo"]

COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count", "taker_buy_volume",
    "taker_buy_quote_volume", "ignore",
]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_file_list(symbol: str, interval: str) -> list[str]:
    """从 Binance 公开数据目录获取文件列表（支持分页翻取全部数据）。"""
    prefix = f"data/futures/um/daily/klines/{symbol}/{interval}/"
    base_url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

    files = []
    marker = ""

    try:
        while True:
            url = f"{base_url}?delimiter=/&prefix={prefix}&max-keys=1000"
            if marker:
                url += f"&marker={marker}"

            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)

            for contents in root.findall("s3:Contents", ns):
                key = contents.find("s3:Key", ns)
                if key is not None and key.text.endswith(".zip"):
                    filename = key.text.rsplit("/", 1)[-1]
                    files.append(filename)

            is_truncated = root.find("s3:IsTruncated", ns)
            next_marker = root.find("s3:NextMarker", ns)

            if is_truncated is None or is_truncated.text != "true":
                break
            if next_marker is not None and next_marker.text:
                marker = next_marker.text
            else:
                break

        return sorted(files, reverse=True)

    except Exception as e:
        st.error(t("bn_fetch_failed", error=str(e)))
        return []


def download_and_parse(url: str) -> pl.DataFrame | None:
    """下载一个 zip 文件并解析其中的 CSV。"""
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                content = f.read()

        # 检测是否有 header
        first_line = content.split(b"\n", 1)[0].decode("utf-8", errors="ignore")
        if first_line.startswith("open_time"):
            df = pl.read_csv(
                content,
                has_header=True,
                schema_overrides={
                    "open_time": pl.Int64,
                    "open": pl.Float64, "high": pl.Float64,
                    "low": pl.Float64, "close": pl.Float64,
                    "volume": pl.Float64,
                },
            )
        else:
            df = pl.read_csv(
                content,
                has_header=False,
                new_columns=COLUMNS,
                schema_overrides={
                    "open_time": pl.Int64,
                    "open": pl.Float64, "high": pl.Float64,
                    "low": pl.Float64, "close": pl.Float64,
                    "volume": pl.Float64,
                },
            )
            keep = ["open_time", "open", "high", "low", "close", "volume"]
            df = df.select([c for c in keep if c in df.columns])

        return df

    except Exception as e:
        filename = url.rsplit("/", 1)[-1]
        st.warning(t("bn_download_file_failed", filename=filename, error=str(e)))
        return None


def save_to_parquet(df: pl.DataFrame, symbol: str, interval: str, dates: list[str]) -> Path:
    """保存为 Parquet。已有数据则合并去重。"""
    path = DOWNLOAD_DIR / f"{symbol}_{interval}.parquet"

    keep_cols = ["open_time", "open", "high", "low", "close", "volume"]
    df = df.select([c for c in keep_cols if c in df.columns])

    df = df.with_columns(pl.col("open_time").cast(pl.Int64))
    df = df.with_columns(
        pl.from_epoch("open_time", time_unit="ms").alias("open_time")
    )

    if path.exists():
        existing = pl.read_parquet(path)
        df = pl.concat([existing, df]).unique(subset=["open_time"], keep="last")
        df = df.sort("open_time")

    df.write_parquet(path)
    return path


# ── Session State ──
if "binance_files" not in st.session_state:
    st.session_state.binance_files = []
if "binance_downloaded" not in st.session_state:
    st.session_state.binance_downloaded = []
if "binance_symbol" not in st.session_state:
    st.session_state.binance_symbol = "BTCUSDT"
if "binance_interval" not in st.session_state:
    st.session_state.binance_interval = "4h"


# ── 主界面 ──
col1, col2 = st.columns(2)

with col1:
    symbol = st.text_input(
        t("bn_symbol_label"), value=st.session_state.binance_symbol,
        help=t("bn_symbol_help"),
    ).upper()
    st.session_state.binance_symbol = symbol
    st.caption(t("bn_popular_caption") + " · ".join(POPULAR_SYMBOLS))
    quick = st.selectbox(t("bn_symbol_quick"), [""] + POPULAR_SYMBOLS, label_visibility="collapsed")
    if quick:
        symbol = quick
        st.session_state.binance_symbol = quick

with col2:
    interval = st.selectbox(
        t("bn_interval_label"), INTERVALS,
        index=INTERVALS.index(st.session_state.binance_interval)
        if st.session_state.binance_interval in INTERVALS else 7,
    )
    st.session_state.binance_interval = interval

# 获取文件列表
if st.button(t("bn_fetch_btn"), type="primary"):
    with st.spinner(t("bn_fetch_spinner", symbol=symbol, interval=interval)):
        st.session_state.binance_files = fetch_file_list(symbol, interval)
    if not st.session_state.binance_files:
        st.warning(t("bn_no_files", symbol=symbol, interval=interval))

files = st.session_state.binance_files

if files:
    st.success(t("bn_found_files", count=len(files)))

    # 日期范围快速选择
    st.caption(t("bn_quick_filter"))
    quick_cols = st.columns(6)
    year_buttons = {
        "2026": quick_cols[0], "2025": quick_cols[1], "2024": quick_cols[2],
        "2023": quick_cols[3], "2022": quick_cols[4], t("bn_select_all"): quick_cols[5],
    }
    quick_filter = None
    for yr, col in year_buttons.items():
        if col.button(yr, key=f"yr_{yr}"):
            quick_filter = yr

    if quick_filter == t("bn_select_all"):
        default_files = files
    elif quick_filter:
        default_files = [f for f in files if quick_filter in f]
    else:
        this_year = str(datetime.datetime.now().year)
        default_files = [f for f in files if this_year in f]
        if not default_files:
            default_files = files[:3]

    # 快捷操作行
    action_cols = st.columns([1, 1, 1, 3])
    with action_cols[0]:
        if st.button(t("bn_select_all_btn"), key="select_all"):
            st.session_state["binance_selected"] = files
            st.rerun()
    with action_cols[1]:
        if st.button(t("bn_deselect_all_btn"), key="select_none"):
            st.session_state.pop("binance_selected", None)
            st.rerun()
    with action_cols[2]:
        this_year = str(datetime.datetime.now().year)
        if st.button(t("bn_select_year_btn", year=this_year), key=f"select_{this_year}"):
            st.session_state["binance_selected"] = [f for f in files if this_year in f]
            st.rerun()

    selected_files = st.multiselect(
        t("bn_file_select", total=len(files)),
        files,
        default=st.session_state.get("binance_selected", default_files),
    )

    if selected_files:
        st.caption(t("bn_selected_count", count=len(selected_files)))

    # 下载按钮
    if selected_files and st.button(t("bn_download_btn"), type="primary"):
        total = len(selected_files)
        progress = st.progress(0)
        status = st.empty()
        all_dfs = []
        success_count = 0

        for i, filename in enumerate(selected_files):
            status.text(t("bn_downloading", i=i + 1, total=total, filename=filename))
            url = f"{BASE_URL}/{symbol}/{interval}/{filename}"
            df = download_and_parse(url)

            if df is not None:
                all_dfs.append(df)
                success_count += 1

            progress.progress((i + 1) / total)

        if all_dfs:
            status.text(t("bn_merging"))
            combined = pl.concat(all_dfs)
            path = save_to_parquet(combined, symbol, interval,
                                   [f.replace(".zip", "") for f in selected_files])
            st.session_state.binance_downloaded = [f"{symbol} {interval}"]
            st.success(t("bn_download_success", success=success_count, total=total, path=str(path)))
            st.metric(t("bn_total_klines"), combined.height)
            st.metric(t("bn_time_range"),
                      f"{combined['open_time'].min()} ~ {combined['open_time'].max()}")
            st.dataframe(combined.head(10), width='stretch', hide_index=True)
        else:
            st.error(t("bn_download_failed"))

        status.empty()

# ── 已下载数据 ──
st.divider()
st.header(t("bn_downloaded_header"))

if DOWNLOAD_DIR.exists():
    parquet_files = sorted(DOWNLOAD_DIR.glob("*.parquet"))
    if parquet_files:
        rows = []
        for pf in parquet_files:
            name = pf.stem
            parts = name.split("_", 1)
            sym = parts[0]
            itv = parts[1] if len(parts) > 1 else "?"
            size_mb = round(pf.stat().st_size / (1024 * 1024), 2)
            try:
                df = pl.read_parquet(pf)
                kline_count = df.height
                time_range = f"{df['open_time'].min()} ~ {df['open_time'].max()}"
            except Exception:
                kline_count = "?"
                time_range = "?"
            rows.append({
                t("bn_col_symbol"): sym,
                t("bn_col_interval"): itv,
                t("bn_col_klines"): kline_count,
                t("bn_col_size"): size_mb,
                t("bn_col_range"): str(time_range),
            })

        st.dataframe(rows, width='stretch', hide_index=True)

        # 一键导入到 DataHub
        st.divider()
        st.caption(t("bn_import_hint"))
        if st.button(t("bn_import_btn"), type="secondary"):
            from core.data_hub import DataHub
            hub = DataHub()
            imported = 0
            for pf in parquet_files:
                name = pf.stem
                parts = name.split("_", 1)
                sym = parts[0]
                itv = parts[1] if len(parts) > 1 else "1h"
                try:
                    df = pl.read_parquet(pf)
                    target = Path("data/raw") / f"{sym}_{itv}.parquet"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    df.write_parquet(target)
                    imported += 1
                except Exception as e:
                    st.warning(t("bn_import_failed", sym=sym, itv=itv, error=str(e)))
            st.success(t("bn_import_success", count=imported))
            st.rerun()
    else:
        st.caption(t("bn_no_downloads"))
