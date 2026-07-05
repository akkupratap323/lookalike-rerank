# Failure taxonomy — why embedding lookalikes miss, seed by seed

Method: every rejected candidate in the published benchmark run
(`openfunnel.json`, judge `gpt-5.4-mini`) categorized from the judge's own one-line
rationale — keyword bucketing over all 7 seeds, hand-verified samples per seed.

## Rejection counts by category (of 100 judged candidates per seed)

| seed | rejected | servicer/agency | self/dupe | scale | narrow/niche | diff. category | B2B-inversion & other |
|---|---|---|---|---|---|---|---|
| veeva | 46 | 22 | 3 | 11 | 3 | — | 7 |
| shopify | 32 | 15 | 2 (+2 tools) | 3 | 1 | 1 | 8 |
| hubspot | 33 | 24 | 1 | 2 | 3 | — | 3 |
| roto-rooter | 26 | 1 | 11 | 2 | 2 | 3 | 7 |
| nubank | 65 | 3 | — | 7 | — | 8 | 47 |
| siemens | 84 | 38 | — | 21 | 4 | — | 21 |
| sea-shopee | 90 | 17 | 1 | 27 | 1 | 12 | 32 |

## The four distinct diseases

**1. Ecosystem confusion (veeva, hubspot, shopify, siemens).** Agencies, consultancies and
implementation partners describe themselves in the seed's own vocabulary, so they embed
closer to the seed than the seed's real competitors do. Veeva: 22/46 rejects are Veeva
consultancies; hubspot: 24/33 are marketing/CRM agencies; siemens: 38/84 are industrial
engineering-services firms. **Wrapper fixes this** — it's a role judgment ("similar to X"
vs "works with X") that geometry can't make. Certified gains: veeva +30, hubspot +18.5,
shopify +19.5.

**2. Self-retrieval (veeva, roto-rooter).** The seed, its subsidiaries and regional
variants outrank everything (veeva.com was rank #1 AND #2; roto-rooter: 11/26 rejects are
Roto-Rooter franchises/duplicates). **Fixed by pure code** (hygiene stage, zero LLM cost).

**3. B2B/B2C audience inversion (nubank — the dominant mode, 47/65).** The judge's
rationales are near-uniform: "banking software vendor serving banks, not a consumer
digital bank". Embeddings can't distinguish *being* a digital bank from *selling to*
digital banks — same words, inverted buyer. This is the same role-judgment failure as
ecosystem confusion, one level up. **Wrapper fixes most of it**: nubank +31.5 (50→81.5).

**4. Coverage + facet blur (sea-shopee, siemens).** Sea and Siemens are multi-business
companies whose single averaged embedding matches nothing well; and the index thins out
for Southeast-Asia consumer internet (sea-shopee scale/geography rejects: 27+12).
Facet queries recover what exists (+13 siemens, +9.5 sea-shopee) but **the wrapper cannot
invent index coverage** — candidates that aren't in the top ~1000 can't be reranked into
the top 100. This is index-side work: regional source ingestion and per-facet
multi-vector indexing.

## Root cause, one sentence

Embeddings measure *textual closeness*; the benchmark's judge measures *categorical
sameness* — and the gap between the two is exactly the set of companies whose text is
about the seed's world without being the seed's kind of company (servicers, tools,
suppliers-to-the-category, and the seed itself).
