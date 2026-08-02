"""PM_Watch local configuration bootstrap.

Python imports ``sitecustomize`` automatically during interpreter startup when
this repository is on ``sys.path``.  The existing dashboard currently reads
``st.secrets`` while its module is imported.  To keep that legacy path from
crashing without committing credentials, this bootstrap creates a local,
gitignored ``.streamlit/secrets.toml`` from ``monex_config.json`` when no
Streamlit secrets file already exists.

The browser-based Playwright refresh does not require this file.  It exists only
for the optional manual bearer-token refresh retained in the original app.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "monex_config.json"
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"

DEFAULT_COMMON = {
    "client_id": "a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5",
    "instance": "59155a1a-4c2d-44c1-9ae2-1b083713b0d5",
    "cookie": "",
}

TOKEN_SECRET_NAMES = {
    "junk_90_silver": "JUNK_90_SILVER_BEARER_TOKEN",
    "silver_eagles": "SILVER_EAGLES_BEARER_TOKEN",
    "gold_eagles": "GOLD_EAGLES_BEARER_TOKEN",
    "silver_1000oz": "SILVER_1000_OZ_BEARER_TOKEN",
    "gold_1kg": "GOLD_1_KG_BEARER_TOKEN",
    "gold_10oz": "GOLD_10_OZ_BEARER_TOKEN",
    "silver_10oz": "SILVER_10_OZ_BEARER_TOKEN",
}


def _toml_string(value: Any) -> str:
    """Encode a scalar as a TOML basic string."""
    text = "" if value is None else str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_config(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("The Monex configuration root must be a JSON object.")
    return payload


def _render_secrets(config: Mapping[str, Any]) -> str:
    common = dict(DEFAULT_COMMON)
    common.update(_mapping(config.get("common")))
    tokens = _mapping(config.get("bearer_tokens"))

    values = {
        "COMMON_CLIENT_ID": common.get("client_id", DEFAULT_COMMON["client_id"]),
        "COMMON_INSTANCE": common.get("instance", DEFAULT_COMMON["instance"]),
        "COMMON_COOKIE": common.get("cookie", ""),
    }
    for product_key, secret_name in TOKEN_SECRET_NAMES.items():
        values[secret_name] = tokens.get(product_key, "")

    header = (
        "# Generated locally by sitecustomize.py.\n"
        "# Do not commit this file. Edit monex_config.json instead.\n"
    )
    body = "\n".join(f"{name} = {_toml_string(value)}" for name, value in values.items())
    return header + body + "\n"


def bootstrap() -> None:
    if SECRETS_PATH.exists():
        return

    configured_path = os.environ.get("PM_WATCH_MONEX_CONFIG", "").strip()
    config_path = Path(configured_path).expanduser() if configured_path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = ROOT / config_path

    config = _load_config(config_path)
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SECRETS_PATH.with_suffix(".toml.tmp")
    temporary_path.write_text(_render_secrets(config), encoding="utf-8")
    temporary_path.replace(SECRETS_PATH)


try:
    bootstrap()
except Exception as exc:  # Do not make every Python command fail over optional config.
    print(f"PM_Watch configuration bootstrap warning: {exc}", file=sys.stderr)
