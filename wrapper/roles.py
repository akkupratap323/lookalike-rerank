"""Stage 3: LLM role classifier — peer / servicer / tool / self / unrelated.

Also provides `validate_against_judge()`: runs the classifier over the BASELINE
candidates (which already carry the official judge's verdicts) and reports agreement.
Run that first — it turns "I picked DeepSeek" into "validated at X% agreement".
"""
import asyncio
import json
import os

import config
import llm


def _load_prompt(seed_name, seed_domain, seed_desc):
    p = open(os.path.join(config.PROMPTS_DIR, "role_classifier.txt")).read()
    return (p.replace("{{SEED_NAME}}", seed_name)
             .replace("{{SEED_DOMAIN}}", seed_domain)
             .replace("{{SEED_DESC}}", seed_desc))


def _render(batch):
    # NOTE: show the classifier the same evidence the judge sees (name/domain/description).
    # Feeding employee_count was tried and HURT agreement (71%->63%): the judge never sees
    # size data and happily accepts tiny same-category vendors.
    lines = []
    for i, c in enumerate(batch):
        desc = (c.get("description") or "")[:400]
        lines.append(f'{i}. {c.get("name","?")} ({c.get("domain","?")}) — {desc}')
    return "\n".join(lines)


async def classify_roles(candidates, seed_name, seed_domain, seed_desc):
    client = llm.deepseek_client()
    prompt = _load_prompt(seed_name, seed_domain, seed_desc)
    rows = await llm.map_batches(client, config.WRAPPER_FAST_MODEL, prompt,
                                 candidates, config.ROLE_BATCH_SIZE, _render)
    for c, r in zip(candidates, rows):
        c["role"] = r.get("role", "unrelated")
        c["role_why"] = r.get("why", "")
    return candidates


def _enrich_from_raw(cands: list, raw: dict) -> list:
    """Baseline candidates only carry linkedin/hq; join the raw vendor response by
    domain+name to add employee_count/revenue/industries (same data the wrapper sees)."""
    results = (raw.get("attempts") or [{}])[0].get("vendor_calls", [{}])[0] \
        .get("response_body", {}).get("results", []) or []
    by_key = {(r.get("domain") or "", r.get("name") or ""): r for r in results}
    out = []
    for c in cands:
        r = by_key.get((c.get("domain") or "", c.get("name") or ""))
        extra = dict(c.get("extra") or {})
        if r:
            for k in ("employee_count", "revenue_usd", "funding_stage", "industries"):
                extra.setdefault(k, r.get(k))
        out.append({**c, "extra": extra})
    return out


async def validate_against_judge(seed: str):
    """Agreement check on baseline: judge said relevant<->we say peer?"""
    base = json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.json")))
    bjson = json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.raw.json")))
    si = bjson.get("seed_input", {})
    cands = _enrich_from_raw([dict(c) for c in base["candidates"]], bjson)
    cands = await classify_roles(cands, si.get("seed_name", seed),
                                 si.get("seed_domain", ""), si.get("description", ""))
    agree = sum(1 for c in cands if (c["role"] == "peer") == bool(c["relevant"]))
    n = len(cands)
    print(f"{seed}: classifier-vs-judge agreement {agree}/{n} = {100*agree/n:.0f}%")
    disagreements = [c for c in cands if (c["role"] == "peer") != bool(c["relevant"])]
    for c in disagreements[:10]:
        print(f"  judge={'REL' if c['relevant'] else 'rej'} us={c['role']:9s} "
              f"{c['name']}: {c['role_why'][:80]}")
    return agree / n


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", required=True, choices=list(config.WEAK_SEEDS))
    a = ap.parse_args()
    asyncio.run(validate_against_judge(a.validate))
