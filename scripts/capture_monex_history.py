#!/usr/bin/env python3
"""Capture initial Monex/nFusion history JSON files for PM_Watch.

Preferred workflow:
  1. Open any Monex widget page and copy the Network request named ``history``
     as cURL.
  2. Save the copied command to a temporary text file.
  3. Run this script with ``--curl-file``. The script reuses the captured
     request metadata and downloads the configured PM_Watch products.

Token-only mode is also supported for compatibility with the instructions in
``metals_spot_w_corr_app.py``. Bearer tokens and cookies are used only in
memory; they are never written to disk or printed.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shlex
import sys
import tempfile
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import parse_qsl

import requests

HISTORY_URL = "https://widget.nfusionsolutions.com/api/v1/Data/history"
CLIENT_ID = "a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5"
INSTANCE_ID = "59155a1a-4c2d-44c1-9ae2-1b083713b0d5"
WIDGET_BASE_URL = (
    "https://widget.nfusionsolutions.com/custom/monex/chart/1/"
    f"{CLIENT_ID}/{INSTANCE_ID}"
)


@dataclass(frozen=True)
class Product:
    key: str
    label: str
    request_symbol: str
    referer_symbol: str
    output_file: str
    page_url: str

    @property
    def widget_url(self) -> str:
        return f"{WIDGET_BASE_URL}?symbols={self.referer_symbol}"


PRODUCTS: Tuple[Product, ...] = (
    Product(
        key="junk_90_silver",
        label="90% Silver U.S. Coin Bag",
        request_symbol="sc",
        referer_symbol="SC",
        output_file="history_90_percent_silver.json",
        page_url="https://www.monex.com/90-us-silver-coin-bag-price-charts/",
    ),
    Product(
        key="silver_eagles",
        label="Silver American Eagles",
        request_symbol="saei",
        referer_symbol="SAEI",
        output_file="history_silver_eagles.json",
        page_url="https://www.monex.com/silver-american-eagle-price-charts/",
    ),
    Product(
        key="gold_eagles",
        label="Gold American Eagles",
        request_symbol="ae",
        referer_symbol="AE",
        output_file="history_gold_eagles.json",
        page_url="https://www.monex.com/gold-american-eagle-price-charts/",
    ),
    Product(
        key="silver_1000oz",
        label="1000 oz Silver Bullion",
        request_symbol="sbi1000",
        referer_symbol="SBI1000",
        output_file="history_1000oz_silver.json",
        page_url="https://www.monex.com/1000-oz-silver-bullion-price-charts/",
    ),
    Product(
        key="gold_1kg",
        label="1 Kilo Gold Bullion Bar",
        request_symbol="gbx1k",
        referer_symbol="GBX1K",
        output_file="history_1kg_gold.json",
        page_url="https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/",
    ),
    Product(
        key="gold_10oz",
        label="10 oz Gold Bullion Bar",
        request_symbol="gbx10",
        referer_symbol="GBX10",
        output_file="history_10oz_gold.json",
        page_url="https://www.monex.com/10-oz-gold-bullion-bar-price-charts/",
    ),
    Product(
        key="silver_10oz",
        label="10 oz Silver Bullion Bar",
        request_symbol="sbx",
        referer_symbol="SBX",
        output_file="history_10oz_silver.json",
        page_url="https://www.monex.com/10-oz-silver-bullion-price-charts/",
    ),
)
PRODUCT_BY_KEY = {product.key: product for product in PRODUCTS}

DROP_WHEN_REPLAYING = {
    "content-length",
    "host",
    "connection",
    "accept-encoding",
}


@dataclass
class CurlRequest:
    url: str
    headers: Dict[str, str]
    data: Dict[str, str]


def _strip_line_continuations(command: str) -> str:
    """Normalize browser-generated cURL commands from bash, cmd, or PowerShell."""
    normalized = command.replace("\r\n", "\n")
    normalized = re.sub(r"(?:\\|\^|`)\s*\n\s*", " ", normalized)
    return " ".join(line.strip() for line in normalized.splitlines() if line.strip())


def _split_curl(command: str) -> List[str]:
    normalized = _strip_line_continuations(command)
    if not normalized:
        raise ValueError("The copied cURL command is empty.")

    try:
        return shlex.split(normalized, posix=True)
    except ValueError as exc:
        raise ValueError(f"Could not parse the copied cURL command: {exc}") from exc


def parse_curl(command: str) -> CurlRequest:
    """Parse the subset of cURL syntax emitted by browser Developer Tools."""
    tokens = _split_curl(command)
    if not tokens or Path(tokens[0]).name.lower() not in {"curl", "curl.exe"}:
        raise ValueError("Input does not begin with curl or curl.exe.")

    url: Optional[str] = None
    headers: Dict[str, str] = {}
    data_chunks: List[str] = []

    i = 1
    while i < len(tokens):
        token = tokens[i]

        if token in {"-H", "--header"}:
            i += 1
            if i >= len(tokens):
                raise ValueError(f"Missing header value after {token}.")
            raw_header = tokens[i]
            if ":" not in raw_header:
                raise ValueError(f"Malformed cURL header: {raw_header!r}")
            name, value = raw_header.split(":", 1)
            headers[name.strip()] = value.strip()
        elif token in {"-d", "--data", "--data-raw", "--data-binary", "--data-ascii"}:
            i += 1
            if i >= len(tokens):
                raise ValueError(f"Missing request body after {token}.")
            data_chunks.append(tokens[i])
        elif token == "--data-urlencode":
            i += 1
            if i >= len(tokens):
                raise ValueError("Missing request body after --data-urlencode.")
            data_chunks.append(tokens[i])
        elif token == "--url":
            i += 1
            if i >= len(tokens):
                raise ValueError("Missing URL after --url.")
            url = tokens[i]
        elif token.startswith(("http://", "https://")) and url is None:
            url = token
        elif token in {"-X", "--request", "-A", "--user-agent", "-e", "--referer"}:
            i += 1
            if i >= len(tokens):
                raise ValueError(f"Missing value after {token}.")
            if token in {"-A", "--user-agent"}:
                headers["User-Agent"] = tokens[i]
            elif token in {"-e", "--referer"}:
                headers["Referer"] = tokens[i]
        elif token.startswith("-"):
            pass
        i += 1

    if not url:
        raise ValueError("No URL was found in the copied cURL command.")
    if "/api/v1/Data/history" not in url:
        raise ValueError(
            "The copied request is not the nFusion history request. "
            "In Developer Tools, copy the request named 'history'."
        )

    body = "&".join(chunk.lstrip("@") for chunk in data_chunks if chunk)
    data = dict(parse_qsl(body, keep_blank_values=True)) if body else {}

    if not _find_header(headers, "Authorization"):
        raise ValueError("The copied cURL command does not contain an Authorization header.")

    return CurlRequest(url=url, headers=headers, data=data)


def _find_header(headers: Mapping[str, str], target: str) -> Optional[str]:
    target_lower = target.lower()
    for name, value in headers.items():
        if name.lower() == target_lower:
            return value
    return None


def extract_bearer_token(value: str) -> str:
    """Accept a bare token, a Bearer value, an Authorization line, or full cURL."""
    raw = value.strip()
    if not raw:
        raise ValueError("Bearer token is empty.")

    if raw.lower().startswith(("curl ", "curl.exe ")):
        auth = _find_header(parse_curl(raw).headers, "Authorization")
        if auth is None:
            raise ValueError("No Authorization header found in cURL command.")
        raw = auth

    match = re.search(r"(?i)(?:authorization\s*:\s*)?bearer\s+(.+)$", raw)
    token = match.group(1).strip() if match else raw
    token = token.strip("'\"")
    if not token or any(character.isspace() for character in token):
        raise ValueError("Bearer token contains whitespace or is malformed.")
    return token


def default_request(bearer_token: str, cookie: Optional[str], timeframe_type: str) -> CurlRequest:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Authorization": f"Bearer {extract_bearer_token(bearer_token)}",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://widget.nfusionsolutions.com",
    }
    if cookie:
        headers["Cookie"] = cookie.strip()

    data = {
        "clientId": CLIENT_ID,
        "instance": INSTANCE_ID,
        "customId": "monex",
        "widgetVersion": "1",
        "widgetType": "chart",
        "currency": "USD",
        "unitOfMeasure": "toz",
        "timeframeType": timeframe_type,
    }
    return CurlRequest(url=HISTORY_URL, headers=headers, data=data)


def request_for_product(template: CurlRequest, product: Product, timeframe_type: Optional[str]) -> CurlRequest:
    headers: Dict[str, str] = {}
    for name, value in template.headers.items():
        if name.lower() not in DROP_WHEN_REPLAYING:
            headers[name] = value

    headers["Referer"] = product.widget_url
    headers.setdefault("Origin", "https://widget.nfusionsolutions.com")
    headers.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    headers.setdefault("X-Requested-With", "XMLHttpRequest")

    data = dict(template.data)
    data.setdefault("clientId", CLIENT_ID)
    data.setdefault("instance", INSTANCE_ID)
    data.setdefault("customId", "monex")
    data.setdefault("widgetVersion", "1")
    data.setdefault("widgetType", "chart")
    data.setdefault("currency", "USD")
    data.setdefault("unitOfMeasure", "toz")
    data["symbols"] = product.request_symbol
    if timeframe_type:
        data["timeframeType"] = timeframe_type
    else:
        data.setdefault("timeframeType", "year")

    return CurlRequest(url=template.url or HISTORY_URL, headers=headers, data=data)


def validate_history(payload: object, product: Product) -> int:
    if not isinstance(payload, list) or not payload:
        raise ValueError("Response JSON is not a non-empty list.")

    interval_count = 0
    response_symbols = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Response JSON contains a non-object item.")
        symbol = item.get("symbol")
        if symbol:
            response_symbols.add(str(symbol).lower())
        intervals = item.get("intervals")
        if not isinstance(intervals, list):
            raise ValueError("Response item is missing an intervals list.")
        interval_count += len(intervals)

    if interval_count == 0:
        raise ValueError("Response contains no history intervals.")

    expected_symbols = {product.request_symbol.lower(), product.referer_symbol.lower()}
    if response_symbols and response_symbols.isdisjoint(expected_symbols):
        raise ValueError(
            f"Response symbols {sorted(response_symbols)} do not match "
            f"the requested product symbol {product.referer_symbol}."
        )
    return interval_count


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def fetch_product(
    session: requests.Session,
    template: CurlRequest,
    product: Product,
    output_dir: Path,
    timeout: float,
    timeframe_type: Optional[str],
) -> Tuple[Path, int]:
    request = request_for_product(template, product, timeframe_type)
    response = session.post(
        request.url,
        headers=request.headers,
        data=request.data,
        timeout=timeout,
    )

    if response.status_code in {401, 403}:
        cookie_present = bool(_find_header(request.headers, "Cookie"))
        hint = (
            "The copied credentials were rejected. Capture a fresh history request."
            if cookie_present
            else "The token was rejected. Use --curl-file so the request cookie is included."
        )
        raise RuntimeError(f"HTTP {response.status_code}. {hint}")

    response.raise_for_status()
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        preview = response.text[:120].replace("\n", " ")
        raise ValueError(f"Response was not JSON (preview: {preview!r}).") from exc

    interval_count = validate_history(payload, product)
    output_path = output_dir / product.output_file
    atomic_write_json(output_path, payload)
    return output_path, interval_count


def choose_products(keys: Sequence[str]) -> List[Product]:
    if not keys or "all" in keys:
        return list(PRODUCTS)
    seen = set()
    selected: List[Product] = []
    for key in keys:
        if key not in PRODUCT_BY_KEY:
            raise ValueError(f"Unknown product key: {key}")
        if key not in seen:
            selected.append(PRODUCT_BY_KEY[key])
            seen.add(key)
    return selected


def _read_curl_file(path: Path) -> CurlRequest:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"Could not read cURL file {path}: {exc}") from exc
    return parse_curl(text)


def build_parser() -> argparse.ArgumentParser:
    product_choices = [product.key for product in PRODUCTS] + ["all"]
    parser = argparse.ArgumentParser(
        description="Capture validated Monex history JSON files for PM_Watch.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    credential_group = parser.add_mutually_exclusive_group()
    credential_group.add_argument(
        "--curl-file",
        type=Path,
        help="Text file containing the copied browser cURL request named 'history'.",
    )
    credential_group.add_argument(
        "--bearer-token",
        help=(
            "Bearer token. Prefer interactive entry or MONEX_BEARER_TOKEN because "
            "command-line arguments may be visible to other local processes."
        ),
    )
    parser.add_argument(
        "--cookie",
        help="Optional Cookie header for token-only mode; may also use MONEX_COOKIE.",
    )
    parser.add_argument(
        "--product",
        action="append",
        choices=product_choices,
        default=[],
        help="Product key to capture; repeat for multiple products, or use all.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where PM_Watch history_*.json files are written.",
    )
    parser.add_argument(
        "--timeframe-type",
        default=None,
        help=(
            "Override timeframeType. When omitted, full-cURL mode preserves the "
            "captured value and token-only mode uses year."
        ),
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--open-pages",
        action="store_true",
        help="Open the selected Monex widget pages before requesting credentials.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between product requests in seconds.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        products = choose_products(args.product)
        if args.open_pages:
            for product in products:
                webbrowser.open_new_tab(product.widget_url)

        if args.curl_file:
            template = _read_curl_file(args.curl_file)
            source_description = f"copied cURL in {args.curl_file}"
        else:
            bearer_value = args.bearer_token or os.environ.get("MONEX_BEARER_TOKEN")
            if not bearer_value:
                bearer_value = getpass.getpass("Paste the value after 'Authorization: Bearer': ")
            cookie = args.cookie or os.environ.get("MONEX_COOKIE")
            template = default_request(
                bearer_token=bearer_value,
                cookie=cookie,
                timeframe_type=args.timeframe_type or "year",
            )
            source_description = "bearer token input"

        extract_bearer_token(_find_header(template.headers, "Authorization") or "")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    print(f"Credential source: {source_description}")
    print(f"Output directory: {args.output_dir.resolve()}")
    print("Sensitive request headers will not be displayed or saved.\n")

    failures: List[Tuple[str, str]] = []
    with requests.Session() as session:
        for index, product in enumerate(products):
            try:
                output_path, intervals = fetch_product(
                    session=session,
                    template=template,
                    product=product,
                    output_dir=args.output_dir,
                    timeout=args.timeout,
                    timeframe_type=args.timeframe_type,
                )
                print(f"[OK] {product.label}: {intervals} intervals -> {output_path}")
            except (requests.RequestException, RuntimeError, ValueError, OSError) as exc:
                failures.append((product.label, str(exc)))
                print(f"[FAILED] {product.label}: {exc}", file=sys.stderr)

            if index < len(products) - 1 and args.delay > 0:
                time.sleep(args.delay)

    if failures:
        print("\nCapture completed with failures:", file=sys.stderr)
        for label, message in failures:
            print(f"  - {label}: {message}", file=sys.stderr)
        print(
            "\nCapture a fresh cURL request for an affected product and rerun with "
            "--product <key> if one captured credential does not authorize every symbol.",
            file=sys.stderr,
        )
        return 1

    print("\nAll requested Monex history files were captured successfully.")
    if args.curl_file:
        print("Delete the temporary cURL text file because it contains live credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
