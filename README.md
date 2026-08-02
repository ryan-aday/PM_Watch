# Silver Watch — Monex vs Spot Metals Dashboard

A Streamlit dashboard for comparing Monex physical precious-metals products with Yahoo Finance silver and gold futures proxies, FRED macro overlays, premiums to spot, and dynamic correlation analysis.

The repository includes historical Monex JSON files so the dashboard remains usable when live authentication is unavailable. Users can refresh those files manually with page-specific bearer tokens or automatically through the Playwright browser helper.

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

Create and activate a virtual environment, then install the single consolidated dependency file:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Install the Chromium browser used by the automated Monex refresh:

```powershell
python -m playwright install chromium
```

On Linux, Playwright may also require system dependencies:

```bash
python -m playwright install --with-deps chromium
```

## Local Monex configuration

The original dashboard reads several values through `st.secrets` during module import. Active bearer tokens and cookies must not be committed to Git, so PM_Watch now uses a local JSON configuration and creates a gitignored Streamlit compatibility file at startup.

Copy the example file:

```powershell
Copy-Item monex_config.example.json monex_config.json
```

macOS or Linux:

```bash
cp monex_config.example.json monex_config.json
```

The local file has this structure:

```json
{
  "common": {
    "client_id": "a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5",
    "instance": "59155a1a-4c2d-44c1-9ae2-1b083713b0d5",
    "cookie": ""
  },
  "bearer_tokens": {
    "junk_90_silver": "",
    "silver_eagles": "",
    "gold_eagles": "",
    "silver_1000oz": "",
    "gold_1kg": "",
    "gold_10oz": "",
    "silver_10oz": ""
  }
}
```

The client ID and instance are non-secret request metadata. The cookie and bearer-token fields should remain blank unless the manual refresh workflow is being used.

`monex_config.json`, `.streamlit/secrets.toml`, browser profiles, and captured cURL files are ignored by Git.

You may keep the configuration elsewhere by setting:

```powershell
$env:PM_WATCH_MONEX_CONFIG = "C:\path\to\monex_config.json"
```

## Running the app

Use the configuration-aware launcher from the repository root:

```powershell
python run_pm_watch.py
```

Additional Streamlit arguments can be passed through the launcher:

```powershell
python run_pm_watch.py --server.port 8502
```

The launcher:

1. reads `monex_config.json` when present;
2. supplies blank defaults when it is absent;
3. creates the local `.streamlit/secrets.toml` expected by the original dashboard; and
4. starts `metals_spot_w_corr_app.py` in the same Python environment.

After the compatibility file has been generated once, the traditional command also works:

```powershell
streamlit run metals_spot_w_corr_app.py
```

Streamlit exposes the main dashboard and **Automated Monex Refresh** in sidebar navigation.

## Historical-data protection

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

A refresh never deletes all historical data first. Each product file is replaced only after the returned JSON is non-empty, contains intervals, and matches the expected product symbol. A failed product retains its previous local file.

## Manual Monex refresh

The manual workflow remains available on the main dashboard sidebar.

For each product:

1. Open the relevant Monex product or nFusion widget link under **Data references**.
2. Press **F12** and select **Network**.
3. Reload the page if needed.
4. Find the request named **history**.
5. Right-click and choose **Copy as cURL**.
6. Paste it into a temporary text editor.
7. Copy the value after `Authorization: Bearer`.
8. Paste that value into the matching password field in the sidebar.
9. Select **Refresh Monex JSON files using manual token input**.

The sidebar fields are blank by default. They can optionally be prefilled through the `bearer_tokens` object in `monex_config.json`.

The manual request also needs the common client ID, instance, and cookie. Put the current cookie in `common.cookie` inside the local configuration file. If the cookie or token is rejected, the previous historical JSON remains available.

Do not commit, share, or paste active bearer tokens, cookies, captured cURLs, or browser profiles into issues or pull requests.

## Automated Monex refresh from Streamlit

Open **Automated Monex Refresh** from the Streamlit sidebar and select:

```text
Update all Monex JSON files
```

The page checks that both Playwright and its Chromium browser are installed. The helper then:

1. opens each Monex product page;
2. watches network traffic from the page and embedded chart frames;
3. captures that page's authenticated `POST /api/v1/Data/history` request;
4. saves PowerShell and Bash cURL reproductions in `.monex_captures/`;
5. validates the returned JSON; and
6. atomically replaces the corresponding `history_*.json` file.

The full seven-product run is intentionally slow because every page performs its own authentication. Keep the refresh page open until completion. Visible Chromium is recommended so browser challenges can be completed. The Streamlit launcher applies a 30-minute safety timeout.

The Playwright workflow obtains its own current authentication data and does not depend on the manual tokens or cookie stored in `monex_config.json`.

## Automated refresh from the command line

```powershell
python scripts/capture_monex_history.py --product all
```

Useful alternatives:

```powershell
# One product
python scripts/capture_monex_history.py --product silver_eagles

# Headless browser
python scripts/capture_monex_history.py --product all --headless

# Capture cURLs without replacing JSON
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

Credential-bearing artifacts are written to `.monex_captures/`; the persistent browser profile is written to `.monex_browser_profile/`. Both are gitignored.

## Product normalization

- 90% Silver U.S. Coin Bag: `$1` face value is treated as `0.715` troy ounces, so a `$1000` face bag contains `715` troy ounces.
- 1000 oz Silver Bullion: `1000` troy ounces.
- 10 oz Gold Bullion Bar: `10` troy ounces.
- 1 Kilo Gold Bullion Bar: `32.1507466` troy ounces.
- Products already quoted per ounce use `1.0` ounce per unit.

```text
price per ounce = product price / ounces per unit
premium percent = (product price per ounce / reference spot price per ounce - 1) × 100
```

## Macro data

The dashboard includes:

- U.S. 10-year Treasury yield — `DGS10`
- Japan 10-year government bond yield — `IRLTLT01JPM156N`
- U.S. CPI — `CPIAUCSL`, converted to year-over-year inflation
- U.S. unemployment — `UNRATE`
- U.S. real GDP growth, percent change SAAR — `A191RL1Q225SBEA`

Daily series are forward-filled where appropriate. Monthly values are mapped across their represented month, and quarterly values across their represented quarter.

## Validation

```powershell
python -m py_compile run_pm_watch.py sitecustomize.py scripts/capture_monex_history.py pages/1_Automated_Monex_Refresh.py
python -m unittest discover -s tests -p "test_capture_monex_history.py"
```

This dashboard is intended for research and comparative analysis. Independently verify all prices, spreads, and macro interpretations before using the output for investment, trading, or business decisions.
