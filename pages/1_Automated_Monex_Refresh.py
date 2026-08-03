from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st


APP_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = APP_ROOT / "scripts" / "capture_monex_history.py"
CAPTURE_DIR = APP_ROOT / ".monex_captures"
PROFILE_DIR = APP_ROOT / ".monex_browser_profile"
MAX_RUNTIME_SECONDS = 30 * 60


@st.cache_data(ttl=60, show_spinner=False)
def check_playwright_chromium() -> Tuple[bool, str]:
    """Check both the Python package and the installed Chromium executable."""
    if importlib.util.find_spec("playwright") is None:
        return (
            False,
            "Playwright is not installed in this Python environment. Run "
            "`python -m pip install -r requirements.txt`.",
        )

    probe = (
        "from pathlib import Path; "
        "from playwright.sync_api import sync_playwright; "
        "p = sync_playwright().start(); "
        "path = Path(p.chromium.executable_path); "
        "p.stop(); "
        "raise SystemExit(0 if path.exists() else 1)"
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=APP_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not check the Playwright Chromium installation: {exc}"

    if result.returncode != 0:
        return (
            False,
            "The Playwright package is installed, but its Chromium browser is not. "
            "Run `python -m playwright install chromium`.",
        )

    return True, "Playwright and its Chromium browser are available."


def build_capture_command(headless: bool) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(HELPER_PATH),
        "--product",
        "all",
        "--browser",
        "chromium",
        "--output-dir",
        str(APP_ROOT),
        "--capture-dir",
        str(CAPTURE_DIR),
        "--profile-dir",
        str(PROFILE_DIR),
    ]
    if headless:
        command.append("--headless")
    return command


def combine_process_output(
    stdout: Optional[str],
    stderr: Optional[str],
    limit: int = 24_000,
) -> str:
    sections = []
    if stdout:
        sections.append(stdout.strip())
    if stderr:
        sections.append(stderr.strip())
    output = "\n\n".join(section for section in sections if section)
    if len(output) > limit:
        output = "[Earlier output omitted]\n" + output[-limit:]
    return output or "The helper produced no console output."


st.set_page_config(page_title="Automated Monex Refresh", layout="wide")
st.title("Automated Monex history refresh")
st.caption(
    "This page runs the Playwright helper that opens each Monex product page, "
    "captures its authenticated history request, and refreshes the seven local JSON files."
)

st.warning(
    "The full seven-product refresh is intentionally slow and may take several minutes "
    "because each page must complete its own authentication. Keep this Streamlit page "
    "open until the run finishes."
)

st.info(
    "Existing historical JSON files remain available while the helper runs. Each file is "
    "replaced only after that product returns valid, non-empty history data. If one product "
    "fails, its previous local JSON file is left unchanged."
)

ready, readiness_message = check_playwright_chromium()
if ready:
    st.success(readiness_message)
else:
    st.error(readiness_message)

with st.expander("One-time installation and command-line usage"):
    st.markdown(
        "From the repository root, install all Python dependencies and Chromium:\n\n"
        "```powershell\n"
        "python -m pip install -r requirements.txt\n"
        "python -m playwright install chromium\n"
        "```\n\n"
        "The same refresh can be run outside Streamlit with:\n\n"
        "```powershell\n"
        "python scripts/capture_monex_history.py --product all\n"
        "```"
    )

with st.sidebar:
    st.header("Automated Monex refresh")
    st.warning(
        "Slow operation: the seven authenticated page loads can take several minutes."
    )
    headless = st.checkbox(
        "Run Chromium headless",
        value=False,
        help=(
            "Visible Chromium is recommended because it lets you complete any browser "
            "challenge. Headless mode is useful only when the pages authenticate without interaction."
        ),
    )
    run_capture = st.button(
        "Update all Monex JSON files",
        type="primary",
        use_container_width=True,
        disabled=not ready,
    )
    st.caption(
        "Requires Playwright plus `python -m playwright install chromium`. "
        "The button runs locally on the machine hosting Streamlit."
    )

if run_capture:
    command = build_capture_command(headless=headless)
    started = time.monotonic()

    with st.status(
        "Opening Monex pages and capturing authenticated history requests...",
        expanded=True,
    ) as capture_status:
        st.write(
            "A Chromium window may open. No Developer Tools work is required. "
            "Complete a browser challenge if one appears and leave the browser open."
        )

        try:
            result = subprocess.run(
                command,
                cwd=APP_ROOT,
                capture_output=True,
                text=True,
                timeout=MAX_RUNTIME_SECONDS,
                check=False,
            )
            elapsed = time.monotonic() - started
            output = combine_process_output(result.stdout, result.stderr)

            st.code(output, language="text")

            if result.returncode == 0:
                capture_status.update(
                    label=f"Monex JSON refresh completed in {elapsed / 60:.1f} minutes.",
                    state="complete",
                    expanded=True,
                )
                st.success(
                    "All seven validated history files were updated. Return to the main "
                    "dashboard to use the refreshed data."
                )
            else:
                capture_status.update(
                    label=(
                        "The helper completed with one or more product failures. "
                        "See the log below."
                    ),
                    state="error",
                    expanded=True,
                )
                st.warning(
                    "Products that completed successfully were updated. Any failed product "
                    "kept its previous historical JSON file."
                )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            output = combine_process_output(
                exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout,
                exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr,
            )
            st.code(output, language="text")
            capture_status.update(
                label=f"Automated refresh stopped after {elapsed / 60:.1f} minutes.",
                state="error",
                expanded=True,
            )
            st.error(
                "The helper exceeded the 30-minute safety limit. Existing files remain in place "
                "for products that did not complete successfully."
            )
        except OSError as exc:
            capture_status.update(
                label="The automated helper could not be started.",
                state="error",
                expanded=True,
            )
            st.error(f"Could not start the helper process: {exc}")
