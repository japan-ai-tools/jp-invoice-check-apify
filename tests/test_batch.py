"""Batch mode (a normal Apify run). No network: Apify's API is replaced by a stub."""
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jpinvoice import batch  # noqa: E402

ENV = {"APIFY_TOKEN": "t", "ACTOR_DEFAULT_DATASET_ID": "ds1", "ACTOR_DEFAULT_KEY_VALUE_STORE_ID": "kv1"}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def stub(inp=None, missing=False):
    calls = []

    def opener(req, timeout=30):
        calls.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None))
        if req.full_url.endswith("/records/INPUT"):
            if missing:
                raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
            return Resp(json.dumps(inp or {}).encode())
        return Resp(b"{}")
    return opener, calls


class TestBatch(unittest.TestCase):
    def setUp(self):
        self.old = {k: os.environ.get(k) for k in ENV}
        os.environ.update(ENV)

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_no_input_checks_sample_writes_item_and_charges_nothing(self):
        for kw in ({"inp": {}}, {"missing": True}):
            opener, calls = stub(**kw)
            charged = []
            items = batch.run(env=ENV, opener=opener, charge=lambda e, r: charged.append(e))
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0]["sample"] and items[0]["ok"])
            post = [c for c in calls if c[0] == "POST"]
            self.assertEqual(post[0][1], "https://api.apify.com/v2/datasets/ds1/items")
            self.assertEqual(len(post[0][2]), 1)             # the daily test gets a non-empty dataset
            self.assertEqual(charged, [])

    def test_input_invoices_are_checked_and_each_charged_once(self):
        bad = json.loads(json.dumps(batch.SAMPLE))
        bad["totals"][0]["tax"] = 205
        opener, calls = stub({"invoices": [batch.SAMPLE, bad], "role": "receive"})
        charged = []
        items = batch.run(env=ENV, opener=opener, charge=lambda e, r: charged.append(e))
        self.assertEqual([i["ok"] for i in items], [True, False])
        self.assertEqual(charged, ["invoice-checked", "invoice-checked"])

    def test_bad_input_fails_before_charging_or_writing(self):
        for inp in ({"invoices": "x"}, {"invoices": [1, 2]}, {"invoices": [{}] * 1001}):
            opener, calls = stub(inp)
            charged = []
            with self.assertRaises(ValueError):
                batch.run(env=ENV, opener=opener, charge=lambda e, r: charged.append(e))
            self.assertEqual(charged, [])
            self.assertFalse([c for c in calls if c[0] == "POST"])

    def test_standby_detection(self):
        os.environ["APIFY_META_ORIGIN"] = "STANDBY"
        self.assertTrue(batch.is_standby())
        for v in ("API", "WEB", "SCHEDULER", "TEST"):
            os.environ["APIFY_META_ORIGIN"] = v
            self.assertFalse(batch.is_standby())
        os.environ.pop("APIFY_META_ORIGIN")

    def test_sample_in_input_schema_matches(self):
        s = json.loads((ROOT / ".actor" / "input_schema.json").read_text(encoding="utf-8"))
        self.assertEqual(s["properties"]["invoices"]["prefill"][0], batch.SAMPLE)


if __name__ == "__main__":
    unittest.main()
