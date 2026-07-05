"""Download baseline benchmark data for the weak seeds.

For each seed we pull:
- openfunnel.json      -> judged candidates (relevant flag + rationale) = baseline list
- openfunnel.raw.json  -> literal vendor HTTP envelope + literal judge prompts (for replay)
"""
import json
import os
import httpx

import config


def fetch(url: str) -> str:
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r.text


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    for seed in config.WEAK_SEEDS:
        seed_dir = os.path.join(config.DATA_DIR, seed)
        os.makedirs(seed_dir, exist_ok=True)
        for fname in ("openfunnel.json", "openfunnel.raw.json"):
            dest = os.path.join(seed_dir, fname)
            if os.path.exists(dest):
                print(f"skip (exists): {seed}/{fname}")
                continue
            url = f"{config.BENCH_RAW_BASE}/{seed}/{fname}"
            print(f"downloading {url}")
            open(dest, "w").write(fetch(url))
        d = json.load(open(os.path.join(seed_dir, "openfunnel.json")))
        print(
            f"  {seed}: published P@100={d['precision_at_100']} "
            f"(P@10={d['precision_at_10']}, P@50={d['precision_at_50']}), "
            f"judge={d['judge_model']}, candidates={len(d['candidates'])}"
        )


if __name__ == "__main__":
    main()
