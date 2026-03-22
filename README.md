# Silver Watch — Monex vs Spot Metals Dashboard

A Streamlit dashboard for comparing multiple **Monex retail precious-metals products** against **Yahoo Finance metals spot proxies**, with optional **FRED macro overlays** and a **dynamic correlation heatmap**.

The app is designed to:

- refresh Monex product-history JSON files from the nFusion widget endpoint when possible
- fall back to local JSON files when refresh fails
- normalize Monex products to **price per troy ounce**
- compare each product against the appropriate spot proxy
- calculate spreads and premium/discount percentages versus spot
- overlay macro series and recalculate correlations over a selected timeframe

---

## What the app does

The dashboard loads historical data for multiple Monex products, including:

- 90% Silver U.S. Coin Bag
- Silver American Eagles
- Gold American Eagles
- 1000 oz Silver Bullion
- 1 Kilo Gold Bullion Bar
- 10 oz Gold Bullion Bar
- 10 oz Silver Bullion Bar

It then compares those products against:

- **Silver spot proxy** from Yahoo Finance: `SI=F`
- **Gold spot proxy** from Yahoo Finance: `GC=F`

The app includes:

### 1. Monex Products vs Spot
Plots selected Monex products on a **per-ounce basis** and overlays the relevant silver and/or gold spot-proxy series.

### 2. Monex Product Premium / Discount vs Spot
Plots each selected product’s spread versus its reference spot price, either as:

- absolute difference (`$/oz`)
- premium / discount (`%`)

### 3. Macro Overlay
Overlays selected macro series from FRED over the same selected timeframe.

### 4. Dynamic Correlation Heatmap
Recalculates correlations based on the currently selected date window and selected products.

---

## Product normalization to price per ounce

Monex JSON values are converted into **implied price per troy ounce** using product-specific ounce assumptions.

Examples:

- **90% Silver U.S. Coin Bag**  
  Assumes `$1 face value = 0.715 troy oz silver`, so a `$1000 face bag = 715 troy oz`

- **1000 oz Silver Bullion**  
  Uses `1000 oz`

- **10 oz bars**  
  Uses `10 oz`

- **1 kilo gold bar**  
  Uses `32.1507466 troy oz`

The app stores each product’s `ounces_per_unit` in the product registry and computes:

\[
\text{price per oz} = \frac{\text{product price}}{\text{ounces per unit}}
\]

---

## Premium / discount calculation

For each Monex product, the app calculates:

- **absolute spread**
- **premium / discount percent**

The premium / discount formula is:

\[
\left(\frac{\text{product price per oz}}{\text{reference spot price per oz}} - 1\right) \times 100
\]

Interpretation:

- `0%` = at spot
- positive value = premium to spot
- negative value = discount to spot

---

## Spot references used

The app matches each Monex product to the appropriate Yahoo Finance spot proxy:

- **Silver products** → `SI=F`
- **Gold products** → `GC=F`

The app can also compute the **gold/silver ratio** when both spot series are available.

---

## Macro data included

The dashboard can overlay and correlate against the following FRED series:

- **U.S. 10Y Treasury yield** — `DGS10`
- **Japan 10Y government bond yield** — `IRLTLT01JPM156N`
- **U.S. CPI for All Urban Consumers** — `CPIAUCSL`
  - converted to **YoY CPI inflation**
- **U.S. unemployment rate** — `UNRATE`
- **U.S. real GDP growth, percent change SAAR** — `A191RL1Q225SBEA`

### Frequency handling

Because these macro series have mixed frequencies, the app expands them onto a daily index for comparison:

- **daily series** → forward-filled where appropriate
- **monthly series** → same value used for every day in the represented month
- **quarterly series** → same value used for every day in the represented quarter

---

## Main features

- Multiple Monex products handled through a shared product registry
- Per-product local JSON fallback support
- Optional Windows `curl.exe` refresh for Monex JSON files
- Per-ounce normalization by product
- Product-minus-spot spread calculations
- Dynamic date-range filtering
- Multi-product selection
- Macro overlay chart
- Dynamic correlation heatmap
- CSV download of the current filtered view
- Cached Monex, Yahoo, and macro data for faster reruns

---

## Project structure

Example layout:

```text
your_project/
├─ metals_spot_w_corr_app.py
├─ history_90_percent_silver.json
├─ history_silver_eagles.json
├─ history_gold_eagles.json
├─ history_1000oz_silver.json
├─ history_1kg_gold.json
├─ history_10oz_gold.json
├─ history_10oz_silver.json
├─ cache/
│  ├─ yahoo_metals.pkl
│  ├─ fred_DGS10.pkl
│  ├─ fred_IRLTLT01JPM156N.pkl
│  ├─ fred_CPIAUCSL.pkl
│  ├─ fred_UNRATE.pkl
│  └─ fred_A191RL1Q225SBEA.pkl
├─ README_Silver_Watch_v2.md
└─ requirements.txt
```

Recommended local Monex JSON filenames:

- `history_90_percent_silver.json`
- `history_silver_eagles.json`
- `history_gold_eagles.json`
- `history_1000oz_silver.json`
- `history_1kg_gold.json`
- `history_10oz_gold.json`
- `history_10oz_silver.json`

---

## Installation

### 1. Create and activate a virtual environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install streamlit streamlit-extras pandas plotly yfinance pandas_datareader
```

Example `requirements.txt`:

```text
streamlit
pandas
plotly
yfinance
pandas_datareader
```

---

## Running the app

```bash
streamlit run metals_spot_w_corr_app.py
```

Then open the local Streamlit URL shown in the terminal.

---

## Monex refresh behavior

The app can attempt to refresh local Monex JSON files using saved Windows `curl.exe` parameters captured from the Monex/nFusion widget requests.

When refresh succeeds, files such as these are updated:

- `history_90_percent_silver.json`
- `history_silver_eagles.json`
- `history_gold_eagles.json`
- `history_1000oz_silver.json`
- `history_1kg_gold.json`
- `history_10oz_gold.json`
- `history_10oz_silver.json`

### Important note

The Monex refresh flow depends on saved **bearer tokens** captured from the widget calls. Those tokens may expire over time.

That is why the app also supports:

- local JSON fallback files
- cached previously refreshed files

---

## Yahoo and FRED caching behavior

To make the app more resilient:

- Yahoo metals pulls can be cached to a local file
- FRED macro series can be cached to local files
- cached files can be used when live pulls fail
- warnings can be shown when the app falls back to cached data

This helps avoid empty charts when a provider is temporarily unavailable.

---

## Expected Monex JSON shape

The Monex / nFusion history files are expected to look like:

```json
[
  {
    "symbol": "SC",
    "name": "90% Silver Bullion Bar",
    "baseCurrency": "USD",
    "intervals": [
      {
        "start": "2022-09-21T00:00:00",
        "end": "2022-09-21T23:59:59.999+00:00",
        "open": 23.05,
        "high": 23.22,
        "low": 22.79,
        "last": 23.01,
        "change": -0.15,
        "changePercent": -0.6519
      }
    ]
  }
]
```

The app uses interval fields such as:

- `start`
- `end`
- `open`
- `high`
- `low`
- `last`
- `change`
- `changePercent`

---

## Sidebar / UI behavior

### Sidebar
The sidebar includes:

- product selection
- plot display toggles
- refresh controls
- source/reference links

### Main page
The main page includes:

- synchronized date-range controls
- summary metrics
- latest row details
- price comparison chart
- spread / premium chart
- macro chart
- correlation heatmap
- data preview
- CSV download

---

## Performance notes

The app is optimized by caching:

- parsed Monex JSON data
- concatenated Monex dataframes
- Yahoo metals downloads
- FRED macro data
- fully merged datasets

This keeps slider/date adjustments much faster by avoiding unnecessary reloading and reparsing on each rerun.

---

## Known behaviors and limitations

- Some Monex products start later than others.  
  Example: a specific product may only begin in 2022, so it will not appear earlier in the selected window.

- Some products can visually overlap spot closely when their premium is small.

- Yahoo `SI=F` and `GC=F` are **futures-based spot proxies**, not direct physical spot benchmarks.

- Saved Monex bearer tokens may expire.

- The correlation heatmap is recalculated on the filtered timeframe, so correlations can change meaningfully as the time window changes.

---

## Data references

### Yahoo Finance
- [Silver futures / spot proxy (SI=F)](https://finance.yahoo.com/quote/SI%3DF/)
- [Gold futures / spot proxy (GC=F)](https://finance.yahoo.com/quote/GC%3DF/)

### Monex product pages
- [90% Silver U.S. Coin Bag](https://www.monex.com/90-us-silver-coin-bag-price-charts/)
- [Silver American Eagles](https://www.monex.com/silver-american-eagle-price-charts/)
- [Gold American Eagles](https://www.monex.com/gold-american-eagle-price-charts/)
- [1000 oz Silver Bullion](https://www.monex.com/1000-oz-silver-bullion-price-charts/)
- [1 Kilo Gold Bullion Bar](https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/)
- [10 oz Gold Bullion Bar](https://www.monex.com/10-oz-gold-bullion-bar-price-charts/)
- [10 oz Silver Bullion Bar](https://www.monex.com/10-oz-silver-bullion-price-charts/)

### nFusion widget pages
- [90% Silver Coin Bag widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SC)
- [Silver American Eagles widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SAEI)
- [Gold American Eagles widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=AE)
- [1000 oz Silver Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBI1000)
- [1 Kilo Gold Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX1K)
- [10 oz Gold Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX10)
- [10 oz Silver Bullion widget](https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBX)

### FRED macro series
- [U.S. 10Y Treasury yield (DGS10)](https://fred.stlouisfed.org/series/DGS10)
- [Japan 10Y government bond yield (IRLTLT01JPM156N)](https://fred.stlouisfed.org/series/IRLTLT01JPM156N)
- [U.S. CPI for All Urban Consumers (CPIAUCSL)](https://fred.stlouisfed.org/series/CPIAUCSL)
- [U.S. unemployment rate (UNRATE)](https://fred.stlouisfed.org/series/UNRATE)
- [Real GDP growth, percent change SAAR (A191RL1Q225SBEA)](https://fred.stlouisfed.org/series/A191RL1Q225SBEA)

---

## Usage note

This dashboard is intended for research and comparative analysis. Users should independently verify all prices, spreads, and macro interpretations before using the output for investment, trading, or business decisions.
