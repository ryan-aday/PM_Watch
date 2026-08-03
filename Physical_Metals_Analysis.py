from __future__ import annotations

import streamlit as st

from scripts.app_config import APP_TITLE, MACRO_COLUMNS
from scripts.charts import (
    build_correlation_dataframe,
    make_corr_heatmap,
    make_macro_chart,
    make_multi_product_difference_chart,
    make_multi_product_price_chart,
)
from scripts.market_data import build_full_merged_df, refresh_live_macro_cache
from scripts.monex_data import (
    build_monex_all_df,
    discover_monex_file_specs,
    refresh_products_with_manual_tokens,
    reload_local_monex_files,
)
from scripts.ui_helpers import (
    render_date_controls,
    render_header,
    render_product_selector,
    render_sidebar,
    render_summary,
    secret_or_blank,
)


st.set_page_config(page_title=APP_TITLE, layout="wide")
render_header()
controls = render_sidebar()
status_placeholder = st.empty()

if controls.reload_monex_json:
    available_files, missing_files = reload_local_monex_files()
    if available_files:
        status_placeholder.success(
            "Reloaded local Monex JSON data from: " + ", ".join(available_files)
        )
    if missing_files:
        status_placeholder.warning(
            "Missing local Monex JSON files: " + ", ".join(missing_files)
        )

if controls.run_manual_refresh:
    messages = refresh_products_with_manual_tokens(
        token_inputs=controls.token_inputs,
        client_id=secret_or_blank("COMMON_CLIENT_ID"),
        instance=secret_or_blank("COMMON_INSTANCE"),
        cookie=secret_or_blank("COMMON_COOKIE"),
    )
    status_placeholder.info("\n".join(messages))

file_specs = discover_monex_file_specs()
if not file_specs:
    st.error("No Monex product JSON files were found.")
    st.stop()

try:
    monex_all_df, monex_load_errors = build_monex_all_df(file_specs)
except Exception as exc:
    st.error(f"No Monex product JSON files could be loaded: {exc}")
    st.stop()

for message in monex_load_errors:
    st.warning(message)

if controls.run_macro_refresh:
    refresh_messages = refresh_live_macro_cache(monex_all_df)
    build_full_merged_df.clear()
    status_placeholder.info("\n".join(refresh_messages))

try:
    merged_df, spot_df, yahoo_messages, macro_messages = build_full_merged_df(monex_all_df)
except Exception as exc:
    st.error(f"Failed to build merged dataset: {exc}")
    st.stop()

for message in [*yahoo_messages, *macro_messages]:
    lowered = message.lower()
    if "failed" in lowered or "cached" in lowered:
        st.warning(message)

try:
    start_date, end_date = render_date_controls(
        merged_df,
        monex_all_df,
        spot_df,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

view_df = merged_df[
    (merged_df["date"] >= start_date)
    & (merged_df["date"] <= end_date)
].copy()
if view_df.empty:
    st.warning("No data in the selected date range.")
    st.stop()

selected_products = render_product_selector()
filtered_view_df = view_df[
    view_df["product_key"].isin(selected_products)
].copy()
if filtered_view_df.empty:
    st.warning("No selected product data exists in the selected date range.")
    st.stop()

selected_min_dates = filtered_view_df.groupby("product_label")["date"].min().sort_values()
if not selected_min_dates.empty:
    earliest_selected = selected_min_dates.min()
    if start_date < earliest_selected:
        st.info(
            "Some selected products begin later. The earliest selected-product "
            f"data starts on {earliest_selected.date()}."
        )

summary_df = view_df[view_df["product_key"].isin(selected_products)].copy()
render_summary(summary_df)

price_figure = make_multi_product_price_chart(
    filtered_view_df,
    start_date=start_date,
    end_date=end_date,
    show_silver_spot=True,
    show_gold_spot=controls.show_gold,
)
difference_figure = make_multi_product_difference_chart(
    filtered_view_df,
    mode=controls.difference_mode,
    start_date=start_date,
    end_date=end_date,
)
st.plotly_chart(price_figure, use_container_width=True)
st.plotly_chart(difference_figure, use_container_width=True)

macro_available = [
    column for column in MACRO_COLUMNS if column in filtered_view_df.columns
]
if (
    not macro_available
    or filtered_view_df[list(macro_available)].dropna(how="all").empty
):
    st.warning(
        "Macro overlay has no populated data in the selected timeframe. "
        "The live FRED pull may have failed without a usable local cache."
    )
else:
    macro_plot_df = (
        filtered_view_df.sort_values("date")
        .drop_duplicates(subset=["date"])
        .copy()
    )
    st.plotly_chart(
        make_macro_chart(
            macro_plot_df,
            start_date=start_date,
            end_date=end_date,
        ),
        use_container_width=True,
    )

st.subheader("Correlation map")
st.caption(
    "Correlations use only the selected timeframe after aligning series to "
    "a common daily index and expanding lower-frequency macro data."
)
st.write("-1.0 to -0.7: strong inverse correlation.")
st.write("0.7 to 1.0: strong positive correlation.")
correlation_input = build_correlation_dataframe(filtered_view_df)
st.plotly_chart(
    make_corr_heatmap(correlation_input),
    use_container_width=True,
)

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

st.download_button(
    "Download current filtered view as CSV",
    data=filtered_view_df.to_csv(index=False).encode("utf-8"),
    file_name="physical_metals_analysis_filtered_view.csv",
    mime="text/csv",
)
