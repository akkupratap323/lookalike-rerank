# Lookalike Rerank

**A reasoning layer for embedding-based company search. +17.6 points average Precision@100
on the 7 hardest seeds of a public benchmark, certified by byte-exact replay of the
benchmark's own LLM judge. Fully reproducible for under $5.**

Built on the [OpenFunnel](https://openfunnel.dev) Lookalikes API (the overall leader on
[OpenBenchmarks' lookalike benchmark](https://openbenchmarks.com/lookalikes)) — using only
the public API, from outside the company. The failure modes addressed here are inherent to
*any* pure-embedding lookalike system, not specific to one vendor.

## Results

Official judge (`gpt-5.4-mini`), two independent runs averaged, run-to-run variance ≤2 points.

| seed | base P@100 | ours P@100 | Δ P@100 | ours P@10 |
|---|---|---|---|---|
| veeva | 58.5% | **88.5%** | **+30.0** | **100%** (was 50) |
| nubank | 50.0% | **81.5%** | **+31.5** | **100%** |
| shopify | 74.5% | **94.0%** | **+19.5** | 95% |
| hubspot | 66.0% | **84.5%** | **+18.5** | 80% |
| siemens | 26.5% | **39.5%** | **+13.0** | 60% |
| sea-shopee | 9.5% | **19.0%** | **+9.5** | 65% |
| roto-rooter | 84.5% | 85.0% | +0.5 | 80% |

Full table with P@50, pipeline stats, and per-seed wall-clock: [`report/results.md`](report/results.md)

## The one-sentence insight

**Embeddings measure textual closeness, not categorical sameness.** A consultancy that
deploys a product describes itself in that product's own words, so it embeds *closer* to
the product than the product's actual competitors do. Geometry cannot distinguish
"competes with X" from "works with X" — a role judgment that this wrapper adds.

Evidence: all 700 judge rationales on the 7 weakest seeds, bucketed into four failure
modes (ecosystem confusion, self-retrieval, B2B/B2C audience inversion, coverage/facet
blur) in [`report/taxonomy.md`](report/taxonomy.md).

## How it works

```
seed ──► 0. facet check          conglomerate? split into 3–5 per-business-line queries
     ──► 1. overfetch            250 candidates per query (bulk endpoint) — the good
                                 candidates already exist at ranks 100–250, just buried
     ──► 2. hygiene filter       pure code: drop the seed itself, subsidiaries, name
                                 variants, duplicate domains (zero LLM cost)
     ──► 3. role classifier      one LLM question per candidate: peer / servicer / tool /
                                 self / unrelated — keep peers
     ──► 4. rerank + backfill    score survivors 0–10, merge facets, cut to exactly 100
     ──► 5. judge replay         re-score old list vs new list with the benchmark's
                                 literal recorded judge prompts
```

The role classifier was **validated before being trusted**: run over the published
baselines and compared against the official judge's own verdicts — 81–83% agreement,
with disagreements concentrated in the judge's borderline zone and skewed recall-safe.

## Reproduce it (3 commands, <$5)

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env   # add your own OpenFunnel (free 50k credits), DeepSeek, OpenAI keys

python -m harness.download                                        # 1. baselines + raw judge prompts
python -m wrapper.pipeline --seed veeva                           # 2. run the wrapper
JUDGE_MODE=final python -m harness.judge --seed veeva --list wrapper --runs 2   # 3. certify
```

Then `python -m harness.compare --seed veeva` prints the before/after table.

Iterate cheaply: `JUDGE_MODE=dev` routes the judge to DeepSeek (~free). Dev-judge numbers
are directional only and never appear in the report — certified numbers come exclusively
from the official judge model.

## Integrity notes

1. **No tuning against the grader.** The wrapper's brain (facet check, role classifier,
   reranker) runs on DeepSeek end to end; the judge is OpenAI `gpt-5.4-mini`. Different
   model families.
2. **Literal judge replay.** The judge's system prompt and seed block are byte-identical
   to the benchmark's recorded calls — verified across all 700 recorded messages — with
   only the candidate block substituted, reconstructed to the recorded format exactly.
3. **Drift-honest baselines.** The public judge has drifted since the benchmark's June
   snapshot (three seeds re-judge above their published scores). All deltas here are against
   same-day re-judged baselines — same judge, same prompts, same day — which makes the
   improvements *conservative* relative to published numbers.
4. **Failures reported.** One P@10 regression (hubspot, 90→80) is in the results table.
   A negative result worth knowing: giving the classifier `employee_count` *hurt*
   judge-agreement (71%→63%) — the judge never sees size data. And where the wrapper
   can't win (sea-shopee, siemens long tail), the limit is index coverage, not ranking;
   that's index-side work, honestly out of scope for a wrapper.

## Costs & latency, honestly

| item | cost |
|---|---|
| Wrapper LLM calls (DeepSeek), per seed | ~$0.01–0.03 |
| Certified judging, whole report (2,800 gpt-5.4-mini calls) | ~$1.80 |
| OpenFunnel credits | free tier (50k) |
| Wall-clock per seed at concurrency 8 | 5–13 min (raw API: ~21s) — a production integration would run stages 3–4 at higher concurrency in <60s |

## Layout

```
config.py          models, keys, JUDGE_MODE switch, pipeline knobs
llm.py             async OpenAI-compatible client, batching, retries
wrapper/           the 5 pipeline stages (facets, fetch, hygiene, roles, rerank, pipeline)
harness/           download baselines, judge replay, before/after comparison
prompts/           all LLM prompts, with few-shot examples drawn from real judge verdicts
report/            results.md (certified numbers) · taxonomy.md (700-rationale failure analysis)
```

## Credit

[OpenFunnel](https://openfunnel.dev)'s agent-self-serve API (email-OTP key, free credits,
no dashboard required) made building on it possible in an afternoon, and
[OpenBenchmarks](https://openbenchmarks.com)' radical reproducibility — literal HTTP
envelopes and judge prompts published per cell — is what made outside verification
possible at all. More vendors should ship this way.

---

*Built by [Aditya Pratap Singh](https://github.com/akkupratap323) ·
[saientai.xyz](https://saientai.xyz)*
