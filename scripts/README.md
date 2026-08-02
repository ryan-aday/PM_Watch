# Monex initial-history capture helper

`capture_monex_history.py` creates the seven `history_*.json` files used by
`metals_spot_w_corr_app.py`.

## Recommended: paste the complete copied cURL

1. Open one of the Monex/nFusion widget links in the app's **Data references** section.
2. Press **F12**, open **Network**, reload the page, and select the request named **history**.
3. Right-click the request and choose **Copy as cURL**.
4. Paste it into a temporary file, for example `monex_history.curl.txt`.
5. From the PM_Watch repository root, run:

```bash
python scripts/capture_monex_history.py --curl-file monex_history.curl.txt --product all
```

The complete-cURL method is preferred because it captures the bearer token,
cookie, client ID, instance ID, and request body together. The helper changes
the symbol and referer for each configured product, validates the returned JSON,
and only then replaces the corresponding local file.

Delete `monex_history.curl.txt` after the run. It contains live credentials and
must not be committed or shared.

## Token-only compatibility mode

To follow the app's existing instructions and paste only the value after
`Authorization: Bearer`, run:

```bash
python scripts/capture_monex_history.py --product all
```

The token prompt is hidden. If the endpoint rejects token-only mode, use the
complete-cURL method so the request cookie is included.

You may capture a single product when a credential is symbol-specific:

```bash
python scripts/capture_monex_history.py \
  --curl-file silver_eagles.monex.curl.txt \
  --product silver_eagles
```

Available product keys:

- `junk_90_silver`
- `silver_eagles`
- `gold_eagles`
- `silver_1000oz`
- `gold_1kg`
- `gold_10oz`
- `silver_10oz`
- `all`

## Output files

The script writes these files to the current directory by default:

- `history_90_percent_silver.json`
- `history_silver_eagles.json`
- `history_gold_eagles.json`
- `history_1000oz_silver.json`
- `history_1kg_gold.json`
- `history_10oz_gold.json`
- `history_10oz_silver.json`

Use `--output-dir PATH` to write elsewhere. Run
`python scripts/capture_monex_history.py --help` for all options.

## Validation

```bash
python -m unittest discover -s tests -p "test_capture_monex_history.py"
```
