from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf
from pandas_datareader.fred import FredReader

from scripts.app_config import (
    CACHE_DIR,
    FRED_SERIES,
    YAHOO_GOLD_TICKER,
    YAHOO_SILVER_TICKER,
)
from scripts.monex_data import attach_spot_and_spreads
from scripts.storage import load_pickle, save_pickle


def fetch_yahoo_metals_live(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
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

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            continue
        ticker_frame = raw[ticker].copy().reset_index()
        dates = pd.to_datetime(ticker_frame["Date"], errors="coerce").dt.normalize()
        output = pd.DataFrame({"date": dates})
        if ticker == YAHOO_SILVER_TICKER:
            output["spot_open_per_oz"] = pd.to_numeric(ticker_frame["Open"], errors="coerce")
            output["spot_close_per_oz"] = pd.to_numeric(ticker_frame["Close"], errors="coerce")
        else:
            output["gold_open_per_oz"] = pd.to_numeric(ticker_frame["Open"], errors="coerce")
            output["gold_close_per_oz"] = pd.to_numeric(ticker_frame["Close"], errors="coerce")
        frames.append(output)

    if not frames:
        raise ValueError("Yahoo Finance returned no usable silver/gold frames.")

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="date", how="outer")
    return merged.sort_values("date").reset_index(drop=True)


def get_yahoo_metals_data_resilient(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, list[str]]:
    cache_path = CACHE_DIR / "yahoo_metals.pkl"
    messages: list[str] = []
    try:
        frame = fetch_yahoo_metals_live(start_date, end_date)
        save_pickle(frame, cache_path)
        messages.append("Yahoo Finance metals data pulled live and cache updated.")
        return frame, messages
    except Exception as exc:
        messages.append(f"Yahoo Finance live pull failed: {exc}")

    if cache_path.exists():
        frame = load_pickle(cache_path)
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)].copy()
        messages.append("Using cached Yahoo metals data from local file.")
        return frame, messages

    raise RuntimeError("Yahoo Finance pull failed and no local Yahoo cache file exists.")


def fetch_fred_series_live(
    series_code: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.Series:
    reader = FredReader(
        symbols=series_code,
        start=start_date,
        end=end_date,
        timeout=8,
        retry_count=1,
        pause=0.1,
    )
    frame = reader.read()
    if frame is None or frame.empty or series_code not in frame.columns:
        raise ValueError(f"FRED returned no usable data for {series_code}.")

    series = pd.to_numeric(frame[series_code], errors="coerce")
    series.index = pd.to_datetime(series.index).normalize()
    return series.rename(series_code)


def get_fred_series_resilient(
    series_code: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.Series, list[str]]:
    cache_path = CACHE_DIR / f"fred_{series_code}.pkl"
    messages: list[str] = []
    try:
        series = fetch_fred_series_live(series_code, start_date, end_date)
        save_pickle(series, cache_path)
        messages.append(f"FRED {series_code} pulled live and cache updated.")
        return series, messages
    except Exception as exc:
        messages.append(f"FRED live pull failed for {series_code}: {exc}")

    if cache_path.exists():
        series = load_pickle(cache_path)
        series.index = pd.to_datetime(series.index).normalize()
        series = series[(series.index >= start_date) & (series.index <= end_date)]
        messages.append(f"Using cached local file for FRED {series_code}.")
        return series.rename(series_code), messages

    raise RuntimeError(f"FRED pull failed for {series_code} and no local cache exists.")


def expand_monthly_series_to_daily(
    series: pd.Series,
    daily_index: pd.DatetimeIndex,
) -> pd.Series:
    monthly = series.dropna().copy()
    monthly.index = pd.to_datetime(monthly.index).to_period("M")
    monthly_map = monthly.groupby(monthly.index).last()
    daily_periods = pd.to_datetime(daily_index).to_period("M")
    return pd.Series(daily_periods.map(monthly_map), index=daily_index, dtype="float64")


def expand_quarterly_series_to_daily(
    series: pd.Series,
    daily_index: pd.DatetimeIndex,
) -> pd.Series:
    quarterly = series.dropna().copy()
    quarterly.index = pd.to_datetime(quarterly.index).to_period("Q")
    quarterly_map = quarterly.groupby(quarterly.index).last()
    daily_periods = pd.to_datetime(daily_index).to_period("Q")
    return pd.Series(daily_periods.map(quarterly_map), index=daily_index, dtype="float64")


def build_macro_dataframe_resilient(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, list[str]]:
    messages: list[str] = []
    daily_index = pd.date_range(start=start_date, end=end_date, freq="D")
    macro = pd.DataFrame(index=daily_index)

    us10, current = get_fred_series_resilient("DGS10", start_date, end_date)
    messages.extend(current)
    macro = macro.join(us10.rename("us_10y_yield"), how="left")
    macro["us_10y_yield"] = macro["us_10y_yield"].ffill()

    jp10, current = get_fred_series_resilient("IRLTLT01JPM156N", start_date, end_date)
    messages.extend(current)
    macro["jpn_10y_yield"] = expand_monthly_series_to_daily(jp10.rename("jpn_10y_yield"), macro.index)

    cpi, current = get_fred_series_resilient("CPIAUCSL", start_date - pd.DateOffset(months=13), end_date)
    messages.extend(current)
    macro["us_cpi_index"] = expand_monthly_series_to_daily(cpi.rename("us_cpi_index"), macro.index)
    cpi_monthly = cpi.dropna().copy()
    cpi_monthly.index = pd.to_datetime(cpi_monthly.index).to_period("M")
    cpi_yoy = cpi_monthly.groupby(cpi_monthly.index).last().pct_change(12) * 100
    macro["us_cpi_yoy_pct"] = pd.Series(
        pd.to_datetime(macro.index).to_period("M").map(cpi_yoy),
        index=macro.index,
        dtype="float64",
    )

    unemployment, current = get_fred_series_resilient("UNRATE", start_date, end_date)
    messages.extend(current)
    macro["us_unemployment"] = expand_monthly_series_to_daily(
        unemployment.rename("us_unemployment"),
        macro.index,
    )

    gdp, current = get_fred_series_resilient("A191RL1Q225SBEA", start_date, end_date)
    messages.extend(current)
    macro["us_real_gdp_growth"] = expand_quarterly_series_to_daily(
        gdp.rename("us_real_gdp_growth"),
        macro.index,
    )

    return macro.reset_index().rename(columns={"index": "date"}), messages


def refresh_live_macro_cache(monex_all_df: pd.DataFrame) -> list[str]:
    messages: list[str] = []
    start_date = monex_all_df["date"].min()
    end_date = pd.Timestamp.today().normalize()

    try:
        _, current = get_yahoo_metals_data_resilient(start_date, end_date)
        messages.extend(current)
    except Exception as exc:
        messages.append(f"Yahoo refresh failed and no cache was available: {exc}")

    for series_code in FRED_SERIES:
        try:
            _, current = get_fred_series_resilient(series_code, start_date, end_date)
            messages.extend(current)
        except Exception as exc:
            messages.append(
                f"FRED refresh failed for {series_code} and no cache was available: {exc}"
            )
    return messages


@st.cache_data(show_spinner=False)
def build_full_merged_df(
    monex_all_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
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
