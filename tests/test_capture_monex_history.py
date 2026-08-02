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


class FakeRequest:
    def __init__(self, url, method="POST", post_data=""):
        self.url = url
        self.method = method
        self.post_data = post_data


class CaptureMonexHistoryTests(unittest.TestCase):
    def test_matches_page_specific_history_request(self):
        product = MODULE.PRODUCT_BY_KEY["gold_eagles"]
        request = FakeRequest(
            "https://widget.nfusionsolutions.com/api/v1/Data/history",
            post_data="clientId=x&instance=page-specific&symbols=ae&timeframeType=year",
        )
        self.assertTrue(MODULE.is_history_request(request, product))

    def test_rejects_other_symbol_and_non_history_request(self):
        product = MODULE.PRODUCT_BY_KEY["silver_eagles"]
        wrong_symbol = FakeRequest(
            "https://widget.nfusionsolutions.com/api/v1/Data/history",
            post_data="symbols=ae",
        )
        wrong_path = FakeRequest(
            "https://widget.nfusionsolutions.com/api/v1/Data/spot",
            post_data="symbols=saei",
        )
        self.assertFalse(MODULE.is_history_request(wrong_symbol, product))
        self.assertFalse(MODULE.is_history_request(wrong_path, product))

    def test_powershell_curl_contains_complete_request(self):
        command = MODULE.format_curl_powershell(
            method="POST",
            url="https://widget.nfusionsolutions.com/api/v1/Data/history",
            headers={
                "authorization": "Bearer abc.def",
                "cookie": "session=x&other=y",
                "content-length": "999",
            },
            post_data="symbols=sc&timeframeType=year",
        )
        self.assertIn("authorization", command.lower())
        self.assertIn("Bearer abc.def", command)
        self.assertIn("session=x&other=y", command)
        self.assertIn("symbols=sc&timeframeType=year", command)
        self.assertNotIn("content-length", command.lower())

    def test_source_auto_uses_product_then_widget(self):
        product = MODULE.PRODUCT_BY_KEY["silver_10oz"]
        urls = MODULE.source_urls(product, "auto")
        self.assertEqual(urls[0], product.page_url)
        self.assertEqual(urls[1], product.fallback_widget_url)

    def test_extracts_page_specific_widget_url(self):
        product = MODULE.PRODUCT_BY_KEY["gold_1kg"]
        html = (
            '<script src="https://widget.nfusionsolutions.com/custom/monex/'
            'script/chart/1/client/page-instance?symbols=GBX1K&amp;currency=USD"></script>'
        )
        urls = MODULE.extract_widget_urls_from_html(html, product)
        self.assertEqual(
            urls,
            [
                "https://widget.nfusionsolutions.com/custom/monex/chart/1/"
                "client/page-instance?symbols=GBX1K&currency=USD"
            ],
        )

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
