from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from scripts.app_config import (
    APP_TITLE,
    DEFAULT_SELECTED_PRODUCTS,
    MONEX_PRODUCTS,
)


@dataclass
class SidebarControls:
    reload_monex_json: bool
    uploaded_file: Any
    token_inputs: dict[str, str]
    run_manual_refresh: bool
    run_macro_refresh: bool
    difference_mode: str
    show_gold: bool


def secret_or_blank(name: str) -> str:
    try:
        return str(st.secrets.get(name, ""))
    except Exception:
        return ""


def render_header() -> None:
    st.title(APP_TITLE)
    st.caption(
        "Compares physical metal sale-price history with Yahoo Finance metals "
        "spot data."
    )
    st.write(
        "For the Monex 90 percent silver U.S. coin bag, 1 USD face value is treated as "
        "0.715 troy oz, so a $1000 face bag contains 715 oz."
    )
    st.write("Monex 10 oz silver bullion history begins on 09-22-2022.")
    st.write("Local baseline data pulled as of 03/21/2026.")


def _render_data_references() -> None:
    st.subheader("Data references")
    with st.expander("Yahoo Finance"):
        st.markdown(
            "- [Silver futures / spot proxy (SI=F)]"
            "(https://finance.yahoo.com/quote/SI%3DF/)\n"
            "- [Gold futures / spot proxy (GC=F)]"
            "(https://finance.yahoo.com/quote/GC%3DF/)"
        )

    with st.expander("Monex product pages"):
        st.markdown(
            "\n".join(
                f"- [{meta['label']}]({meta['page_url']})"
                for meta in MONEX_PRODUCTS.values()
            )
        )

    with st.expander("nFusion widget pages"):
        st.markdown(
            "\n".join(
                f"- [{meta['label']} widget]({meta['widget_url']})"
                for meta in MONEX_PRODUCTS.values()
            )
        )

    with st.expander("FRED macro data"):
        st.markdown(
            "- [U.S. 10Y Treasury yield (DGS10)]"
            "(https://fred.stlouisfed.org/series/DGS10)\n"
            "- [Japan 10Y government bond yield (IRLTLT01JPM156N)]"
            "(https://fred.stlouisfed.org/series/IRLTLT01JPM156N)\n"
            "- [U.S. CPI (CPIAUCSL)]"
            "(https://fred.stlouisfed.org/series/CPIAUCSL)\n"
            "- [U.S. unemployment (UNRATE)]"
            "(https://fred.stlouisfed.org/series/UNRATE)\n"
            "- [Real GDP growth (A191RL1Q225SBEA)]"
            "(https://fred.stlouisfed.org/series/A191RL1Q225SBEA)"
        )


def render_sidebar() -> SidebarControls:
    with st.sidebar:
        st.header("Data source options")
        reload_monex_json = st.button(
            "Reload Monex JSON files from disk",
            use_container_width=True,
        )
        uploaded_file = st.file_uploader(
            "Or upload matching Monex JSON",
            type=["json"],
        )

        st.markdown("---")
        st.subheader("Manual Monex token refresh")
        st.caption(
            "Paste bearer tokens below to query Monex manually. Blank products "
            "continue using their existing local JSON files."
        )
        with st.expander("How to find the bearer token"):
            st.markdown(
                "1. Open the relevant Monex link.\n"
                "2. Press **F12** and select **Network**.\n"
                "3. Reload the page if needed.\n"
                "4. Find the request named **history**.\n"
                "5. Copy the request as cURL.\n"
                "6. Copy the value following **Authorization: Bearer**."
            )

        token_inputs: dict[str, str] = {}
        for product_key, meta in MONEX_PRODUCTS.items():
            token_inputs[product_key] = st.text_input(
                f"Bearer token: {meta['label']}",
                value=secret_or_blank(str(meta["secret_name"])),
                type="password",
                key=f"token_{product_key}",
            )

        run_manual_refresh = st.button(
            "Query Monex using manual token input",
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("Manual data refresh")
        run_macro_refresh = st.button(
            "Refresh live Yahoo + FRED cache",
            use_container_width=True,
        )

        st.markdown("---")
        difference_mode = st.radio(
            "Difference chart mode",
            (
                "Absolute difference ($/oz)",
                "Percent premium / discount (%)",
            ),
            index=0,
        )
        show_gold = st.checkbox("Show gold close $/oz", value=True)

        st.markdown("---")
        _render_data_references()

    return SidebarControls(
        reload_monex_json=reload_monex_json,
        uploaded_file=uploaded_file,
        token_inputs=token_inputs,
        run_manual_refresh=run_manual_refresh,
        run_macro_refresh=run_macro_refresh,
        difference_mode=difference_mode,
        show_gold=show_gold,
    )


def render_date_controls(
    merged_df: pd.DataFrame,
    monex_all_df: pd.DataFrame,
    spot_df: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    global_min = merged_df["date"].min().date()
    global_max = merged_df["date"].max().date()

    initial_start = max(
        monex_all_df["date"].min().date(),
        spot_df["date"].min().date(),
    )
    initial_start = min(max(initial_start, global_min), global_max)
    initial_end = global_max

    # Session state survives reruns and data refreshes, so clamp it every time.
    stored_start = st.session_state.get("start_date", initial_start)
    stored_end = st.session_state.get("end_date", initial_end)

    current_start = min(max(stored_start, global_min), global_max)
    current_end = min(max(stored_end, global_min), global_max)

    if current_start > current_end:
        current_start = initial_start
        current_end = initial_end

    st.session_state.start_date = current_start
    st.session_state.end_date = current_end

    st.subheader("Date range")

    slider_start, slider_end = st.slider(
        "Select observed time range",
        min_value=global_min,
        max_value=global_max,
        value=(current_start, current_end),
        format="YYYY-MM-DD",
    )

    left, right = st.columns(2)

    with left:
        start_input = st.date_input(
            "Start date",
            value=slider_start,
            min_value=global_min,
            max_value=global_max,
        )

    with right:
        end_input = st.date_input(
            "End date",
            value=slider_end,
            min_value=global_min,
            max_value=global_max,
        )

    if start_input > end_input:
        st.error("Start date must be earlier than or equal to end date.")
        st.stop()

    st.session_state.start_date = start_input
    st.session_state.end_date = end_input

    return (
        pd.Timestamp(start_input).normalize(),
        pd.Timestamp(end_input).normalize(),
    )


def render_product_selector() -> list[str]:
    return st.multiselect(
        "Monex products to display",
        options=list(MONEX_PRODUCTS),
        default=list(DEFAULT_SELECTED_PRODUCTS),
        format_func=lambda key: str(MONEX_PRODUCTS[key]["label"]),
    )


def render_summary(summary_df: pd.DataFrame) -> None:
    latest = summary_df.sort_values("date").iloc[-1]
    columns = st.columns(5)
    columns[0].metric("Rows in view", f"{len(summary_df):,}")
    columns[1].metric("Latest selected product", latest["product_label"])
    columns[2].metric("Product last ($/oz)", f"{latest['last_per_oz']:.2f}")
    columns[3].metric(
        "Difference vs spot ($/oz)",
        f"{latest['product_minus_spot']:.2f}",
    )

    if {"gold_close_per_oz", "spot_close_per_oz"}.issubset(summary_df.columns):
        gold = summary_df["gold_close_per_oz"].dropna()
        silver = summary_df["spot_close_per_oz"].dropna()
        if not gold.empty and not silver.empty and silver.iloc[-1] != 0:
            columns[4].metric(
                "Gold/Silver ratio",
                f"{gold.iloc[-1] / silver.iloc[-1]:.2f}",
            )

    with st.expander("Latest row details"):
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
