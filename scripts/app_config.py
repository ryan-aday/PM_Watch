from __future__ import annotations

from pathlib import Path

APP_TITLE = "Physical Metals Analysis"
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

YAHOO_SILVER_TICKER = "SI=F"
YAHOO_GOLD_TICKER = "GC=F"

FRED_SERIES = (
    "DGS10",
    "IRLTLT01JPM156N",
    "CPIAUCSL",
    "UNRATE",
    "A191RL1Q225SBEA",
)

MACRO_COLUMNS = (
    "us_10y_yield",
    "jpn_10y_yield",
    "us_cpi_yoy_pct",
    "us_unemployment",
    "us_real_gdp_growth",
)

DEFAULT_SELECTED_PRODUCTS = (
    "junk_90_silver",
    "silver_eagles",
    "silver_10oz",
    "gold_eagles",
    "gold_10oz",
)

MONEX_PRODUCTS = {
    "junk_90_silver": {
        "label": "90% Silver U.S. Coin Bag",
        "symbol": "sc",
        "referer_symbol": "SC",
        "metal": "silver",
        "ounces_per_unit": 715.0,
        "json_file": "history_90_percent_silver.json",
        "page_url": "https://www.monex.com/90-us-silver-coin-bag-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SC",
        "secret_name": "JUNK_90_SILVER_BEARER_TOKEN",
    },
    "silver_eagles": {
        "label": "Silver American Eagles",
        "symbol": "saei",
        "referer_symbol": "SAEI",
        "metal": "silver",
        "ounces_per_unit": 1.0,
        "json_file": "history_silver_eagles.json",
        "page_url": "https://www.monex.com/silver-american-eagle-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SAEI",
        "secret_name": "SILVER_EAGLES_BEARER_TOKEN",
    },
    "gold_eagles": {
        "label": "Gold American Eagles",
        "symbol": "ae",
        "referer_symbol": "AE",
        "metal": "gold",
        "ounces_per_unit": 1.0,
        "json_file": "history_gold_eagles.json",
        "page_url": "https://www.monex.com/gold-american-eagle-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=AE",
        "secret_name": "GOLD_EAGLES_BEARER_TOKEN",
    },
    "silver_1000oz": {
        "label": "1000 oz Silver Bullion",
        "symbol": "sbi1000",
        "referer_symbol": "SBI1000",
        "metal": "silver",
        "ounces_per_unit": 1000.0,
        "json_file": "history_1000oz_silver.json",
        "page_url": "https://www.monex.com/1000-oz-silver-bullion-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBI1000",
        "secret_name": "SILVER_1000_OZ_BEARER_TOKEN",
    },
    "gold_1kg": {
        "label": "1 Kilo Gold Bullion Bar",
        "symbol": "gbx1k",
        "referer_symbol": "GBX1K",
        "metal": "gold",
        "ounces_per_unit": 32.1507466,
        "json_file": "history_1kg_gold.json",
        "page_url": "https://www.monex.com/1-kilo-gold-bullion-bar-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX1K",
        "secret_name": "GOLD_1_KG_BEARER_TOKEN",
    },
    "gold_10oz": {
        "label": "10 oz Gold Bullion Bar",
        "symbol": "gbx10",
        "referer_symbol": "GBX10",
        "metal": "gold",
        "ounces_per_unit": 10.0,
        "json_file": "history_10oz_gold.json",
        "page_url": "https://www.monex.com/10-oz-gold-bullion-bar-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=GBX10",
        "secret_name": "GOLD_10_OZ_BEARER_TOKEN",
    },
    "silver_10oz": {
        "label": "10 oz Silver Bullion Bar",
        "symbol": "sbx",
        "referer_symbol": "SBX",
        "metal": "silver",
        "ounces_per_unit": 10.0,
        "json_file": "history_10oz_silver.json",
        "page_url": "https://www.monex.com/10-oz-silver-bullion-price-charts/",
        "widget_url": "https://widget.nfusionsolutions.com/custom/monex/chart/1/a0fa8f6f-0b7b-4d1a-bb3f-045d29d8aee5/59155a1a-4c2d-44c1-9ae2-1b083713b0d5?symbols=SBX",
        "secret_name": "SILVER_10_OZ_BEARER_TOKEN",
    },
}
