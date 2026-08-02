# Silver Watch — Monex vs Spot Metals Dashboard

A Streamlit dashboard for comparing Monex physical precious-metals products with Yahoo Finance silver and gold futures proxies, with FRED macro overlays and dynamic correlation analysis.

The repository includes historical Monex JSON files so the dashboard remains usable when live authentication is unavailable. Users can refresh those files in either of two ways:

1. manually paste bearer tokens captured from browser Developer Tools; or
2. run the Playwright browser helper from the Streamlit sidebar or command line.

The automated helper validates each response before replacing its corresponding historical JSON file. A failed product therefore keeps its previous local history.

## Products tracked

- 90% Silver U.S. Coin Bag
- Silver American Eagles
- Gold American Eagles
- 1000 oz Silver Bullion
- 1 Kilo Gold Bullion Bar
- 10 oz Gold Bullion Bar
- 10 oz Silver Bullion Bar

Silver products are compared with Yahoo Finance `SI=F`; gold products are compared with `GC=F`.

## Main features

- Multiple Monex products through a shared product registry
- Historical local JSON fallback
- Manual bearer-token refresh from the main dashboard sidebar
- Automated page-specific cURL and JSON capture through Playwright
- Per-ounce normalization
- Absolute and percentage premiums or discounts to spot
- Synchronized date filtering
- Yahoo and FRED caching
- U.S. and Japanese yield, CPI, unemployment, and GDP overlays
- Dynamic correlation heatmap
- CSV export of the filtered view

## Installation

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv venv
venv\Scripts\activate.bat
```

macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install all Python dependencies

The project uses one consolidated dependency file:

```bash
python -m pip install -r requirements.txt
```

### 3. Install the Playwright Chromium browser

The Python package and the browser binary are separate installations. This command is required before using the automated Monex refresh:

```bash
python -m playwright install chromium
```

On some Linux systems, Playwright may also require operating-system packages:

```bash
python -m playwright install --with-deps chromium
```

## Running the app

From the repository root:

```bash
streamlit run metals_spot_w_corr_app.py
```

Streamlit automatically exposes two pages in its sidebar navigation:

- the main precious-metals dashboard; and
- **Automated Monex Refresh**.

## Historical-data behavior

The checked-in `history_*.json` files are the baseline data source. The app loads these files whenever a live refresh is not requested or does not succeed.

Files used by the app:

```text
history_90_percent_silver.json
history_silver_eagles.json
history_gold_eagles.json
history_1000oz_silver.json
history_1kg_gold.json
history_10oz_gold.json
history_10oz_silver.json
```

A refresh never deletes the entire historical dataset first. Each product file is replaced only after the returned JSON is non-empty, contains intervals, and matches the expected product symbol.

## Manual Monex refresh

The original manual workflow remains available in the main dashboard sidebar.

For each relevant product:

1. Open the Monex product or nFusion widget link under **Data references**.
2. Press **F12** to open Developer Tools.
3. Select the **Network** tab.
4. Reload the page if necessary.
5. Find the request named **history**.
6. Right-click it and choose **Copy as cURL**.
7. Paste the command into a temporary text editor.
8. Copy the value after `Authorization: Bearer`.
9. Paste that value into the matching password field in the dashboard sidebar.
10. Select **Refresh Monex JSON files using manual token input**.

Tokens can expire. If a token or cookie is rejected, the previous local JSON file remains available.

The manual request path also uses the common client ID, widget instance, and cookie values configured through Streamlit secrets. A local `.streamlit/secrets.toml` can contain values such as:

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

## Automated Monex refresh from Streamlit

Open **Automated Monex Refresh** from the Streamlit sidebar.

The page checks whether both Playwright and its Chromium browser are installed. When ready, select:

```text
Update all Monex JSON files
```

The browser helper then:

1. opens each of the seven Monex product pages;
2. watches network activity from the page and embedded chart frames;
3. identifies that product's authenticated `POST /api/v1/Data/history` request;
4. captures the exact request as PowerShell and Bash cURL files;
5. validates the returned JSON; and
6. atomically replaces the matching `history_*.json` file.

### Runtime warning

This is intentionally slow. Each product page performs its own authentication and may take tens of seconds or longer. A full seven-product run may take several minutes.

Keep the Streamlit refresh page open until completion. A visible Chromium window is the default because it allows a user to complete any browser challenge. Headless mode is optional but is less resilient when interaction is required.

The Streamlit launcher applies a 30-minute safety timeout. Successful products are retained even if another product fails.

## Automated refresh from the command line

The same helper can be run independently:

```bash
python scripts/capture_monex_history.py --product all
```

Useful alternatives:

```bash
# Capture one product
python scripts/capture_monex_history.py --product silver_eagles

# Run without a visible browser
python scripts/capture_monex_history.py --product all --headless

# Capture cURLs without replacing JSON files
python scripts/capture_monex_history.py --product all --no-json
```

Available product keys:

```text
junk_90_silver
silver_eagles
gold_eagles
silver_1000oz
gold_1kg
gold_10oz
silver_10oz
all
```

Credential-bearing artifacts are written to `.monex_captures/`:

```text
.monex_captures/
├─ junk_90_silver.curl.ps1
├─ junk_90_silver.curl.sh
├─ silver_eagles.curl.ps1
├─ silver_eagles.curl.sh
├─ ...
└─ manifest.json
```

The persistent browser profile is stored in `.monex_browser_profile/`. Both locations are ignored by Git because they can contain temporary authentication data.

## Product normalization

Monex product prices are converted to implied price per troy ounce using product-specific assumptions.

- 90% Silver U.S. Coin Bag: `$1` face value is treated as `0.715` troy ounces, so a `$1000` face bag contains `715` troy ounces.
- 1000 oz Silver Bullion: `1000` troy ounces.
- 10 oz Gold Bullion Bar: `10` troy ounces.
- 1 Kilo Gold Bullion Bar: `32.1507466` troy ounces.
- Products already quoted per ounce use `1.0` ounce per unit in the registry.

The calculation is:

```text
price per ounce = product price / ounces per unit
```

Premium or discount is calculated as:

```text
(product price per ounce / reference spot price per ounce - 1) × 100
```

## Macro data

The dashboard includes:

- U.S. 10-year Treasury yield — `DGS10`
- Japan 10-year government bond yield — `IRLTLT01JPM156N`
- U.S. CPI — `CPIAUCSL`, converted to year-over-year inflation
- U.S. unemployment — `UNRATE`
- U.S. real GDP growth, percent change SAAR — `A191RL1Q225SBEA`

Daily series are forward-filled where appropriate. Monthly values are mapped across their represented month, and quarterly values across their represented quarter.

## Project structure

```text
PM_Watch/
├─ metals_spot_w_corr_app.py
├─ pages/
│  └─ 1_Automated_Monex_Refresh.py
├─ scripts/
│  └─ capture_monex_history.py
├─ tests/
│  └─ test_capture_monex_history.py
├─ history_*.json
├─ cache/
├─ requirements.txt
└─ README.md
```

## Validation

Run the helper tests from the repository root:

```bash
python -m unittest discover -s tests -p "test_capture_monex_history.py"
```

A syntax-only check can also be run with:

```bash
python -m py_compile scripts/capture_monex_history.py pages/1_Automated_Monex_Refresh.py
```

## Known limitations

- Monex authentication can be slow or change without notice.
- Captured bearer tokens and cookies are temporary.
- Some product histories begin later than others.
- Yahoo `SI=F` and `GC=F` are futures-based proxies rather than direct physical spot benchmarks.
- The automated Streamlit button runs on the machine hosting Streamlit. A remote or managed deployment must permit subprocesses, persistent local files, and browser execution.
- A hosted headless environment may not be able to complete interactive browser challenges.

## Data references

### Yahoo Finance

- [Silver futures / spot proxy (`SI=F`)](https://finance.yahoo.com/quote/SI%3DF/)
- [Gold futures / spot proxy (`GC=F`)](https://finance.yahoo.com/quote/GC%3DF/)

### Monex product pages

- [90% Silver U.S. Coin Bag](https://www.monex.com/90-us-silver-coin-bag-price-charts/)
- [Silver American Eagles](https://www.monex.com/silver-american-eagle-price-charts/)
- [Gold American Eagles](https://www.monex.com/gold-american-eagle-price-charts/)
- [1000 oz Silver Bullion](https://www.monex.com/1000-oz-silver-bullion-price-charts/)
- [1 Kilo Gold Bullion Bar](https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/)
- [10 oz Gold Bullion Bar](https://www.monex.com/10-oz-gold-bullion-bar-price-charts/)
- [10 oz Silver Bullion Bar](https://www.monex.com/10-oz-silver-bullion-price-charts/)

## Usage note

This dashboard is intended for research and comparative analysis. Independently verify prices, spreads, and macro interpretations before using them for investment, trading, or business decisions.
