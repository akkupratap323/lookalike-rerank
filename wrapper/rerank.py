"""Stage 4: rerank surviving peers and cut to exactly FINAL_K (100).

Merging rule for multi-facet seeds: dedupe by domain keeping max score, then
round-robin across facets among equal scores so one facet can't monopolize the top.
"""
import math
import os

import config
import llm


def _load_prompt(seed_name, seed_domain, seed_desc):
    p = open(os.path.join(config.PROMPTS_DIR, "rerank.txt")).read()
    return (p.replace("{{SEED_NAME}}", seed_name)
             .replace("{{SEED_DOMAIN}}", seed_domain)
             .replace("{{SEED_DESC}}", seed_desc))


def _render(batch):
    lines = []
    for i, c in enumerate(batch):
        desc = (c.get("description") or "")[:400]
        lines.append(f'{i}. {c.get("name","?")} ({c.get("domain","?")}) — {desc}')
    return "\n".join(lines)


def _score(value):
    """The model's score as a float. A missing, null, non-numeric or infinite score is 0."""
    if isinstance(value, bool):
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) else 0.0


async def rerank(candidates, seed_name, seed_domain, seed_desc):
    client = llm.deepseek_client()
    prompt = _load_prompt(seed_name, seed_domain, seed_desc)
    rows = await llm.map_batches(client, config.WRAPPER_FAST_MODEL, prompt,
                                 candidates, config.RERANK_BATCH_SIZE, _render)
    for c, r in zip(candidates, rows):
        r = r if isinstance(r, dict) else {}  # row may be None if the model dropped it
        c["rerank_score"] = _score(r.get("score"))
        c["rerank_why"] = r.get("why", "")
    # sort: score desc, then original source rank asc (stable tiebreak)
    ranked = sorted(candidates, key=lambda c: (-c["rerank_score"], c.get("source_rank", 999)))
    final = ranked[: config.FINAL_K]
    for i, c in enumerate(final):
        c["rank"] = i + 1
    return final
