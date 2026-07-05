"""Stage 1: overfetch candidates from the OpenFunnel lookalikes API.

IMPORTANT before first run:
The literal request the benchmark sent is recorded in data/<seed>/openfunnel.raw.json
under vendor_calls[] (endpoint, params, headers minus auth). Run
`python -m wrapper.fetch --show-envelope --seed veeva` to print it, then align
ENDPOINT/params here so our calls match the benchmark's exactly (apart from k).
"""
import argparse
import json
import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

import config

ENDPOINT = "/api/v1/account/search-lookalikes"  # from benchmark agent-usage table


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def search_lookalikes(query: str, k: int = config.OVERFETCH_K) -> list:
    """One lookalikes query -> list of candidate dicts (name/domain/description/extra)."""
    headers = {"X-API-Key": config.OPENFUNNEL_API_KEY}
    params = {"query": query, "limit": k}  # confirm param names against raw envelope/docs
    with httpx.Client(base_url=config.OPENFUNNEL_BASE_URL, timeout=120) as cli:
        r = cli.get(ENDPOINT, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
    items = data.get("results") or data.get("companies") or data.get("data") or []
    out = []
    for i, it in enumerate(items):
        out.append({
            "name": it.get("name") or it.get("company_name") or "",
            "domain": it.get("domain") or it.get("website") or "",
            "description": it.get("description") or it.get("match_reason") or "",
            "source_rank": i + 1,
            "extra": it,
        })
    return out


def show_envelope(seed: str):
    raw = json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.raw.json")))
    calls = raw.get("vendor_calls") or []
    if not calls:
        print("no vendor_calls[] found — inspect the raw file manually")
        print("top-level keys:", list(raw.keys()))
        return
    c = calls[0]
    print(json.dumps({k: c.get(k) for k in ("method", "url", "params", "body")}, indent=2)[:3000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-envelope", action="store_true")
    ap.add_argument("--seed", default="veeva")
    ap.add_argument("--query", help="run a live test query")
    a = ap.parse_args()
    if a.show_envelope:
        show_envelope(a.seed)
    elif a.query:
        res = search_lookalikes(a.query, k=10)
        print(json.dumps(res[:5], indent=2)[:2000], f"\n... {len(res)} results")
