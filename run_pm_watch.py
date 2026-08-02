#!/usr/bin/env python3
"""Start PM_Watch after preparing its local Monex configuration.

Use this launcher instead of calling the Streamlit console script directly on a
fresh checkout. It converts the gitignored ``monex_config.json`` into the local
``.streamlit/secrets.toml`` compatibility file expected by the original app,
then starts Streamlit in the same Python environment.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sitecustomize import bootstrap  # noqa: E402


def main() -> int:
    bootstrap()

    try:
        from streamlit.web import cli as stcli
    except ImportError:
        print(
            "Streamlit is not installed. Run: "
            "python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "metals_spot_w_corr_app.py"),
        *sys.argv[1:],
    ]
    return int(stcli.main())


if __name__ == "__main__":
    raise SystemExit(main())
