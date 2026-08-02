import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "capture_monex_history.py"
SPEC = importlib.util.spec_from_file_location("capture_monex_history", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CaptureMonexHistoryTests(unittest.TestCase):
    def test_parse_windows_multiline_curl(self):
        command = r'''curl "https://widget.nfusionsolutions.com/api/v1/Data/history" ^
  -H "Authorization: Bearer abc.def-123" ^
  -H "Cookie: session=secret" ^
  -H "Content-Type: application/x-www-form-urlencoded; charset=UTF-8" ^
  --data-raw "clientId=client&instance=instance&symbols=sc&timeframeType=year"'''
        parsed = MODULE.parse_curl(command)
        self.assertEqual(parsed.url, MODULE.HISTORY_URL)
        self.assertEqual(parsed.headers["Authorization"], "Bearer abc.def-123")
        self.assertEqual(parsed.headers["Cookie"], "session=secret")
        self.assertEqual(parsed.data["symbols"], "sc")

    def test_request_rewrites_symbol_and_referer(self):
        template = MODULE.CurlRequest(
            url=MODULE.HISTORY_URL,
            headers={"Authorization": "Bearer token", "Cookie": "x=y"},
            data={"symbols": "sc", "timeframeType": "year"},
        )
        product = MODULE.PRODUCT_BY_KEY["gold_eagles"]
        request = MODULE.request_for_product(template, product, None)
        self.assertEqual(request.data["symbols"], "ae")
        self.assertEqual(request.headers["Referer"], product.widget_url)
        self.assertEqual(request.data["timeframeType"], "year")

    def test_validate_and_atomic_write(self):
        product = MODULE.PRODUCT_BY_KEY["silver_eagles"]
        payload = [{"symbol": "SAEI", "intervals": [{"start": "2026-01-01"}]}]
        self.assertEqual(MODULE.validate_history(payload, product), 1)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / product.output_file
            MODULE.atomic_write_json(path, payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    def test_rejects_empty_history(self):
        product = MODULE.PRODUCT_BY_KEY["silver_eagles"]
        with self.assertRaisesRegex(ValueError, "no history intervals"):
            MODULE.validate_history([{"symbol": "SAEI", "intervals": []}], product)


if __name__ == "__main__":
    unittest.main()
