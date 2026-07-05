"""Stage 1: overfetch candidates from the OpenFunnel lookalikes API.

Request shape VERIFIED against data/<seed>/openfunnel.raw.json attempts[0].vendor_calls[0]:
  GET /api/v1/account/search-lookalikes
  params: query="Companies most similar to <Name>: <description>", limit=100,
          search_type=semantic
  headers: X-API-Key

The sync endpoint caps limit at 100 (verified live: 422 above 100, no pagination).
For OVERFETCH_K > 100 we use the documented async bulk endpoint:
  POST /api/v1/account/search-lookalikes-bulk  {query, limit}  -> {job_id}
  GET  /api/v1/account/search-lookalikes-bulk/{job_id}         -> poll status, page cursor
"""
import argparse
import json
import os
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

import config

ENDPOINT = "/api/v1/account/search-lookalikes"  # verified from recorded vendor_calls
ENDPOINT_BULK = "/api/v1/account/search-lookalikes-bulk"
SYNC_MAX_LIMIT = 100
BULK_POLL_S = 4
BULK_TIMEOUT_S = 600


def benchmark_query(seed_name: str, seed_desc: str) -> str:
    """The literal query template the benchmark used (from recorded vendor_calls)."""
    return f"Companies most similar to {seed_name}: {seed_desc}"


def _headers() -> dict:
    return {"X-API-Key": config.OPENFUNNEL_API_KEY}


def _normalize(items: list) -> list:
    out = []
    for i, it in enumerate(items):
        out.append({
            "name": it.get("name") or it.get("company_name") or "",
            "domain": it.get("domain") or it.get("website") or "",
            # the benchmark judges on match_reason (verified: extracted_candidates
            # description == vendor match_reason), so replicate that mapping
            "description": it.get("match_reason") or it.get("description") or "",
            "source_rank": i + 1,
            "extra": it,
        })
    return out


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _search_sync(query: str, k: int) -> list:
    params = {"query": query, "limit": k, "search_type": "semantic"}  # verified
    with httpx.Client(base_url=config.OPENFUNNEL_BASE_URL, timeout=120) as cli:
        r = cli.get(ENDPOINT, params=params, headers=_headers())
        r.raise_for_status()
        data = r.json()
    return data.get("results") or data.get("companies") or data.get("data") or []


def _search_bulk(query: str, k: int) -> list:
    """Async bulk flow (shape verified live): submit -> {job_id}; poll GET returns
    {status, rows, page, next_cursor, ...}. Rows stream in while running, so we wait
    for status=completed FIRST, then walk the cursor chain once to collect pages."""
    with httpx.Client(base_url=config.OPENFUNNEL_BASE_URL, timeout=120) as cli:
        r = cli.post(ENDPOINT_BULK, json={"query": query, "limit": k}, headers=_headers())
        r.raise_for_status()
        job_id = r.json()["job_id"]

        deadline = time.time() + BULK_TIMEOUT_S
        while True:  # phase 1: wait for completion
            r = cli.get(f"{ENDPOINT_BULK}/{job_id}", headers=_headers())
            r.raise_for_status()
            status = r.json().get("status")
            if status == "completed":
                break
            if status in ("failed", "cancelled"):
                raise RuntimeError(f"bulk job {job_id} status={status}: "
                                   f"{r.json().get('error_message')}")
            if time.time() > deadline:
                raise TimeoutError(f"bulk job {job_id} not completed in {BULK_TIMEOUT_S}s")
            time.sleep(BULK_POLL_S)

        results, cursor = [], None
        while True:  # phase 2: page through results
            params = {"cursor": cursor} if cursor else {}
            r = cli.get(f"{ENDPOINT_BULK}/{job_id}", params=params, headers=_headers())
            r.raise_for_status()
            data = r.json()
            results.extend(data.get("rows") or [])
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return results[:k]


def search_lookalikes(query: str, k: int = config.OVERFETCH_K) -> list:
    """One lookalikes query -> list of candidate dicts (name/domain/description/extra)."""
    if k <= SYNC_MAX_LIMIT:
        items = _search_sync(query, k)
    else:
        items = _search_bulk(query, k)
    return _normalize(items)


def show_envelope(seed: str):
    raw = json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.raw.json")))
    attempts = raw.get("attempts") or []
    calls = (attempts[0].get("vendor_calls") if attempts else None) or raw.get("vendor_calls") or []
    if not calls:
        print("no vendor_calls[] found — inspect the raw file manually")
        print("top-level keys:", list(raw.keys()))
        return
    c = calls[0]
    print(json.dumps({k: c.get(k) for k in ("method", "url", "request_headers", "request_body")},
                     indent=2)[:3000])


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
