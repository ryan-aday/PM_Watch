import json
import subprocess
from pathlib import Path
from typing import Optional
import pickle

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

import numpy as np
from pandas_datareader import data as pdr
from streamlit_extras.buy_me_a_coffee import button

import requests

st.set_page_config(page_title="Physical Metals vs Spot", layout="wide")


CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# -----------------------------
# Constants
# -----------------------------
DEFAULT_JSON_PATH = Path("history_90_percent_silver.json")
FALLBACK_JSON_PATH = Path("history.json")  # user-provided reference file
YAHOO_SILVER_TICKER = "SI=F"
YAHOO_GOLD_TICKER = "GC=F"

MONEX_PRODUCTS = {
    "junk_90_silver": {
        "label": "90% Silver U.S. Coin Bag",
        "symbol": "sc",
        "referer_symbol": "SC",
        "metal": "silver",
        "ounces_per_unit": 715.0,  # $1000 face * 0.715 oz per $1 face
        "json_file": "history_90_percent_silver.json",
        "page_url": "https://www.monex.com/90-us-silver-coin-bag-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SC",
        "bearer_token": st.secrets["JUNK_90_SILVER_BEARER_TOKEN"] 
    },
    "silver_eagles": {
        "label": "Silver American Eagles",
        "symbol": "saei",
        "referer_symbol": "SAEI",
        "metal": "silver",
        "ounces_per_unit": 1.0,  # Data already imported as cost per troy oz
        "json_file": "history_silver_eagles.json",
        "page_url": "https://www.monex.com/silver-american-eagle-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SAEI",
        "bearer_token": st.secrets["SILVER_EAGLES_BEARER_TOKEN"]
    },
    "gold_eagles": {
        "label": "Gold American Eagles",
        "symbol": "ae",
        "referer_symbol": "AE",
        "metal": "gold",
        "ounces_per_unit": 1.0, # Data already imported as cost per troy oz
        "json_file": "history_gold_eagles.json",
        "page_url": "https://www.monex.com/gold-american-eagle-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=AE",
        "bearer_token": st.secrets["GOLD_EAGLES_BEARER_TOKEN"]
    },
    "silver_1000oz": {
        "label": "1000 oz Silver Bullion",
        "symbol": "sbi1000",
        "referer_symbol": "SBI1000",
        "metal": "silver",
        "ounces_per_unit": 1000.0,
        "json_file": "history_1000oz_silver.json",
        "page_url": "https://www.monex.com/1000-oz-silver-bullion-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBI1000",
        "bearer_token": st.secrets["SILVER_1000_OZ_BEARER_TOKEN"]
    },
    "gold_1kg": {
        "label": "1 Kilo Gold Bullion Bar",
        "symbol": "gbx1k",
        "referer_symbol": "GBX1K",
        "metal": "gold",
        "ounces_per_unit": 32.1507466,
        "json_file": "history_1kg_gold.json",
        "page_url": "https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX1K",
        "bearer_token": st.secrets["GOLD_1_KG_BEARER_TOKEN"]
    },
    "gold_10oz": {
        "label": "10 oz Gold Bullion Bar",
        "symbol": "gbx10",
        "referer_symbol": "GBX10",
        "metal": "gold",
        "ounces_per_unit": 10.0,
        "json_file": "history_10oz_gold.json",
        "page_url": "https://www.monex.com/10-oz-gold-bullion-bar-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX10",
        "bearer_token": st.secrets["GOLD_10_OZ_BEARER_TOKEN"]
    },
    "silver_10oz": {
        "label": "10 oz Silver Bullion Bar",
        "symbol": "sbx",
        "referer_symbol": "SBX",
        "metal": "silver",
        "ounces_per_unit": 1.0, # Data already imported as cost per troy oz
        "json_file": "history_10oz_silver.json",
        "page_url": "https://www.monex.com/10-oz-silver-bullion-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBX",
        "bearer_token": st.secrets["SILVER_10_OZ_BEARER_TOKEN"]
    },
}


# User specified:
# $1 face value = 0.715 troy oz silver
TROY_OZ_PER_1_FACE = 0.715
FACE_VALUE_PER_BAG = 1000.0
TROY_OZ_PER_BAG = TROY_OZ_PER_1_FACE * FACE_VALUE_PER_BAG  # 715 oz


# -----------------------------
# Helpers
# -----------------------------

def save_pickle(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f)

def load_pickle(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)
        
        
def fetch_yahoo_metals_live(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    tickers = [YAHOO_SILVER_TICKER, YAHOO_GOLD_TICKER]

    raw = yf.download(
        tickers,
        start=(start_date - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=False,
    )

    if raw is None or raw.empty:
        raise ValueError("Yahoo Finance returned no metals data.")

    frames = []

    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            continue

        df = raw[ticker].copy().reset_index()
        df["date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()

        out = pd.DataFrame({"date": df["date"]})

        if ticker == YAHOO_SILVER_TICKER:
            out["spot_open_per_oz"] = pd.to_numeric(df["Open"], errors="coerce")
            out["spot_close_per_oz"] = pd.to_numeric(df["Close"], errors="coerce")
        elif ticker == YAHOO_GOLD_TICKER:
            out["gold_open_per_oz"] = pd.to_numeric(df["Open"], errors="coerce")
            out["gold_close_per_oz"] = pd.to_numeric(df["Close"], errors="coerce")

        frames.append(out)

    if not frames:
        raise ValueError("Yahoo Finance returned no usable silver/gold frames.")

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="date", how="outer")

    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def get_yahoo_metals_data_resilient(start_date: pd.Timestamp, end_date: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    cache_path = CACHE_DIR / "yahoo_metals.pkl"
    messages = []

    try:
        df = fetch_yahoo_metals_live(start_date, end_date)
        save_pickle(df, cache_path)
        messages.append("Yahoo Finance metals data pulled live and cache updated.")
        return df, messages
    except Exception as e:
        messages.append(f"Yahoo Finance live pull failed: {e}")

        if cache_path.exists():
            df = load_pickle(cache_path)
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
            messages.append("Using cached Yahoo metals data from local file.")
            return df, messages

        raise RuntimeError("Yahoo Finance pull failed and no local Yahoo cache file exists.")
        
def fetch_fred_series_live(series_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.Series:
    s = pdr.DataReader(series_code, "fred", start_date, end_date)
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).normalize()
    return s.rename(series_code)


def get_fred_series_resilient(series_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> tuple[pd.Series, list[str]]:
    cache_path = CACHE_DIR / f"fred_{series_code}.pkl"
    messages = []

    try:
        s = fetch_fred_series_live(series_code, start_date, end_date)
        save_pickle(s, cache_path)
        messages.append(f"FRED {series_code} pulled live and cache updated.")
        return s, messages
    except Exception as e:
        messages.append(f"FRED live pull failed for {series_code}: {e}")

        if cache_path.exists():
            s = load_pickle(cache_path)
            s.index = pd.to_datetime(s.index).normalize()
            s = s[(s.index >= start_date) & (s.index <= end_date)]
            messages.append(f"Using cached local file for FRED {series_code}.")
            return s.rename(series_code), messages

        raise RuntimeError(f"FRED pull failed for {series_code} and no local cache exists.")


def refresh_monex_json_to_file(
    output_path: Path,
    symbol: str,
    referer_symbol: str,
    bearer_token: str,
) -> tuple[bool, str]:
    url = "https://widget.nfusionsolutions.com/api/v1/Data/history"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "*/*",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Authorization": f"Bearer {bearer_token}",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://widget.nfusionsolutions.com",
        "Referer": f"https://widget.nfusionsolutions.com/custom/monex/chart/1/{st.secrets["COMMON_CLIENT_ID"]}/{st.secrets["COMMON_INSTANCE"]}?symbols={referer_symbol}",
        "Cookie": st.secrets["COMMON_COOKIE"],
    }

    data = {
        "clientId": st.secrets["COMMON_CLIENT_ID"],
        "instance": st.secrets["COMMON_INSTANCE"],
        "customId": "monex",
        "widgetVersion": "1",
        "widgetType": "chart",
        "symbols": symbol,
        "currency": "USD",
        "unitOfMeasure": "toz",
        "timeframeType": "year",
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=60)
        response.raise_for_status()

        # Validate JSON before saving
        parsed = response.json()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)

        return True, f"Refreshed {output_path.name}\n"

    except Exception as e:
        return False, f"Refresh failed for {output_path.name}: {e}\n"

@st.cache_data(show_spinner=False)
def load_monex_json_cached(json_path_str: str, product_key: str, mtime: float) -> pd.DataFrame:
    json_path = Path(json_path_str)
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    meta = MONEX_PRODUCTS[product_key]
    ounces_per_unit = float(meta["ounces_per_unit"])
    rows = []

    for item in raw:
        for interval in item.get("intervals", []):
            dt = pd.to_datetime(interval.get("start"), utc=True, errors="coerce")
            if pd.isna(dt):
                continue

            rows.append({
                "product_key": product_key,
                "product_label": meta["label"],
                "metal": meta["metal"],
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "date": dt.tz_convert(None).normalize(),
                "open_price": interval.get("open"),
                "high_price": interval.get("high"),
                "low_price": interval.get("low"),
                "last_price": interval.get("last"),
                "change": interval.get("change"),
                "changePercent": interval.get("changePercent"),
                "ounces_per_unit": ounces_per_unit,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"No interval rows found for product {product_key}")

    df = df.sort_values("date").reset_index(drop=True)

    for col in ["open_price", "high_price", "low_price", "last_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["open_per_oz"] = df["open_price"] / df["ounces_per_unit"]
    df["high_per_oz"] = df["high_price"] / df["ounces_per_unit"]
    df["low_per_oz"] = df["low_price"] / df["ounces_per_unit"]
    df["last_per_oz"] = df["last_price"] / df["ounces_per_unit"]

    return df
    
@st.cache_data(show_spinner=False)
def build_monex_all_df(file_specs: tuple) -> pd.DataFrame:
    frames = []
    for product_key, path_str, mtime in file_specs:
        df = load_monex_json_cached(path_str, product_key, mtime)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
    
@st.cache_data(show_spinner=False)
def build_full_merged_df(monex_all_df: pd.DataFrame):
    monex_min = monex_all_df["date"].min()

    spot_df, yahoo_messages = get_yahoo_metals_data_resilient(
        monex_min,
        pd.Timestamp.today().normalize(),
    )
    merged_df = attach_spot_and_spreads(monex_all_df, spot_df)

    macro_df, macro_messages = build_macro_dataframe_resilient(
        merged_df["date"].min(),
        merged_df["date"].max(),
    )
    merged_df = merged_df.merge(macro_df, on="date", how="left")

    return merged_df, spot_df, yahoo_messages, macro_messages


def attach_spot_and_spreads(monex_df: pd.DataFrame, spot_df: pd.DataFrame) -> pd.DataFrame:
    df = monex_df.merge(spot_df, on="date", how="inner").sort_values(["product_key", "date"]).reset_index(drop=True)

    df["reference_spot_per_oz"] = None
    df.loc[df["metal"] == "silver", "reference_spot_per_oz"] = df.loc[df["metal"] == "silver", "spot_close_per_oz"]
    df.loc[df["metal"] == "gold", "reference_spot_per_oz"] = df.loc[df["metal"] == "gold", "gold_close_per_oz"]

    df["reference_spot_per_oz"] = pd.to_numeric(df["reference_spot_per_oz"], errors="coerce")
    df["product_minus_spot"] = df["last_per_oz"] - df["reference_spot_per_oz"]
    df["product_pct_premium"] = (df["last_per_oz"] / df["reference_spot_per_oz"] - 1.0) * 100.0

    return df


def make_multi_product_price_chart(df, start_date, end_date, show_silver_spot=True, show_gold_spot=True):
    fig = go.Figure()

    for product_key in sorted(df["product_key"].dropna().unique()):
        sub = df[df["product_key"] == product_key]
        if sub.empty:
            continue

        metal = sub["metal"].iloc[0]
        axis = "y" if metal == "silver" else "y2"

        fig.add_trace(go.Scatter(
            x=sub["date"],
            y=sub["last_per_oz"],
            mode="lines",
            name=sub["product_label"].iloc[0],
            yaxis=axis,
        ))

    if show_silver_spot and "spot_close_per_oz" in df.columns:
        silver_spot = df[["date", "spot_close_per_oz"]].drop_duplicates().sort_values("date")
        fig.add_trace(go.Scatter(
            x=silver_spot["date"],
            y=silver_spot["spot_close_per_oz"],
            mode="lines",
            name="Silver spot proxy ($/oz)",
            yaxis="y",
        ))

    if show_gold_spot and "gold_close_per_oz" in df.columns:
        gold_spot = df[["date", "gold_close_per_oz"]].drop_duplicates().sort_values("date")
        fig.add_trace(go.Scatter(
            x=gold_spot["date"],
            y=gold_spot["gold_close_per_oz"],
            mode="lines",
            name="Gold spot proxy ($/oz)",
            yaxis="y2",
        ))

    fig.update_layout(
        title="Monex Products vs Spot",
        xaxis_title="Date",
        yaxis=dict(title="Silver USD per oz"),
        yaxis2=dict(title="Gold USD per oz", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
        height=620,
        margin=dict(l=60, r=70, t=95, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title=None),
    )
    fig.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return fig


def make_multi_product_difference_chart(df, mode, start_date, end_date):
    fig = go.Figure()

    for product_key in sorted(df["product_key"].dropna().unique()):
        sub = df[df["product_key"] == product_key]
        if sub.empty:
            continue

        y = sub["product_minus_spot"] if mode == "Absolute difference ($/oz)" else sub["product_pct_premium"]

        fig.add_trace(go.Scatter(
            x=sub["date"],
            y=y,
            mode="lines",
            name=sub["product_label"].iloc[0],
        ))

    fig.update_layout(
        title="Monex Product Premium / Discount vs Spot",
        xaxis_title="Date",
        yaxis_title="Difference" if mode == "Absolute difference ($/oz)" else "Premium / Discount (%)",
        hovermode="x unified",
        height=520,
        margin=dict(l=60, r=30, t=95, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title=None),
    )
    fig.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return fig

def build_macro_dataframe_resilient(start_date: pd.Timestamp, end_date: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    messages = []
    daily_index = pd.date_range(start=start_date, end=end_date, freq="D")
    macro = pd.DataFrame(index=daily_index)

    # Daily: US 10Y
    us10, msg = get_fred_series_resilient("DGS10", start_date, end_date)
    messages.extend(msg)
    macro = macro.join(us10.rename("us_10y_yield"), how="left")
    macro["us_10y_yield"] = macro["us_10y_yield"].ffill()

    # Monthly: Japan 10Y
    jp10_raw, msg = get_fred_series_resilient("IRLTLT01JPM156N", start_date, end_date)
    messages.extend(msg)
    macro["jpn_10y_yield"] = expand_monthly_series_to_daily(jp10_raw.rename("jpn_10y_yield"), macro.index)

    # Monthly: US CPI
    us_cpi_raw, msg = get_fred_series_resilient("CPIAUCSL", start_date - pd.DateOffset(months=13), end_date)
    messages.extend(msg)
    macro["us_cpi_index"] = expand_monthly_series_to_daily(us_cpi_raw.rename("us_cpi_index"), macro.index)

    us_cpi_monthly = us_cpi_raw.dropna().copy()
    us_cpi_monthly.index = pd.to_datetime(us_cpi_monthly.index).to_period("M")
    us_cpi_yoy_monthly = us_cpi_monthly.groupby(us_cpi_monthly.index).last().pct_change(12) * 100.0
    macro["us_cpi_yoy_pct"] = pd.Series(
        pd.to_datetime(macro.index).to_period("M").map(us_cpi_yoy_monthly),
        index=macro.index,
        dtype="float64",
    )

    # Monthly: US unemployment
    us_unrate_raw, msg = get_fred_series_resilient("UNRATE", start_date, end_date)
    messages.extend(msg)
    macro["us_unemployment"] = expand_monthly_series_to_daily(us_unrate_raw.rename("us_unemployment"), macro.index)

    # Quarterly: US real GDP growth
    us_gdp_growth_raw, msg = get_fred_series_resilient("A191RL1Q225SBEA", start_date, end_date)
    messages.extend(msg)
    macro["us_real_gdp_growth"] = expand_quarterly_series_to_daily(
        us_gdp_growth_raw.rename("us_real_gdp_growth"),
        macro.index,
    )

    macro = macro.reset_index().rename(columns={"index": "date"})
    return macro, messages

def expand_monthly_series_to_daily(s: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    """
    Expand a monthly series so that each daily date in a given month
    takes that month's value.
    """
    s = s.dropna().copy()
    s.index = pd.to_datetime(s.index).to_period("M")
    monthly_map = s.groupby(s.index).last()

    out = pd.Series(index=daily_index, dtype="float64")
    daily_periods = pd.to_datetime(daily_index).to_period("M")
    out[:] = daily_periods.map(monthly_map)
    return out

def expand_quarterly_series_to_daily(s: pd.Series, daily_index: pd.DatetimeIndex) -> pd.Series:
    """
    Expand a quarterly series so each daily date in a quarter
    takes that quarter's value.
    """
    s = s.dropna().copy()
    s.index = pd.to_datetime(s.index).to_period("Q")
    quarterly_map = s.groupby(s.index).last()

    out = pd.Series(index=daily_index, dtype="float64")
    daily_periods = pd.to_datetime(daily_index).to_period("Q")
    out[:] = daily_periods.map(quarterly_map)
    return out

def make_macro_chart(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> go.Figure:
    fig = go.Figure()

    series_map = [
        ("US 10Y yield (%)", "us_10y_yield"),
        ("JPN 10Y yield (%)", "jpn_10y_yield"),
        ("US CPI YoY (%)", "us_cpi_yoy_pct"),
        ("US unemployment (%)", "us_unemployment"),
        ("US real GDP growth SAAR (%)", "us_real_gdp_growth"),
    ]

    for label, col in series_map:
        if col in df.columns:
            plot_df = df[["date", col]].dropna().copy()
            if not plot_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=plot_df["date"],
                        y=plot_df[col],
                        mode="lines",
                        name=label,
                    )
                )

    fig.update_layout(
        title="Macro Overlay",
        xaxis_title="Date",
        yaxis_title="Value / rate",
        hovermode="x unified",
        height=520,
        margin=dict(l=60, r=30, t=90, b=80),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            title=None,
        ),
    )

    fig.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return fig

def build_correlation_dataframe(view_df: pd.DataFrame) -> pd.DataFrame:
    price_wide = view_df.pivot_table(index="date", columns="product_label", values="last_per_oz", aggfunc="last")
    spread_wide = view_df.pivot_table(index="date", columns="product_label", values="product_minus_spot", aggfunc="last")
    spread_wide.columns = [f"{c} minus spot" for c in spread_wide.columns]

    base_cols = [
        "spot_close_per_oz",
        "gold_close_per_oz",
        "us_10y_yield",
        "jpn_10y_yield",
        "us_cpi_yoy_pct",
        "us_unemployment",
        "us_real_gdp_growth",
    ]
    base = view_df[["date"] + [c for c in base_cols if c in view_df.columns]].drop_duplicates("date").set_index("date")

    corr_df = base.join(price_wide, how="outer").join(spread_wide, how="outer")
    return corr_df.sort_index()

def make_corr_heatmap(df: pd.DataFrame) -> go.Figure:
    corr = df.corr(numeric_only=True)

    fig = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            zmin=-1,
            zmax=1,
            colorbar=dict(title="Corr"),
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            hovertemplate="X: %{x}<br>Y: %{y}<br>Corr: %{z:.3f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Dynamic Correlation Heatmap (selected timeframe)",
        height=650,
        margin=dict(l=80, r=30, t=60, b=120),
    )
    return fig



# -----------------------------
# UI
# -----------------------------
st.title("Physical Metals vs Spot Prices")
st.caption(
    "Compares physical metal sale price history with Yahoo Finance metals spot data.\n "
)
st.write("For Monex 90% silver U.S. coin bag, assumes 1 USD face value = 0.715 troy oz, so a 1000 USD face bag contains 715 oz.\n ")
st.write("For Monex 10oz silver bullion bar, date starts on 09-22-2022.\n ")
st.write("Local data pulled as of 03/21/2026.\n")


with st.sidebar:
    st.header("Data source options")

    run_curl = st.button("Refresh Monex JSON files", use_container_width=True)
    uploaded_file = st.file_uploader("Or upload matching Monex JSON", type=["json"])

    st.markdown("---")
    show_open = st.checkbox("Show bag open $/oz", value=False)
    show_spot_open = st.checkbox("Show spot open $/oz", value=False)
    diff_mode = st.radio(
        "Difference chart mode",
        ["Absolute difference ($/oz)", "Percent premium / discount (%)"],
        index=0,
    )
    
    st.markdown("---")
    
    show_gold = st.checkbox("Show gold close $/oz", value=True)
    show_gold_open = st.checkbox("Show gold open $/oz", value=False)
    
    st.markdown("---")
    st.subheader("If you're a fan of my work, consider:")
    button(username="ryanaday", floating=False, width=221)
    
    st.markdown("---")
    st.subheader("Data references")

    with st.expander("Yahoo Finance"):
        st.markdown(
            "- [Silver futures / spot proxy (SI=F)](https://finance.yahoo.com/quote/SI%3DF/)\n"
            "- [Gold futures / spot proxy (GC=F)](https://finance.yahoo.com/quote/GC%3DF/)"
        )

    with st.expander("Monex product pages"):
        st.markdown(
            "- [90% Silver U.S. Coin Bag](https://www.monex.com/90-us-silver-coin-bag-price-charts/)\n"
            "- [Silver American Eagles](https://www.monex.com/silver-american-eagle-price-charts/)\n"
            "- [Gold American Eagles](https://www.monex.com/gold-american-eagle-price-charts/)\n"
            "- [1000 oz Silver Bullion](https://www.monex.com/1000-oz-silver-bullion-price-charts/)\n"
            "- [1 Kilo Gold Bullion Bar](https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/)\n"
            "- [10 oz Gold Bullion Bar](https://www.monex.com/10-oz-gold-bullion-bar-price-charts/)\n"
            "- [10 oz Silver Bullion Bar](https://www.monex.com/10-oz-silver-bullion-price-charts/)"
        )

    with st.expander("nFusion widget pages"):
        st.markdown(
            "- [90% Silver Coin Bag widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SC)\n"
            "- [Silver American Eagles widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SAEI)\n"
            "- [Gold American Eagles widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=AE)\n"
            "- [1000 oz Silver Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBI1000)\n"
            "- [1 Kilo Gold Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX1K)\n"
            "- [10 oz Gold Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX10)\n"
            "- [10 oz Silver Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBX)"
        )

    with st.expander("FRED macro data"):
        st.markdown(
            "- [U.S. 10Y Treasury yield (DGS10)](https://fred.stlouisfed.org/series/DGS10)\n"
            "- [Japan 10Y government bond yield (IRLTLT01JPM156N)](https://fred.stlouisfed.org/series/IRLTLT01JPM156N)\n"
            "- [U.S. CPI for All Urban Consumers (CPIAUCSL)](https://fred.stlouisfed.org/series/CPIAUCSL)\n"
            "- [U.S. unemployment rate (UNRATE)](https://fred.stlouisfed.org/series/UNRATE)\n"
            "- [Real GDP growth, percent change SAAR (A191RL1Q225SBEA)](https://fred.stlouisfed.org/series/A191RL1Q225SBEA)"
        )

# -----------------------------
# Load / refresh JSON
# -----------------------------
status_placeholder = st.empty()

if run_curl:
    refresh_messages = []

    for key, meta in MONEX_PRODUCTS.items():
        ok, msg = refresh_monex_json_to_file(
            output_path=Path(meta["json_file"]),
            symbol=meta["symbol"],
            referer_symbol=meta["referer_symbol"],
            bearer_token=meta["bearer_token"],
        )
        refresh_messages.append(msg)

    st.cache_data.clear()
    status_placeholder.info("\n".join(refresh_messages))


all_monex_frames = []

for key, meta in MONEX_PRODUCTS.items():
    path = Path(meta["json_file"])
    if path.exists():
        try:
            df = load_monex_json_cached(str(path), key, path.stat().st_mtime)
            all_monex_frames.append(df)
        except Exception as e:
            st.warning(f"Failed to load {meta['label']}: {e}")

if not all_monex_frames:
    st.error("No Monex product JSON files were loaded.")
    st.stop()

# Concatenate into one df (intended for faster loading of data through caching)
file_specs = []
for key, meta in MONEX_PRODUCTS.items():
    path = Path(meta["json_file"])
    if path.exists():
        file_specs.append((key, str(path), path.stat().st_mtime))

if not file_specs:
    st.error("No Monex product JSON files were loaded.")
    st.stop()

monex_all_df = build_monex_all_df(tuple(file_specs))    


# -----------------------------
# Spot data + merge
# -----------------------------
try:
    merged_df, spot_df, yahoo_messages, macro_messages = build_full_merged_df(monex_all_df)

    all_status_messages = yahoo_messages + macro_messages
    for msg in all_status_messages:
        if "failed" in msg.lower() or "cached" in msg.lower():
            st.warning(msg)

except Exception as e:
    st.error(f"Failed to build merged dataset: {e}")
    st.stop()
    
# Initial date range = latest first date of either series, then latest common end
global_min_date = merged_df["date"].min().date()
global_max_date = merged_df["date"].max().date()

initial_start = max(monex_all_df["date"].min().date(), spot_df["date"].min().date())
initial_end = merged_df["date"].max().date()

# Clamp defaults to valid slider bounds
if initial_start < global_min_date:
    initial_start = global_min_date
if initial_start > global_max_date:
    initial_start = global_max_date

if initial_end < global_min_date:
    initial_end = global_min_date
if initial_end > global_max_date:
    initial_end = global_max_date

if "start_date" not in st.session_state:
    st.session_state.start_date = initial_start
if "end_date" not in st.session_state:
    st.session_state.end_date = initial_end

st.subheader("Date range")

global_min_date = merged_df["date"].min().date()
global_max_date = merged_df["date"].max().date()

if "start_date" not in st.session_state:
    st.session_state.start_date = global_min_date
if "end_date" not in st.session_state:
    st.session_state.end_date = global_max_date

slider_start, slider_end = st.slider(
    "Select observed time range",
    min_value=global_min_date,
    max_value=global_max_date,
    value=(st.session_state.start_date, st.session_state.end_date),
    format="YYYY-MM-DD",
)

# Slider becomes the source of truth
st.session_state.start_date = slider_start
st.session_state.end_date = slider_end

c1, c2 = st.columns(2)

with c1:
    start_date_input = st.date_input(
        "Start date",
        value=st.session_state.start_date,
        min_value=global_min_date,
        max_value=global_max_date,
    )

with c2:
    end_date_input = st.date_input(
        "End date",
        value=st.session_state.end_date,
        min_value=global_min_date,
        max_value=global_max_date,
    )

# Manual inputs can override slider
st.session_state.start_date = start_date_input
st.session_state.end_date = end_date_input

start_date = pd.Timestamp(st.session_state.start_date).normalize()
end_date = pd.Timestamp(st.session_state.end_date).normalize()

if start_date > end_date:
    st.error("Start date must be earlier than or equal to end date.")
    st.stop()

view_df = merged_df[
    (merged_df["date"] >= start_date) &
    (merged_df["date"] <= end_date)
].copy()

if view_df.empty:
    st.warning("No data in selected date range.")
    st.stop()
    
selected_products = st.multiselect(
    "Monex products to display",
    options=list(MONEX_PRODUCTS.keys()),
    default=["junk_90_silver", "silver_eagles", "silver_10oz", "gold_eagles", "gold_10oz"],
    format_func=lambda k: MONEX_PRODUCTS[k]["label"],
)

filtered_view_df = view_df[
    view_df["product_key"].isin(selected_products)
].copy()

selected_min_dates = (
    filtered_view_df.groupby("product_label")["date"]
    .min()
    .sort_values()
)

if not selected_min_dates.empty:
    earliest_selected_data = selected_min_dates.min()
    if start_date < earliest_selected_data:
        st.info(
            f"Some selected products do not begin until later. "
            f"Earliest available selected-product data starts on {earliest_selected_data.date()}."
        )

# -----------------------------
# Summary stats
# -----------------------------
summary_df = view_df[view_df["product_key"].isin(selected_products)].copy()

if summary_df.empty:
    st.warning("No selected product data in selected date range.")
    st.stop()

latest_by_product = summary_df.sort_values("date").groupby("product_label").tail(1)
latest_row = summary_df.sort_values("date").iloc[-1]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows in view", f"{len(summary_df):,}")
c2.metric("Latest selected product", latest_row["product_label"])
c3.metric("Product last ($/oz)", f"{latest_row['last_per_oz']:.2f}")
c4.metric("Difference vs spot ($/oz)", f"{latest_row['product_minus_spot']:.2f}")

if "gold_close_per_oz" in summary_df.columns and "spot_close_per_oz" in summary_df.columns:
    gold_val = summary_df["gold_close_per_oz"].dropna()
    silver_val = summary_df["spot_close_per_oz"].dropna()
    if not gold_val.empty and not silver_val.empty and silver_val.iloc[-1] != 0:
        c5.metric("Gold/Silver ratio", f"{gold_val.iloc[-1] / silver_val.iloc[-1]:.2f}")


with st.expander("Latest row details"):
    latest = summary_df.sort_values("date").iloc[-1]
    st.json(
        {
            "date": str(latest["date"].date()),
            "product": latest["product_label"],
            "metal": latest["metal"],
            "last_price": float(latest["last_price"]),
            "last_per_oz": float(latest["last_per_oz"]),
            "reference_spot_per_oz": float(latest["reference_spot_per_oz"]),
            "difference_per_oz": float(latest["product_minus_spot"]),
            "premium_pct": float(latest["product_pct_premium"]),
        }
    )

# -----------------------------
# Charts
# -----------------------------

price_fig = make_multi_product_price_chart(
    filtered_view_df,
    start_date=start_date,
    end_date=end_date,
    show_silver_spot=True,
    show_gold_spot=show_gold,
)

diff_fig = make_multi_product_difference_chart(
    filtered_view_df,
    mode=diff_mode,
    start_date=start_date,
    end_date=end_date,
)

st.plotly_chart(price_fig, use_container_width=True)
st.plotly_chart(diff_fig, use_container_width=True)

# -----------------------------
# Macro plots and correlation map
# -----------------------------

macro_cols = [
    "us_10y_yield",
    "jpn_10y_yield",
    "us_cpi_yoy_pct",
    "us_unemployment",
    "us_real_gdp_growth",
]

macro_available = [c for c in macro_cols if c in filtered_view_df.columns]

if not macro_available or filtered_view_df[macro_available].dropna(how="all").empty:
    st.warning(
        "Macro overlay has no populated data in the selected timeframe. "
        "This usually means the FRED pull failed and no cached local macro data was available."
    )
else:
    macro_plot_df = (
        filtered_view_df.sort_values("date")
        .drop_duplicates(subset=["date"])
        .copy()
    )

    macro_fig = make_macro_chart(macro_plot_df, start_date=start_date, end_date=end_date)
    st.plotly_chart(macro_fig, use_container_width=True)

st.subheader("Correlation map")
st.caption(
    "Correlations are computed only over the currently selected timeframe, after aligning the series to a common daily index and forward-filling lower-frequency macro data."
)
st.write("-1.0 >= idx >= -0.7: Strong inverse correlation.")
st.write("0.7 <= idx <= 1.0: Strong positive correlation.")

corr_input_df = build_correlation_dataframe(filtered_view_df)
corr_fig = make_corr_heatmap(corr_input_df)
st.plotly_chart(corr_fig, use_container_width=True)


# -----------------------------
# Data tables / download
# -----------------------------
with st.expander("Merged data preview"):
    st.dataframe(
        summary_df[
            [
                "date",
                "product_label",
                "metal",
                "last_price",
                "last_per_oz",
                "reference_spot_per_oz",
                "product_minus_spot",
                "product_pct_premium",
            ]
        ],
        use_container_width=True,
    )

csv_bytes = filtered_view_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download current filtered view as CSV",
    data=csv_bytes,
    file_name="physical_metals_vs_spot_filtered_view.csv",
    mime="text/csv",
)