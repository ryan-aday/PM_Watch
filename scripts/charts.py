from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def make_multi_product_price_chart(
    frame: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    show_silver_spot: bool = True,
    show_gold_spot: bool = True,
) -> go.Figure:
    figure = go.Figure()
    for product_key in sorted(frame["product_key"].dropna().unique()):
        product = frame[frame["product_key"] == product_key]
        if product.empty:
            continue
        axis = "y" if product["metal"].iloc[0] == "silver" else "y2"
        figure.add_trace(
            go.Scatter(
                x=product["date"],
                y=product["last_per_oz"],
                mode="lines",
                name=product["product_label"].iloc[0],
                yaxis=axis,
            )
        )

    if show_silver_spot and "spot_close_per_oz" in frame.columns:
        silver = frame[["date", "spot_close_per_oz"]].drop_duplicates().sort_values("date")
        figure.add_trace(
            go.Scatter(
                x=silver["date"],
                y=silver["spot_close_per_oz"],
                mode="lines",
                name="Silver spot proxy ($/oz)",
                yaxis="y",
            )
        )

    if show_gold_spot and "gold_close_per_oz" in frame.columns:
        gold = frame[["date", "gold_close_per_oz"]].drop_duplicates().sort_values("date")
        figure.add_trace(
            go.Scatter(
                x=gold["date"],
                y=gold["gold_close_per_oz"],
                mode="lines",
                name="Gold spot proxy ($/oz)",
                yaxis="y2",
            )
        )

    figure.update_layout(
        title="Monex Products vs Spot",
        xaxis_title="Date",
        yaxis=dict(title="Silver USD per oz"),
        yaxis2=dict(title="Gold USD per oz", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
        height=620,
        margin=dict(l=60, r=70, t=95, b=80),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            title=None,
        ),
    )
    figure.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return figure


def make_multi_product_difference_chart(
    frame: pd.DataFrame,
    mode: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> go.Figure:
    figure = go.Figure()
    for product_key in sorted(frame["product_key"].dropna().unique()):
        product = frame[frame["product_key"] == product_key]
        if product.empty:
            continue
        values = (
            product["product_minus_spot"]
            if mode == "Absolute difference ($/oz)"
            else product["product_pct_premium"]
        )
        figure.add_trace(
            go.Scatter(
                x=product["date"],
                y=values,
                mode="lines",
                name=product["product_label"].iloc[0],
            )
        )

    figure.update_layout(
        title="Monex Product Premium / Discount vs Spot",
        xaxis_title="Date",
        yaxis_title=(
            "Difference"
            if mode == "Absolute difference ($/oz)"
            else "Premium / Discount (%)"
        ),
        hovermode="x unified",
        height=520,
        margin=dict(l=60, r=30, t=95, b=80),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            title=None,
        ),
    )
    figure.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return figure


def make_macro_chart(
    frame: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> go.Figure:
    figure = go.Figure()
    series_map = (
        ("US 10Y yield (%)", "us_10y_yield"),
        ("JPN 10Y yield (%)", "jpn_10y_yield"),
        ("US CPI YoY (%)", "us_cpi_yoy_pct"),
        ("US unemployment (%)", "us_unemployment"),
        ("US real GDP growth SAAR (%)", "us_real_gdp_growth"),
    )
    for label, column in series_map:
        if column not in frame.columns:
            continue
        plot_frame = frame[["date", column]].dropna()
        if plot_frame.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=plot_frame["date"],
                y=plot_frame[column],
                mode="lines",
                name=label,
            )
        )

    figure.update_layout(
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
    figure.update_xaxes(range=[start_date, end_date], rangeslider_visible=True)
    return figure


def build_correlation_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    price_wide = frame.pivot_table(
        index="date",
        columns="product_label",
        values="last_per_oz",
        aggfunc="last",
    )
    spread_wide = frame.pivot_table(
        index="date",
        columns="product_label",
        values="product_minus_spot",
        aggfunc="last",
    )
    spread_wide.columns = [f"{column} minus spot" for column in spread_wide.columns]
    base_columns = (
        "spot_close_per_oz",
        "gold_close_per_oz",
        "us_10y_yield",
        "jpn_10y_yield",
        "us_cpi_yoy_pct",
        "us_unemployment",
        "us_real_gdp_growth",
    )
    available = [column for column in base_columns if column in frame.columns]
    base = frame[["date", *available]].drop_duplicates("date").set_index("date")
    return base.join(price_wide, how="outer").join(spread_wide, how="outer").sort_index()


def make_corr_heatmap(frame: pd.DataFrame) -> go.Figure:
    correlation = frame.corr(numeric_only=True)
    figure = go.Figure(
        data=go.Heatmap(
            z=correlation.values,
            x=correlation.columns,
            y=correlation.index,
            zmin=-1,
            zmax=1,
            colorbar=dict(title="Corr"),
            text=np.round(correlation.values, 2),
            texttemplate="%{text}",
            hovertemplate="X: %{x}<br>Y: %{y}<br>Corr: %{z:.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Dynamic Correlation Heatmap (selected timeframe)",
        height=650,
        margin=dict(l=80, r=30, t=60, b=120),
    )
    return figure
