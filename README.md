# OpenFunnel Lookalikes — Rerank Wrapper + Benchmark Harness

Improve OpenFunnel's scores on the [openbenchmarks lookalike benchmark](https://openbenchmarks.com/lookalikes)
from the outside, using only their public API, and prove it by re-scoring with the
benchmark's own judge.

## The idea (one line)

Overfetch from OpenFunnel's API → drop the seed itself (hygiene) → drop agencies/consultants/
plugins via an LLM role classifier ("peer vs servicer") → rerank and backfill to exactly 100 →
grade old list vs new list with the official judge → before/after table.

## Cost discipline (IMPORTANT)

- `JUDGE_MODE=dev`  → judge runs on **DeepSeek** (cheap, ~free). Use for ALL iteration.
- `JUDGE_MODE=final` → judge runs on **gpt-5.4-mini** (the official benchmark judge).
  Use ONLY for the final certified runs that go in the report.
- Dev-judge numbers are directional only. They NEVER go in the report.
- The wrapper brain (facets/roles/rerank) is ALWAYS DeepSeek — a different model family
  from the final judge, so results can't be dismissed as "tuned against the grader."

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

Keys needed in `.env`:
- `OPENFUNNEL_API_KEY` — self-serve via Agent Auth (email OTP), 50k free credits, no card
- `DEEPSEEK_API_KEY`   — 5M free tokens on new accounts
- `OPENAI_API_KEY`     — only used when JUDGE_MODE=final

## Runbook

```bash
# 1. Download baseline data (candidates + judge verdicts + raw API envelopes)
python -m harness.download

# 2. Reproduce the published baseline with the DEV judge (sanity check, ~$0)
python -m harness.judge --seed veeva --list baseline

# 3. Run the wrapper pipeline on one seed
python -m wrapper.pipeline --seed veeva

# 4. Judge the wrapper output with the DEV judge, compare
python -m harness.judge --seed veeva --list wrapper
python -m harness.compare --seed veeva

# 5. Iterate on prompts/stages until dev numbers look right for all 7 seeds

# 6. FINAL certified run (costs ~$2 total): baseline + wrapper, 2 runs each
JUDGE_MODE=final python -m harness.judge --seed veeva --list baseline --runs 2
JUDGE_MODE=final python -m harness.judge --seed veeva --list wrapper  --runs 2
python -m harness.compare --all --mode final
```

## The 7 weak seeds

veeva (54%), shopify (68%), hubspot (67%), roto-rooter (74%), nubank (35%),
siemens (16%), sea-shopee (10%). Published scores = Precision@100, judge gpt-5.4-mini.

Failure analysis so far (from the benchmark's own judge rationales):
- shopify: 32 rejected — 18 Shopify agencies/service firms, ~7 ecosystem tools/plugins,
  2 duplicates of Shopify itself, rest scale/category.
- veeva: 46 rejected — 27 Veeva implementation consultancies, 3 self/subsidiary
  (ranks #1 AND #2 were veeva.com and Veeva APAC), rest infra providers/niche/scale.

Root cause: embeddings confuse "textually near" with "categorically same" — a Veeva
consultancy's website is ABOUT Veeva, so it embeds closer to Veeva than Veeva's real
competitors do. Fix = role judgment, which is what this wrapper adds.

## Layout

```
config.py            model + key config, dev/final judge switch
wrapper/
  facets.py          stage 0: single-business vs conglomerate → facet queries
  fetch.py           stage 1: overfetch K=250 from OpenFunnel API
  hygiene.py         stage 2: drop seed itself, subsidiaries, name variants, dupes
  roles.py           stage 3: LLM role classifier (peer/servicer/tool/unrelated)
  rerank.py          stage 4: score survivors, merge facets, backfill to 100
  pipeline.py        orchestrates stages 0-4, writes runs/<seed>/wrapper.json
harness/
  download.py        pulls baseline files from openbenchmarks-labs/lookalikes
  judge.py           judge replay (dev=DeepSeek / final=gpt-5.4-mini)
  compare.py         before/after Precision@10/50/100 table
prompts/             all LLM prompts live here as text files
data/                downloaded baselines (gitignored)
runs/                pipeline + judge outputs (gitignored)
```

## Integrity rules for the report

1. Final numbers only from the official judge (gpt-5.4-mini), 2 runs averaged, variance reported.
2. Wrapper models (DeepSeek) ≠ judge family (OpenAI). Stated explicitly.
3. Report added latency + credits/cost per query honestly.
4. Where the wrapper can't win (thin regional coverage: nubank, sea-shopee),
   say so — that's index-side work, not wrapper work.
