"""Before/after comparison table.

Usage:
  python -m harness.compare --seed veeva            # one seed, dev-judge results
  python -m harness.compare --all --mode final      # the report table
"""
import argparse
import json
import os

from tabulate import tabulate

import config


def _load(seed, which, mode):
    p = os.path.join(config.RUNS_DIR, seed, f"judged_{which}_{mode}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--mode", default="dev", choices=["dev", "final"])
    a = ap.parse_args()
    seeds = list(config.WEAK_SEEDS) if a.all else [a.seed]

    rows = []
    for seed in seeds:
        pub = config.WEAK_SEEDS[seed]
        base = _load(seed, "baseline", a.mode)
        wrap = _load(seed, "wrapper", a.mode)
        row = [seed, f"{pub:.0f}%"]
        for res in (base, wrap):
            if res:
                row += [f"{res['avg']['P@10']:.0f}%", f"{res['avg']['P@50']:.0f}%",
                        f"{res['avg']['P@100']:.0f}%"]
            else:
                row += ["-", "-", "-"]
        if base and wrap:
            row.append(f"{wrap['avg']['P@100'] - base['avg']['P@100']:+.0f}")
        else:
            row.append("-")
        rows.append(row)

    headers = ["seed", "published", "base P@10", "base P@50", "base P@100",
               "ours P@10", "ours P@50", "ours P@100", "Δ P@100"]
    print(f"\njudge mode: {a.mode}"
          + ("  (DIRECTIONAL ONLY — not for the report)" if a.mode == "dev" else ""))
    print(tabulate(rows, headers=headers, tablefmt="github"))


if __name__ == "__main__":
    main()
