# Physical Metals Analysis

A Streamlit dashboard for comparing Monex physical precious-metals products with Yahoo Finance silver and gold futures proxies, with FRED macro overlays and dynamic correlation analysis.

The repository includes historical Monex JSON files so the dashboard remains usable when live authentication is unavailable. Monex data can be updated manually with captured bearer tokens or automatically with the Playwright browser helper.

## Products tracked

- 90% Silver U.S. Coin Bag
- Silver American Eagles
- Gold American Eagles
- 1000 oz Silver Bullion
- 1 Kilo Gold Bullion Bar
- 10 oz Gold Bullion Bar
- 10 oz Silver Bullion Bar

Silver products are compared with Yahoo Finance `SI=F`; gold products are compared with `GC=F`.

## Installation

Create and activate a virtual environment, then install the consolidated dependencies:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Install the Chromium binary used by the automated Monex refresh:

```powershell
python -m playwright install chromium
```

On Linux, Playwright may also need system packages:

```bash
python -m playwright install --with-deps chromium
```

## Streamlit secrets

The manual Monex request path uses `.streamlit/secrets.toml`:

```toml
COMMON_CLIENT_ID = "..."
COMMON_INSTANCE = "..."
COMMON_COOKIE = "..."

JUNK_90_SILVER_BEARER_TOKEN = ""
SILVER_EAGLES_BEARER_TOKEN = ""
GOLD_EAGLES_BEARER_TOKEN = ""
SILVER_1000_OZ_BEARER_TOKEN = ""
GOLD_1_KG_BEARER_TOKEN = ""
GOLD_10_OZ_BEARER_TOKEN = ""
SILVER_10_OZ_BEARER_TOKEN = ""
```

Do not commit active tokens, cookies, browser profiles, or captured cURL files.

## Running the app

From the repository root:

```powershell
streamlit run Physical_Metals_Analysis.py
```

The sidebar navigation contains:

- **Physical Metals Analysis**
- **Automated Monex Refresh**

The main entry file is named `Physical_Metals_Analysis.py` so Streamlit displays the intended page name instead of deriving a label from the former implementation filename.

## Application structure

The root Streamlit page is intentionally a thin coordinator. Reusable behavior lives in the `scripts` package:

```text
PM_Watch/
├─ Physical_Metals_Analysis.py
├─ pages/
│  └─ 1_Automated_Monex_Refresh.py
├─ scripts/
│  ├─ __init__.py
│  ├─ app_config.py
│  ├─ storage.py
│  ├─ monex_data.py
│  ├─ market_data.py
│  ├─ charts.py
│  ├─ ui_helpers.py
│  └─ capture_monex_history.py
├─ tests/
│  └─ test_capture_monex_history.py
├─ history_*.json
├─ cache/
├─ requirements.txt
└─ README.md
```

Module responsibilities:

- `app_config.py`: page title, product registry, tickers, and macro-series constants.
- `storage.py`: local pickle persistence.
- `monex_data.py`: JSON validation, parsing, manual refresh, local reload, and spot-spread calculations.
- `market_data.py`: Yahoo and FRED retrieval, resilient cache fallbacks, frequency expansion, and merged datasets.
- `charts.py`: Plotly price, spread, macro, and correlation figures.
- `ui_helpers.py`: Streamlit header, sidebar, date controls, product selector, and summary components.
- `capture_monex_history.py`: Playwright capture of authenticated Monex history requests.

## Historical-data behavior

The checked-in `history_*.json` files are the baseline data source:

```text
history_90_percent_silver.json
history_silver_eagles.json
history_gold_eagles.json
history_1000oz_silver.json
history_1kg_gold.json
history_10oz_gold.json
history_10oz_silver.json
```

A product file is replaced only after a returned payload is non-empty, contains history intervals, and matches the expected symbol.

### Reload local files

The main-dashboard button **Reload Monex JSON files from disk** does not contact Monex. It clears only the Monex parsing caches and rereads the existing files in the application directory. Yahoo and FRED caches remain warm.

Because each JSON file's modification time is included in the Monex cache key, newly written Playwright files are also detected automatically on the next main-page run.

## Manual Monex refresh

For each product:

1. Open the relevant Monex product or nFusion widget page.
2. Press **F12** and open **Network**.
3. Reload the page if needed.
4. Find the request named **history**.
5. Copy it as cURL.
6. Copy the value after `Authorization: Bearer`.
7. Paste it into the matching password field.
8. Select **Query Monex using manual token input**.

Products with blank tokens keep using their existing local JSON files. Failed requests do not delete the prior history.

## Automated Monex refresh

Open **Automated Monex Refresh** and select **Update all Monex JSON files**.

The helper:

1. opens each Monex product page;
2. observes page and embedded-frame network activity;
3. captures the matching `POST /api/v1/Data/history` request;
4. saves PowerShell and Bash cURL reproductions;
5. validates the response; and
6. atomically replaces the corresponding `history_*.json`.

The full run is slow because each product page performs its own authentication. A visible browser is the default so interactive challenges can be completed. The Streamlit launcher has a 30-minute overall safety timeout.

Command-line equivalent:

```powershell
python scripts/capture_monex_history.py --product all
```

Useful alternatives:

```powershell
python scripts/capture_monex_history.py --product silver_eagles
python scripts/capture_monex_history.py --product all --headless
python scripts/capture_monex_history.py --product all --no-json
```

Credential-bearing cURLs are written to `.monex_captures/`, and the persistent browser profile is stored in `.monex_browser_profile/`. Both are ignored by Git.

## Yahoo and FRED data

Yahoo metals data uses `yfinance`.

FRED data uses `pandas_datareader.fred.FredReader`, which does not require a FRED API key. The app uses an eight-second timeout, one retry, and local pickle fallbacks.

Macro series:

- U.S. 10-year Treasury yield — `DGS10`
- Japan 10-year government bond yield — `IRLTLT01JPM156N`
- U.S. CPI — `CPIAUCSL`
- U.S. unemployment — `UNRATE`
- U.S. real GDP growth SAAR — `A191RL1Q225SBEA`

Daily series are forward-filled. Monthly and quarterly series are expanded across their represented calendar periods.

## Product normalization

- 90% Silver U.S. Coin Bag: `$1000` face value × `0.715` oz per dollar = `715` troy ounces.
- 1000 oz Silver Bullion: `1000` troy ounces.
- 10 oz Gold Bullion Bar: `10` troy ounces.
- 1 Kilo Gold Bullion Bar: `32.1507466` troy ounces.
- Products already quoted per ounce use `1.0`.

```text
price per ounce = product price / ounces per unit
```

```text
premium or discount (%) =
(product price per ounce / reference spot price per ounce - 1) × 100
```

## Deployment storage

On a single running instance, refreshed JSON files are recognized from the application directory. Managed platforms may recreate their filesystem during restart or redeployment, so runtime-written JSON is not guaranteed to persist.

For durable deployments, either:

- mount a persistent volume and point the helper and loader at it; or
- upload validated JSON to object storage and use the checked-in files as fallback.

## Validation

Run syntax checks:

```powershell
python -m py_compile Physical_Metals_Analysis.py `
  pages/1_Automated_Monex_Refresh.py `
  scripts/app_config.py scripts/storage.py scripts/monex_data.py `
  scripts/market_data.py scripts/charts.py scripts/ui_helpers.py `
  scripts/capture_monex_history.py
```

Run the helper tests:

```powershell
python -m unittest discover -s tests -p "test_capture_monex_history.py"
```

## Known limitations

- Monex authentication can be slow or change without notice.
- Captured tokens and cookies are temporary.
- Some product histories begin later than others.
- Yahoo `SI=F` and `GC=F` are futures-based proxies, not direct physical spot benchmarks.
- A hosted environment must permit subprocesses, browser execution, and writable storage for the automated refresh.
- A headless deployment may not be able to complete interactive browser challenges.

## Usage note

This dashboard is intended for research and comparative analysis. Independently verify prices, spreads, and macro interpretations before using the output for investment, trading, or business decisions.
