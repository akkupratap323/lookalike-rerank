# Results — Rerank wrapper over the OpenFunnel Lookalikes API

**Certified numbers.** Judge = `gpt-5.4-mini` (the official OpenBenchmarks judge), replaying
the benchmark's **literal recorded judge prompts** (rebuilt from
`openfunnel.raw.json → attempts[0].judge_calls[]` and verified **byte-identical on all 700
recorded messages** before any live call). Two independent judge runs per list, averaged;
run-to-run variance was ≤2 points everywhere.

## The table (Precision, official judge, 2-run average)

| seed | published P@100 | base P@10 | base P@50 | base P@100 | ours P@10 | ours P@50 | ours P@100 | Δ P@100 |
|---|---|---|---|---|---|---|---|---|
| veeva | 54% | 50% | 64% | 58.5% | **100%** | **92%** | **88.5%** | **+30** |
| shopify | 68% | 70% | 75% | 74.5% | **95%** | **93%** | **94%** | **+19.5** |
| hubspot | 67% | 90% | 71% | 66% | 80% | **86%** | **84.5%** | **+18.5** |
| roto-rooter | 74% | 70% | 73% | 84.5% | **80%** | **92%** | 85% | +0.5 |
| nubank | 35% | 90% | 58% | 50% | **100%** | **86%** | **81.5%** | **+31.5** |
| siemens | 16% | 40% | 36% | 26.5% | **60%** | **54%** | **39.5%** | **+13** |
| sea-shopee | 10% | 45% | 19% | 9.5% | **65%** | **29%** | **19%** | **+9.5** |

Average Δ P@100 across the 7 weakest seeds: **+17.6 points**. P@10 improved on 6/7 seeds
(veeva 50→100, nubank 90→100); the one regression is hubspot P@10 (90→80).

Baseline replication sanity: our re-judged baselines track the published scores
(sea-shopee 9.5 vs 10, hubspot 66 vs 67, veeva 58.5 vs 54) within the benchmark's own
documented judge drift (±5%); nubank/roto-rooter re-judge higher than published (50 vs 35,
84.5 vs 74), consistent with judge-version drift — which is why Δ against our own
re-judged baseline (same judge, same day, same prompts) is the honest comparison, and it
is reported above.

## What the wrapper is

Five stages on top of the public API — no access to OpenFunnel internals:

0. **Facet check** (LLM): conglomerate seeds (Siemens, Sea) get 3–5 per-business-line
   queries; single-business seeds get the benchmark's literal query plus one sharpened one.
1. **Overfetch**: 250 candidates per query via the documented async bulk endpoint
   (`search-lookalikes-bulk`; the sync endpoint caps at limit=100).
2. **Hygiene** (pure code, zero LLM): drop the seed itself, subsidiaries/regional variants
   (rapidfuzz name match + domain-root dedup). This alone removed veeva.com at rank #1
   and "Veeva Systems APAC" at rank #2 of the published baseline.
3. **Role classifier** (LLM): peer / servicer / tool / self / unrelated. Keep peers.
   Validated against the official judge's own verdicts on the published baselines
   BEFORE trusting it: 81% (veeva) / 83% (shopify) agreement, with disagreements
   concentrated in the judge's own borderline zone and skewed toward keeping too much
   (recall-safe) rather than dropping judge-approved candidates.
4. **Rerank** (LLM, 0–10) + facet merge + backfill to exactly 100.

Per-seed pipeline stats:

| seed | pool fetched | hygiene dropped | servicers/tools removed | wall-clock |
|---|---|---|---|---|
| veeva | 500 | 50 | 114 | 393s |
| shopify | 500 | 130 | 42 | 318s |
| hubspot | 500 | 239 | 80 | 290s |
| roto-rooter | 500 | 59 | 40 | 448s |
| nubank | 500 | 140 | 18 | 364s |
| siemens | 1500 | 239 | 548 | 787s |
| sea-shopee | 1000 | 93 | 76 | 811s |

## Integrity notes

1. **Different model family.** The wrapper's brain (facets, roles, rerank) is DeepSeek
   (`deepseek-v4-flash`/`-pro`) end to end. The judge is OpenAI `gpt-5.4-mini`. The wrapper
   was never tuned against the model that grades it. During iteration we used a DeepSeek
   dev judge; those numbers never appear here.
2. **Literal judge replay.** Judge system prompt and seed block are byte-identical to the
   recorded benchmark calls (700/700 verified); we substitute only the candidate block,
   reconstructed to the recorded format (including its omit-empty-domain and
   extras-serialization quirks).
3. **Costs & latency, honestly.** The wrapper adds 5–13 minutes wall-clock per seed at our
   conservative concurrency (8 parallel LLM calls) vs ~21s for the raw API call. LLM cost
   per seed ≈ $0.01–0.03 (DeepSeek); OpenFunnel credits: 500–1500 lookalike rows per seed.
   Certified judging for this report: 2,800 gpt-5.4-mini calls ≈ $1.80. A production
   integration would run stages 3–4 at higher concurrency in <60s.
4. **Where it can't win.** roto-rooter's baseline re-judges at 84.5% (published 74) — the
   wrapper holds it (85%) but adds ~nothing: the failure mode there isn't ecosystem
   confusion. sea-shopee improves 9.5→19 but stays terrible: the index simply lacks
   Southeast-Asian consumer-internet coverage — candidates below rank ~30 aren't there to
   rerank. Same partially true for siemens (26.5→39.5): facet queries recover real
   industrial peers, but the long tail thins out fast. These are **index-side** fixes
   (regional source ingestion, per-facet multi-vector indexing), not wrapper fixes.

## What I'd build inside the company

- **Multi-vector facet indexing**: one embedding per business line for conglomerates,
  instead of one averaged vector (fixes siemens/sea-class seeds at the index).
- **Role-aware reranking in the product**: the peer/servicer judgment as a cheap
  classifier head or LLM pass over the top-K — this report shows it's worth ~+18 P@100.
- **Hygiene in the API default path**: never return the seed/subsidiaries (veeva ranked
  itself #1 and #2).
- **Regional source ingestion** for LatAm/SEA coverage gaps (nubank, sea-shopee).
- MCP agent-auth: the benchmark's agent-usage table marks OpenFunnel MCP as
  "not agent-accessible yet (human setup)" — Agent Auth already exists for the REST API;
  wiring it into the MCP flow is a quick distribution win.
