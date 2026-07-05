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
    """Rebuild the literal judge messages from a recorded call.

    Verified shape (2026-07-05): raw["attempts"][0]["judge_calls"][*] =
    {model, messages:[system, user], raw_response, parsed_response, for_candidate_rank, ...}
    The system message and the user message's SEED block are byte-identical across
    all 100 calls, so we keep them verbatim and rebuild only the CANDIDATE block:

        CANDIDATE:
          name: <name>
          domain: <domain>
          description: <description>
          extras: {"linkedin_url": ..., "headquarters": ...}   # nulls dropped

    Returns (messages_template, note).
    """
    raw = _load_raw(seed)
    attempts = raw.get("attempts") or []
    judge_calls = (attempts[0].get("judge_calls") if attempts else None) or raw.get("judge_calls") or []
    if not judge_calls:
        raise RuntimeError(
            f"{seed}/openfunnel.raw.json has no attempts[0].judge_calls[]. "
            "Open the file, find where the judge messages live, and adapt "
            "extract_judge_template()."
        )
    messages = judge_calls[0]["messages"]
    system_msg = messages[0]["content"]
    user_msg = messages[1]["content"]
    if "CANDIDATE:" not in user_msg:
        raise RuntimeError(f"{seed}: recorded judge user message has no CANDIDATE: block")
    seed_block = user_msg.split("CANDIDATE:")[0]
    template = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": seed_block},  # candidate block appended at render time
    ]
    return template, "ok (rebuilt from attempts[0].judge_calls[0])"


def _candidate_block(cand: dict) -> str:
    """Byte-exact reconstruction of the benchmark's CANDIDATE block.
    Verified across all 7 seeds: the domain line is OMITTED when empty;
    extras = {linkedin_url, headquarters} with nulls dropped, never empty."""
    extra = cand.get("extra") or {}
    extras = {k: extra.get(k) for k in ("linkedin_url", "headquarters") if extra.get(k)}
    lines = ["CANDIDATE:", f"  name: {cand.get('name') or ''}"]
    if cand.get("domain"):
        lines.append(f"  domain: {cand['domain']}")
    lines.append(f"  description: {cand.get('description') or ''}")
    lines.append(f"  extras: {json.dumps(extras, ensure_ascii=False)}")
    return "\n".join(lines)


def render_judge_messages(template, cand: dict):
    system_msg, seed_block = template[0], template[1]
    return [
        system_msg,
        {"role": "user", "content": seed_block["content"] + _candidate_block(cand)},
    ]


def parse_verdict(reply: str) -> bool:
    """Recorded judge replies (verified): {"relevant": bool, "rationale": "..."}."""
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
    return "yes" in head or ("relevant" in head and "not relevant" not in head)


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
