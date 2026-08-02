# Automated Monex page capture

`capture_monex_history.py` automates the browser steps that previously required
F12, Network, finding `history`, and **Copy as cURL**.

For every selected product, it:

1. opens the public Monex product page in Chromium;
2. watches network traffic from the page and embedded chart frames;
3. finds that product's POST to `api/v1/Data/history`;
4. records the exact request as PowerShell and Bash cURL files; and
5. validates and writes the returned `history_*.json` file.

The `auto` source mode tries the actual Monex product page first. If the chart is
not loaded there, it extracts the page's current nFusion chart instance when
possible and then falls back to the known direct widget URL.

## Install

From the PM_Watch repository root:

```powershell
python -m pip install -r scripts/requirements.txt
python -m playwright install chromium
```

The browser binary installation is a one-time step.

## Capture all seven products

```powershell
python scripts/capture_monex_history.py --product all
```

A visible browser is used by default because it is less likely to be blocked and
lets you complete a browser challenge if one appears. The helper continues
capturing automatically; Developer Tools are not needed.

For unattended operation after confirming it works locally:

```powershell
python scripts/capture_monex_history.py --product all --headless
```

To use an already installed Chrome or Edge instead of Playwright Chromium:

```powershell
python scripts/capture_monex_history.py --product all --browser chrome
python scripts/capture_monex_history.py --product all --browser msedge
```

## Outputs

The normal PM_Watch data files are written to the repository root:

- `history_90_percent_silver.json`
- `history_silver_eagles.json`
- `history_gold_eagles.json`
- `history_1000oz_silver.json`
- `history_1kg_gold.json`
- `history_10oz_gold.json`
- `history_10oz_silver.json`

Page-specific request captures are written under `.monex_captures/`:

- `<product>.curl.ps1` — PowerShell-compatible `curl.exe` command
- `<product>.curl.sh` — Bash/Git Bash/WSL-compatible command
- `manifest.json` — non-secret capture metadata

The cURL files include short-lived Authorization and Cookie headers. The capture
folder and persistent browser profile are gitignored. Do not share the cURL
files while their credentials may still be active.

Use `--no-json` to collect cURLs without replacing the app data files.

## Product-page fallback controls

```powershell
# Only inspect the actual public Monex product pages
python scripts/capture_monex_history.py --product all --source product

# Only inspect the direct nFusion widget pages
python scripts/capture_monex_history.py --product all --source widget
```

## Validation

The unit tests do not require a browser installation:

```powershell
python -m unittest discover -s tests -p "test_capture_monex_history.py"
```
