"""Orchestrates stages 0-4 for one seed. Output: runs/<seed>/wrapper.json

Usage: python -m wrapper.pipeline --seed veeva
"""
import argparse
import asyncio
import json
import os
import time

import config
from wrapper import facets, fetch, hygiene, roles, rerank


def _seed_input(seed: str) -> dict:
    raw = json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.raw.json")))
    si = raw.get("seed_input", {})
    return {
        "name": si.get("seed_name", seed),
        "domain": si.get("seed_domain", ""),
        "desc": si.get("description", ""),
    }


async def run(seed: str):
    t0 = time.time()
    s = _seed_input(seed)
    report = {"seed": seed, "seed_input": s, "stages": {}}

    # stage 0: facet check
    f = await facets.facet_queries(s["name"], s["domain"], s["desc"])
    queries = f["queries"]
    report["stages"]["facets"] = f
    print(f"[0] facets: multi={f.get('multi_business')} queries={len(queries)}")

    # stage 1: overfetch (per facet query)
    pool = []
    for q in queries:
        got = fetch.search_lookalikes(q, k=config.OVERFETCH_K)
        for c in got:
            c["facet_query"] = q
        pool.extend(got)
        print(f"[1] fetched {len(got)} for query: {q[:60]}")
    report["stages"]["fetched"] = len(pool)

    # stage 2: hygiene
    kept, dropped = hygiene.hygiene_filter(pool, s["name"], s["domain"])
    report["stages"]["hygiene"] = {"kept": len(kept), "dropped": len(dropped),
                                   "dropped_examples": dropped[:5]}
    print(f"[2] hygiene: kept {len(kept)}, dropped {len(dropped)}")

    # stage 3: roles
    kept = await roles.classify_roles(kept, s["name"], s["domain"], s["desc"])
    peers = [c for c in kept if c["role"] == "peer"]
    from collections import Counter
    report["stages"]["roles"] = dict(Counter(c["role"] for c in kept))
    print(f"[3] roles: {report['stages']['roles']} -> {len(peers)} peers")
    if len(peers) < config.FINAL_K:
        print(f"[3] WARNING: only {len(peers)} peers (<{config.FINAL_K}). "
              f"Backfilling with best 'unrelated' by source rank.")
        filler = [c for c in kept if c["role"] == "unrelated"]
        peers = peers + filler[: config.FINAL_K - len(peers)]

    # stage 4: rerank -> final 100
    final = await rerank.rerank(peers, s["name"], s["domain"], s["desc"])
    report["stages"]["final_count"] = len(final)
    report["latency_s"] = round(time.time() - t0, 1)
    report["candidates"] = final

    out_dir = os.path.join(config.RUNS_DIR, seed)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "wrapper.json")
    json.dump(report, open(out, "w"), indent=2)
    print(f"[4] wrote {len(final)} candidates -> {out}  ({report['latency_s']}s total)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True, choices=list(config.WEAK_SEEDS))
    a = ap.parse_args()
    asyncio.run(run(a.seed))
