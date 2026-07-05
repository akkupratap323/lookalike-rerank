"""Judge replay.

Grades a candidate list (baseline or wrapper) with the benchmark's judge.
- JUDGE_MODE=dev   -> DeepSeek (cheap iteration, directional only)
- JUDGE_MODE=final -> gpt-5.4-mini (official; report numbers)

The judge prompt is extracted from the benchmark's own raw.json (judge_calls[].messages),
so we replay the LITERAL official rubric — we substitute only the candidate fields.
"""
import argparse
import asyncio
import json
import os
import statistics

import config
import llm


# ---------- judge template extraction ----------

def _load_raw(seed: str) -> dict:
    return json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.raw.json")))


def _load_baseline(seed: str) -> dict:
    return json.load(open(os.path.join(config.DATA_DIR, seed, "openfunnel.json")))


def extract_judge_template(seed: str):
    """Take one recorded judge call and turn it into a template by replacing that
    call's candidate name/domain/description with placeholders.

    Returns (messages_template, note). Raises with a clear message if the raw file
    doesn't contain judge_calls — in that case inspect the file and adapt here.
    """
    raw = _load_raw(seed)
    judge_calls = raw.get("judge_calls") or []
    if not judge_calls:
        raise RuntimeError(
            f"{seed}/openfunnel.raw.json has no judge_calls[]. "
            "Open the file, find where the judge messages live, and adapt "
            "extract_judge_template()."
        )
    call = judge_calls[0]
    cand = call.get("candidate") or {}
    messages = call["messages"]
    baseline = _load_baseline(seed)
    if not cand:  # fall back: identify the candidate by matching rank-1 fields
        cand = baseline["candidates"][0]

    def templ(text: str) -> str:
        for key, ph in (("name", "{{CAND_NAME}}"), ("domain", "{{CAND_DOMAIN}}"),
                        ("description", "{{CAND_DESC}}")):
            val = (cand.get(key) or "").strip()
            if val:
                text = text.replace(val, ph)
        return text

    template = [{"role": m["role"], "content": templ(m["content"])} for m in messages]
    joined = "".join(m["content"] for m in template)
    missing = [p for p in ("{{CAND_NAME}}",) if p not in joined]
    note = "ok" if not missing else f"WARNING: placeholders not found: {missing}"
    return template, note


def render_judge_messages(template, cand: dict):
    return [
        {
            "role": m["role"],
            "content": m["content"]
            .replace("{{CAND_NAME}}", cand.get("name") or "")
            .replace("{{CAND_DOMAIN}}", cand.get("domain") or "")
            .replace("{{CAND_DESC}}", cand.get("description") or ""),
        }
        for m in template
    ]


def parse_verdict(reply: str) -> bool:
    """Benchmark judge returns a binary relevance label + rationale.
    Adapt once you see the literal recorded reply format in raw.json."""
    try:
        obj = llm.extract_json(reply)
        if isinstance(obj, dict):
            for k in ("relevant", "label", "verdict"):
                if k in obj:
                    v = obj[k]
                    return v if isinstance(v, bool) else str(v).lower() in ("yes", "true", "relevant", "1")
    except Exception:
        pass
    head = reply.strip().lower()[:80]
    return "yes" in head or "relevant" in head and "not relevant" not in head


# ---------- scoring ----------

def precision_at(cands: list, k: int) -> float:
    top = cands[:k]
    return 100.0 * sum(1 for c in top if c["relevant"]) / k


async def judge_list(seed: str, which: str, runs: int = 1) -> dict:
    jc = config.judge_config()
    client = llm.judge_client()
    template, note = extract_judge_template(seed)
    print(f"judge template: {note} | mode={jc.label} model={jc.model}")

    if which == "baseline":
        cands = _load_baseline(seed)["candidates"]
    else:
        path = os.path.join(config.RUNS_DIR, seed, "wrapper.json")
        cands = json.load(open(path))["candidates"]

    sem = asyncio.Semaphore(config.CONCURRENCY)

    async def judge_one(c):
        async with sem:
            reply = await llm.chat(client, jc.model, render_judge_messages(template, c))
            return {**c, "relevant": parse_verdict(reply), "judge_reply": reply[:300]}

    run_scores = []
    judged = None
    for r in range(runs):
        judged = await asyncio.gather(*[judge_one(c) for c in cands])
        judged = sorted(judged, key=lambda c: c["rank"])
        scores = {f"P@{k}": precision_at(judged, k) for k in (10, 50, 100)}
        run_scores.append(scores)
        print(f"  run {r+1}: {scores}")

    avg = {k: round(statistics.mean(s[k] for s in run_scores), 1) for k in run_scores[0]}
    result = {
        "seed": seed, "list": which, "judge_mode": jc.label, "judge_model": jc.model,
        "runs": run_scores, "avg": avg, "candidates": judged,
    }
    out_dir = os.path.join(config.RUNS_DIR, seed)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"judged_{which}_{jc.label}.json")
    json.dump(result, open(out, "w"), indent=2)
    print(f"avg: {avg}  -> {out}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True, choices=list(config.WEAK_SEEDS))
    ap.add_argument("--list", required=True, choices=["baseline", "wrapper"])
    ap.add_argument("--runs", type=int, default=1)
    a = ap.parse_args()
    asyncio.run(judge_list(a.seed, a.list, a.runs))
