#!/usr/bin/env python3
"""Automatically capture Monex history requests and response JSON.

The helper opens each Monex product page in a real Chromium-family browser,
waits for that page's POST to the nFusion ``Data/history`` endpoint, and saves:

* an executable PowerShell cURL command containing the exact request; and
* the validated JSON response used by PM_Watch.

No Developer Tools interaction or bearer-token copying is required.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shlex
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlsplit

HISTORY_PATH = "/api/v1/data/history"
CLIENT_ID = "a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5"
FALLBACK_INSTANCE_ID = "59155a1a-4c2d-44c1-9ae2-1b083713b0d5"
FALLBACK_WIDGET_BASE = (
    "https://widget.nfusionsolutions.com/custom/monex/chart/1/"
    f"{CLIENT_ID}/{FALLBACK_INSTANCE_ID}"
)

# curl calculates these itself. Keeping a captured value can make an otherwise
# valid replay fail when the body is edited or the HTTP protocol changes.
CURL_EXCLUDED_HEADERS = {
    "accept-encoding",
    "connection",
    "content-length",
    "host",
}


@dataclass(frozen=True)
class Product:
    key: str
    label: str
    request_symbol: str
    output_file: str
    page_url: str

    @property
    def fallback_widget_url(self) -> str:
        return f"{FALLBACK_WIDGET_BASE}?symbols={self.request_symbol.upper()}"


PRODUCTS: Tuple[Product, ...] = (
    Product(
        key="junk_90_silver",
        label="90% Silver U.S. Coin Bag",
        request_symbol="sc",
        output_file="history_90_percent_silver.json",
        page_url="https://www.monex.com/90-us-silver-coin-bag-price-charts/",
    ),
    Product(
        key="silver_eagles",
        label="Silver American Eagles",
        request_symbol="saei",
        output_file="history_silver_eagles.json",
        page_url="https://www.monex.com/silver-american-eagle-price-charts/",
    ),
    Product(
        key="gold_eagles",
        label="Gold American Eagles",
        request_symbol="ae",
        output_file="history_gold_eagles.json",
        page_url="https://www.monex.com/gold-american-eagle-price-charts/",
    ),
    Product(
        key="silver_1000oz",
        label="1000 oz Silver Bullion",
        request_symbol="sbi1000",
        output_file="history_1000oz_silver.json",
        page_url="https://www.monex.com/1000-oz-silver-bullion-price-charts/",
    ),
    Product(
        key="gold_1kg",
        label="1 Kilo Gold Bullion Bar",
        request_symbol="gbx1k",
        output_file="history_1kg_gold.json",
        page_url="https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/",
    ),
    Product(
        key="gold_10oz",
        label="10 oz Gold Bullion Bar",
        request_symbol="gbx10",
        output_file="history_10oz_gold.json",
        page_url="https://www.monex.com/10-oz-gold-bullion-bar-price-charts/",
    ),
    Product(
        key="silver_10oz",
        label="10 oz Silver Bullion Bar",
        request_symbol="sbx",
        output_file="history_10oz_silver.json",
        page_url="https://www.monex.com/10-oz-silver-bullion-price-charts/",
    ),
)
PRODUCT_BY_KEY = {product.key: product for product in PRODUCTS}


@dataclass(frozen=True)
class CapturedRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    post_data: str
    response_status: int
    payload: object
    source_url: str


class CaptureError(RuntimeError):
    """Raised when a page does not produce a usable history response."""


def choose_products(keys: Sequence[str]) -> List[Product]:
    if not keys or "all" in keys:
        return list(PRODUCTS)

    selected: List[Product] = []
    seen = set()
    for key in keys:
        if key not in PRODUCT_BY_KEY:
            raise ValueError(f"Unknown product key: {key}")
        if key not in seen:
            selected.append(PRODUCT_BY_KEY[key])
            seen.add(key)
    return selected


def request_form(post_data: Optional[str]) -> Dict[str, List[str]]:
    if not post_data:
        return {}
    return parse_qs(post_data, keep_blank_values=True)


def request_symbols(post_data: Optional[str]) -> set[str]:
    values = request_form(post_data).get("symbols", [])
    symbols: set[str] = set()
    for value in values:
        for symbol in value.split(","):
            normalized = symbol.strip().lower()
            if normalized:
                symbols.add(normalized)
    return symbols


def is_history_request(request: Any, product: Product) -> bool:
    """Return whether a Playwright Request is the target history POST."""
    try:
        path = urlsplit(request.url).path.lower()
        method = request.method.upper()
        post_data = request.post_data
    except (AttributeError, TypeError):
        return False

    return (
        method == "POST"
        and path.endswith(HISTORY_PATH)
        and product.request_symbol.lower() in request_symbols(post_data)
    )


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

    if response_symbols and product.request_symbol.lower() not in response_symbols:
        raise ValueError(
            f"Response symbols {sorted(response_symbols)} do not match "
            f"the requested product symbol {product.request_symbol.upper()}."
        )
    return interval_count


def atomic_write_text(path: Path, content: str, sensitive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if sensitive and os.name != "nt":
            temp_path.chmod(0o600)
        temp_path.replace(path)
        if sensitive and os.name != "nt":
            path.chmod(0o600)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: object, sensitive: bool = False) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        sensitive=sensitive,
    )


def _filtered_headers(headers: Mapping[str, str]) -> List[Tuple[str, str]]:
    return [
        (str(name), str(value))
        for name, value in headers.items()
        if str(name).lower() not in CURL_EXCLUDED_HEADERS
    ]


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def format_curl_powershell(
    method: str,
    url: str,
    headers: Mapping[str, str],
    post_data: str,
) -> str:
    """Build a PowerShell-compatible curl.exe command."""
    arguments = [f"curl.exe {_powershell_quote(url)}"]
    if method.upper() != "GET":
        arguments.append(f"-X {_powershell_quote(method.upper())}")
    for name, value in _filtered_headers(headers):
        arguments.append(f"-H {_powershell_quote(f'{name}: {value}')}")
    if post_data:
        arguments.append(f"--data-raw {_powershell_quote(post_data)}")
    return " `\n  ".join(arguments) + "\n"


def format_curl_bash(
    method: str,
    url: str,
    headers: Mapping[str, str],
    post_data: str,
) -> str:
    """Build a POSIX-shell-compatible curl command."""
    arguments = ["curl", shlex.quote(url)]
    if method.upper() != "GET":
        arguments.extend(["-X", shlex.quote(method.upper())])
    for name, value in _filtered_headers(headers):
        arguments.extend(["-H", shlex.quote(f"{name}: {value}")])
    if post_data:
        arguments.extend(["--data-raw", shlex.quote(post_data)])
    return " \\\n  ".join(arguments) + "\n"


def source_urls(product: Product, source: str) -> List[str]:
    if source == "product":
        return [product.page_url]
    if source == "widget":
        return [product.fallback_widget_url]
    if source == "auto":
        return [product.page_url, product.fallback_widget_url]
    raise ValueError(f"Unknown source mode: {source}")


def _auto_scroll(page: Any) -> None:
    """Trigger lazy-loaded charts on the full Monex product page."""
    for fraction in (0.20, 0.45, 0.70, 0.92, 1.0):
        try:
            page.evaluate(
                "fraction => window.scrollTo(0, "
                "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) "
                "* fraction)",
                fraction,
            )
            page.wait_for_timeout(350)
        except Exception:
            return


def extract_widget_urls_from_html(page_html: str, product: Product) -> List[str]:
    """Find the page's current nFusion chart instance and make it navigable."""
    decoded = html.unescape(page_html)
    candidates = re.findall(
        r"https://widget\.nfusionsolutions\.com/custom/monex/"
        r"(?:script/)?chart/1/[^\s\"'<>]+",
        decoded,
        flags=re.IGNORECASE,
    )

    results: List[str] = []
    for candidate in candidates:
        navigable = candidate.replace("/script/chart/", "/chart/")
        query = parse_qs(urlsplit(navigable).query)
        symbols = {
            symbol.strip().lower()
            for value in query.get("symbols", [])
            for symbol in value.split(",")
            if symbol.strip()
        }
        if symbols and product.request_symbol.lower() not in symbols:
            continue
        if navigable not in results:
            results.append(navigable)
    return results


def capture_from_page(
    context: Any,
    product: Product,
    source_url: str,
    request_timeout: float,
    navigation_timeout: float,
) -> CapturedRequest:
    page = context.new_page()
    responses: List[Any] = []

    def handle_response(response: Any) -> None:
        if not responses and is_history_request(response.request, product):
            responses.append(response)

    def wait_for_response(timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        while not responses and time.monotonic() < deadline:
            page.wait_for_timeout(200)

    page.on("response", handle_response)
    effective_source_url = source_url
    navigation_error: Optional[Exception] = None
    try:
        try:
            page.goto(
                source_url,
                wait_until="domcontentloaded",
                timeout=int(navigation_timeout * 1000),
            )
        except Exception as exc:
            # Monex pages can remain busy because of ads/analytics even after the
            # chart has loaded. Preserve a captured request instead of treating a
            # navigation timeout as an automatic failure.
            navigation_error = exc

        if source_url == product.page_url:
            _auto_scroll(page)

        wait_for_response(request_timeout)

        # Some Monex pages expose the chart through a lazy inline script. If the
        # page never executed it, extract that page's current widget instance and
        # navigate to the exact instance rather than relying on a hard-coded one.
        if not responses and source_url == product.page_url:
            try:
                discovered_urls = extract_widget_urls_from_html(page.content(), product)
            except Exception:
                discovered_urls = []
            for discovered_url in discovered_urls:
                effective_source_url = discovered_url
                try:
                    page.goto(
                        discovered_url,
                        wait_until="domcontentloaded",
                        timeout=int(navigation_timeout * 1000),
                    )
                except Exception as exc:
                    navigation_error = exc
                wait_for_response(request_timeout)
                if responses:
                    break

        if not responses:
            detail = f" Last navigation error: {navigation_error}" if navigation_error else ""
            raise CaptureError(
                f"No matching Data/history request appeared within {request_timeout:g} seconds."
                f"{detail}"
            )

        response = responses[0]
        request = response.request
        headers = request.all_headers()
        post_data = request.post_data or ""
        status = int(response.status)

        if status < 200 or status >= 300:
            raise CaptureError(f"The captured history request returned HTTP {status}.")

        try:
            payload = response.json()
        except Exception as exc:
            raise CaptureError("The captured history response was not valid JSON.") from exc

        validate_history(payload, product)
        return CapturedRequest(
            method=request.method,
            url=request.url,
            headers=dict(headers),
            post_data=post_data,
            response_status=status,
            payload=payload,
            source_url=effective_source_url,
        )
    finally:
        try:
            page.remove_listener("response", handle_response)
        except Exception:
            pass
        try:
            page.close()
        except Exception:
            pass


def save_capture(
    captured: CapturedRequest,
    product: Product,
    capture_dir: Path,
    output_dir: Path,
    save_json: bool,
) -> Tuple[Path, Path, Optional[Path], int]:
    interval_count = validate_history(captured.payload, product)
    capture_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        capture_dir.chmod(0o700)

    powershell_path = capture_dir / f"{product.key}.curl.ps1"
    bash_path = capture_dir / f"{product.key}.curl.sh"
    atomic_write_text(
        powershell_path,
        format_curl_powershell(
            captured.method,
            captured.url,
            captured.headers,
            captured.post_data,
        ),
        sensitive=True,
    )
    atomic_write_text(
        bash_path,
        format_curl_bash(
            captured.method,
            captured.url,
            captured.headers,
            captured.post_data,
        ),
        sensitive=True,
    )

    json_path: Optional[Path] = None
    if save_json:
        json_path = output_dir / product.output_file
        atomic_write_json(json_path, captured.payload)

    return powershell_path, bash_path, json_path, interval_count


def _browser_launch_settings(browser: str) -> Tuple[str, Optional[str]]:
    if browser == "chromium":
        return "chromium", None
    if browser == "chrome":
        return "chromium", "chrome"
    if browser == "msedge":
        return "chromium", "msedge"
    raise ValueError(f"Unsupported browser: {browser}")


def build_parser() -> argparse.ArgumentParser:
    choices = [product.key for product in PRODUCTS] + ["all"]
    parser = argparse.ArgumentParser(
        description=(
            "Open Monex pages, capture each page's nFusion Data/history request "
            "as cURL, and save the returned PM_Watch JSON."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--product",
        action="append",
        choices=choices,
        default=[],
        help="Product key to capture; repeat for multiple products or use all.",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "product", "widget"],
        default="auto",
        help=(
            "Page source. auto tries the public Monex product page first and the "
            "direct nFusion widget as a fallback."
        ),
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "chrome", "msedge"],
        default="chromium",
        help="Browser engine/channel used for capture.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a visible browser window. Headed mode is more resilient.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for history_*.json files.",
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path(".monex_captures"),
        help="Directory for credential-bearing cURL files.",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=Path(".monex_browser_profile"),
        help="Persistent browser profile used for cookies and any browser challenge.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for a matching history request after navigation.",
    )
    parser.add_argument(
        "--navigation-timeout",
        type=float,
        default=60.0,
        help="Seconds allowed for each page navigation.",
    )
    parser.add_argument(
        "--slow-mo",
        type=float,
        default=0.0,
        help="Milliseconds of delay between Playwright browser operations.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Capture cURL files only; do not replace history_*.json files.",
    )
    parser.add_argument(
    "--executable-path",
    type=Path,
    default=None,
    help="Explicit Chromium executable, such as /usr/bin/chromium.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        products = choose_products(args.product)
        browser_type_name, channel = _browser_launch_settings(args.browser)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run:\n"
            "  python -m pip install -r scripts/requirements.txt\n"
            "  python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.capture_dir.mkdir(parents=True, exist_ok=True)
    args.profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Capturing {len(products)} Monex product page(s).")
    print(f"cURL output: {args.capture_dir.resolve()}")
    if not args.no_json:
        print(f"JSON output: {args.output_dir.resolve()}")
    print(
        "The cURL files contain temporary Authorization/Cookie values. "
        "They are gitignored and should not be shared."
    )
    if not args.headless:
        print(
            "A browser window will open. No Developer Tools work is needed; "
            "if a browser challenge appears, complete it and leave the window open."
        )

    failures: List[Tuple[str, str]] = []
    manifest: List[Dict[str, object]] = []

    try:
        with sync_playwright() as playwright:
            browser_type = getattr(playwright, browser_type_name)
            launch_options: Dict[str, object] = {
                "headless": bool(args.headless),
                "slow_mo": float(args.slow_mo),
                "viewport": {"width": 1440, "height": 1000},
            }
            if channel:
                launch_options["channel"] = channel

            if args.executable_path:
                executable = args.executable_path.expanduser().resolve()

                if not executable.exists():
                    raise RuntimeError(
                        f"Chromium executable does not exist: {executable}"
                    )

                launch_options["executable_path"] = str(executable)

            context = browser_type.launch_persistent_context(
                user_data_dir=str(args.profile_dir.resolve()),
                **launch_options,
            )
            try:
                for product in products:
                    print(f"\n[{product.label}]")
                    product_errors: List[str] = []
                    captured: Optional[CapturedRequest] = None

                    for source_url in source_urls(product, args.source):
                        source_name = (
                            "Monex product page"
                            if source_url == product.page_url
                            else "direct nFusion widget"
                        )
                        print(f"  Trying {source_name}...")
                        try:
                            captured = capture_from_page(
                                context=context,
                                product=product,
                                source_url=source_url,
                                request_timeout=args.request_timeout,
                                navigation_timeout=args.navigation_timeout,
                            )
                            break
                        except (CaptureError, PlaywrightError, ValueError) as exc:
                            product_errors.append(f"{source_name}: {exc}")
                            print(f"  {source_name} did not yield a usable capture: {exc}")

                    if captured is None:
                        message = " | ".join(product_errors) or "No capture source succeeded."
                        failures.append((product.label, message))
                        continue

                    try:
                        ps_path, sh_path, json_path, interval_count = save_capture(
                            captured=captured,
                            product=product,
                            capture_dir=args.capture_dir,
                            output_dir=args.output_dir,
                            save_json=not args.no_json,
                        )
                    except (OSError, ValueError) as exc:
                        failures.append((product.label, str(exc)))
                        continue

                    form = request_form(captured.post_data)
                    timeframe = (form.get("timeframeType") or [None])[0]
                    manifest.append(
                        {
                            "product_key": product.key,
                            "label": product.label,
                            "source_url": captured.source_url,
                            "request_url": captured.url,
                            "response_status": captured.response_status,
                            "request_symbol": product.request_symbol,
                            "timeframe_type": timeframe,
                            "interval_count": interval_count,
                            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                            "powershell_curl": str(ps_path),
                            "bash_curl": str(sh_path),
                            "json_file": str(json_path) if json_path else None,
                        }
                    )
                    print(f"  Captured {interval_count} intervals.")
                    print(f"  PowerShell cURL: {ps_path}")
                    print(f"  Bash cURL: {sh_path}")
                    if json_path:
                        print(f"  JSON: {json_path}")
            finally:
                context.close()
    except PlaywrightError as exc:
        print(f"Browser launch/capture failed: {exc}", file=sys.stderr)
        print(
            "If Chromium is missing, run: python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    manifest_path = args.capture_dir / "manifest.json"
    atomic_write_json(manifest_path, manifest)

    if failures:
        print("\nCapture completed with failures:", file=sys.stderr)
        for label, message in failures:
            print(f"  - {label}: {message}", file=sys.stderr)
        return 1

    print("\nAll requested page-specific cURLs were captured successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
