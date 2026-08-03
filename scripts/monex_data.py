from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd
import requests
import streamlit as st

from scripts.app_config import MONEX_PRODUCTS


def validate_monex_payload(payload: object, expected_symbol: str) -> int:
    if not isinstance(payload, list) or not payload:
        raise ValueError("Monex response is not a non-empty list.")

    interval_count = 0
    response_symbols: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Monex response contains a non-object item.")
        symbol = item.get("symbol")
        if symbol:
            response_symbols.add(str(symbol).lower())
        intervals = item.get("intervals")
        if not isinstance(intervals, list):
            raise ValueError("Monex response item is missing an intervals list.")
        interval_count += len(intervals)

    if interval_count == 0:
        raise ValueError("Monex response contains no history intervals.")
    if response_symbols and expected_symbol.lower() not in response_symbols:
        raise ValueError(
            f"Monex response symbols {sorted(response_symbols)} do not match "
            f"expected symbol {expected_symbol.upper()}."
        )
    return interval_count


def refresh_monex_json_to_file(
    output_path: Path,
    symbol: str,
    referer_symbol: str,
    bearer_token: str,
    client_id: str,
    instance: str,
    cookie: str,
) -> tuple[bool, str]:
    url = "https://widget.nfusionsolutions.com/api/v1/Data/history"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Accept-Language": "en-US",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Authorization": f"Bearer {bearer_token}",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://widget.nfusionsolutions.com",
        "Referer": (
            "https://widget.nfusionsolutions.com/custom/monex/chart/1/"
            f"{client_id}/{instance}?symbols={referer_symbol}"
        ),
        "Cookie": cookie,
    }
    data = {
        "clientId": client_id,
        "instance": instance,
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
        payload = response.json()
        validate_monex_payload(payload, symbol)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
        return True, f"Refreshed {output_path.name}."
    except Exception as exc:
        return False, f"Refresh failed for {output_path.name}: {exc}"


@st.cache_data(show_spinner=False)
def load_monex_json_cached(
    json_path_str: str,
    product_key: str,
    mtime: float,
) -> pd.DataFrame:
    del mtime
    json_path = Path(json_path_str)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    meta = MONEX_PRODUCTS[product_key]
    validate_monex_payload(payload, str(meta["symbol"]))
    ounces_per_unit = float(meta["ounces_per_unit"])
    rows: list[dict[str, object]] = []

    for item in payload:
        for interval in item.get("intervals", []):
            timestamp = pd.to_datetime(
                interval.get("start"),
                utc=True,
                errors="coerce",
            )
            if pd.isna(timestamp):
                continue
            rows.append(
                {
                    "product_key": product_key,
                    "product_label": meta["label"],
                    "metal": meta["metal"],
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "date": timestamp.tz_convert(None).normalize(),
                    "open_price": interval.get("open"),
                    "high_price": interval.get("high"),
                    "low_price": interval.get("low"),
                    "last_price": interval.get("last"),
                    "change": interval.get("change"),
                    "changePercent": interval.get("changePercent"),
                    "ounces_per_unit": ounces_per_unit,
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"No interval rows found for product {product_key}.")

    frame = frame.sort_values("date").reset_index(drop=True)
    for column in ("open_price", "high_price", "low_price", "last_price"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["open_per_oz"] = frame["open_price"] / frame["ounces_per_unit"]
    frame["high_per_oz"] = frame["high_price"] / frame["ounces_per_unit"]
    frame["low_per_oz"] = frame["low_price"] / frame["ounces_per_unit"]
    frame["last_per_oz"] = frame["last_price"] / frame["ounces_per_unit"]
    return frame


def discover_monex_file_specs(
    products: Mapping[str, Mapping[str, object]] = MONEX_PRODUCTS,
) -> tuple[tuple[str, str, float], ...]:
    specs: list[tuple[str, str, float]] = []
    for product_key, meta in products.items():
        path = Path(str(meta["json_file"]))
        if path.exists():
            specs.append((product_key, str(path), path.stat().st_mtime))
    return tuple(specs)


@st.cache_data(show_spinner=False)
def build_monex_all_df(
    file_specs: tuple[tuple[str, str, float], ...],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for product_key, path_str, mtime in file_specs:
        try:
            frames.append(load_monex_json_cached(path_str, product_key, mtime))
        except Exception as exc:
            label = MONEX_PRODUCTS[product_key]["label"]
            errors.append(f"Failed to load {label}: {exc}")

    if not frames:
        raise ValueError("No Monex product JSON files could be loaded.")
    return pd.concat(frames, ignore_index=True), tuple(errors)


def clear_monex_caches() -> None:
    load_monex_json_cached.clear()
    build_monex_all_df.clear()


def reload_local_monex_files() -> tuple[list[str], list[str]]:
    available: list[str] = []
    missing: list[str] = []
    for meta in MONEX_PRODUCTS.values():
        path = Path(str(meta["json_file"]))
        (available if path.exists() else missing).append(path.name)
    clear_monex_caches()
    return available, missing


def refresh_products_with_manual_tokens(
    token_inputs: Mapping[str, str],
    client_id: str,
    instance: str,
    cookie: str,
) -> list[str]:
    messages: list[str] = []
    for product_key, meta in MONEX_PRODUCTS.items():
        token = token_inputs.get(product_key, "").strip()
        if not token:
            messages.append(
                f"Skipped {meta['label']} because no token was provided; "
                "the local JSON file remains in use."
            )
            continue

        success, message = refresh_monex_json_to_file(
            output_path=Path(str(meta["json_file"])),
            symbol=str(meta["symbol"]),
            referer_symbol=str(meta["referer_symbol"]),
            bearer_token=token,
            client_id=client_id,
            instance=instance,
            cookie=cookie,
        )
        messages.append(message)
        if not success:
            messages.append(
                f"Using the previous local JSON for {meta['label']} if available."
            )

    clear_monex_caches()
    return messages


def attach_spot_and_spreads(
    monex_df: pd.DataFrame,
    spot_df: pd.DataFrame,
) -> pd.DataFrame:
    frame = (
        monex_df.merge(spot_df, on="date", how="inner")
        .sort_values(["product_key", "date"])
        .reset_index(drop=True)
    )
    frame["reference_spot_per_oz"] = pd.NA
    silver_mask = frame["metal"] == "silver"
    gold_mask = frame["metal"] == "gold"
    frame.loc[silver_mask, "reference_spot_per_oz"] = frame.loc[
        silver_mask, "spot_close_per_oz"
    ]
    frame.loc[gold_mask, "reference_spot_per_oz"] = frame.loc[
        gold_mask, "gold_close_per_oz"
    ]
    frame["reference_spot_per_oz"] = pd.to_numeric(
        frame["reference_spot_per_oz"],
        errors="coerce",
    )
    frame["product_minus_spot"] = (
        frame["last_per_oz"] - frame["reference_spot_per_oz"]
    )
    frame["product_pct_premium"] = (
        frame["last_per_oz"] / frame["reference_spot_per_oz"] - 1.0
    ) * 100.0
    return frame
