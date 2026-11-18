"""Batch mode on Apify (a normal run, not Standby). Standard library only.

Why: Apify tests every public Actor once a day with its default input. A Standby-only server never writes a
result, so the test would fail and the Actor would be marked "under maintenance". In a normal run this module
checks the invoices given in the input (or one built-in sample when the input has none), writes one dataset
item per invoice and exits.

- Standby runs (APIFY_META_ORIGIN == "STANDBY") keep serving MCP over HTTP as before.
- Charged: one `invoice-checked` event per invoice from the input that was checked. The built-in sample is free.
- Input is read from the run's default key-value store (record INPUT); results go to the run's default dataset.
  Apify API: https://docs.apify.com/api/v2 . The token is read from the environment and never printed.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from . import __version__
from . import policy as _policy
from .check import check_invoice

API = "https://api.apify.com/v2"
MAX_INVOICES = 1000

# A correct sample (fictional names; the registration number has a valid check digit). Used when the input has no invoices.
SAMPLE = {
    "issuer": {"name": "株式会社サンプル商事", "registration_number": "T7123456789012"},
    "date": "2026-10-28",
    "buyer": {"name": "株式会社テスト"},
    "price_basis": "exclusive",
    "items": [{"description": "コピー用紙", "amount": 1999, "rate": 10},
              {"description": "※ お茶", "amount": 1234, "rate": 8, "reduced": True}],
    "totals": [{"rate": 10, "amount": 1999, "tax": 199}, {"rate": 8, "amount": 1234, "tax": 98}],
}


def is_standby():
    return os.environ.get("APIFY_META_ORIGIN") == "STANDBY"


def _call(method, url, token, payload=None, opener=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with (opener or urllib.request.urlopen)(req, timeout=30) as r:
        body = r.read()
    return json.loads(body.decode("utf-8")) if body else None


def read_input(token, opener=None):
    store = os.environ.get("ACTOR_DEFAULT_KEY_VALUE_STORE_ID")
    if not store:
        return {}
    try:
        return _call("GET", f"{API}/key-value-stores/{store}/records/INPUT", token, opener=opener) or {}
    except urllib.error.HTTPError as e:
        if e.code == 404:          # no input given
            return {}
        raise


def plan(inp):
    """[(invoice, is_sample)] from the input. Bad shapes raise ValueError before anything is charged."""
    inv = (inp or {}).get("invoices")
    if inv in (None, [], {}):
        return [(SAMPLE, True)]
    if isinstance(inv, dict):
        inv = [inv]
    if not isinstance(inv, list) or not all(isinstance(x, dict) for x in inv):
        raise ValueError("`invoices` must be a list of invoice objects (or one object)")
    if len(inv) > MAX_INVOICES:
        raise ValueError(f"at most {MAX_INVOICES} invoices per run (got {len(inv)})")
    return [(x, False) for x in inv]


def run(env=None, opener=None, charge=None):
    """Returns the list of dataset items written. Raises on errors (the run then shows as failed, not silently empty)."""
    env = env if env is not None else os.environ
    auth = env.get("APIFY_TOKEN")
    dataset = env.get("ACTOR_DEFAULT_DATASET_ID")
    if not auth or not dataset:
        raise RuntimeError("not inside an Apify run (APIFY_TOKEN / ACTOR_DEFAULT_DATASET_ID missing)")
    inp = read_input(auth, opener)
    pol = _policy.load(None)
    role = inp.get("role") if inp.get("role") in ("issue", "receive") else "issue"
    items = []
    for i, (inv, sample) in enumerate(plan(inp)):
        out = check_invoice(inv, policy=pol, role=role)
        out["index"] = i
        out["sample"] = sample
        out["checker"] = _policy.fingerprint(pol)
        out["version"] = __version__
        items.append(out)
    _call("POST", f"{API}/datasets/{dataset}/items", auth, items, opener)
    if charge:
        for it in items:
            if not it["sample"]:
                charge("invoice-checked", None)
    sys.stderr.write(f"jp-invoice-check {__version__}: checked {len(items)} invoice(s)"
                     + (" (built-in sample, not charged)" if items and items[0]["sample"] else "") + "\n")
    return items
