"""Stage 2: deterministic hygiene filter. Pure code, zero LLM cost.

Drops: the seed itself, subsidiaries/regional variants, name near-duplicates,
domain duplicates. This alone fixes Veeva's poisoned ranks #1-#2.
"""
import re
from urllib.parse import urlsplit

from rapidfuzz import fuzz

# Registries that sell names one level down, e.g. acme.co.uk, acme.com.au.
_SECOND_LEVEL_SUFFIXES = {"ac", "co", "com", "edu", "gov", "ne", "net", "or", "org"}
_NAME_JUNK = {"inc", "llc", "ltd", "gmbh", "corp", "corporation",
              "systems", "technologies", "solutions"}


def _root(domain: str) -> str:
    d = (domain or "").lower().strip()
    try:
        host = urlsplit(d if "//" in d else f"//{d}").hostname or ""
    except ValueError:
        return ""
    parts = host.removeprefix("www.").split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL_SUFFIXES:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


def _norm_name(name: str) -> str:
    n = (name or "").lower().replace("k.k", " ")
    return " ".join(w for w in re.split(r"[,.\s]+", n) if w and w not in _NAME_JUNK)


def is_self(cand: dict, seed_name: str, seed_domain: str) -> bool:
    seed_root = _root(seed_domain)
    cand_root = _root(cand.get("domain") or "")
    if cand_root and cand_root == seed_root:
        return True
    sn, cn = _norm_name(seed_name), _norm_name(cand.get("name") or "")
    if not cn:
        return False
    # "Veeva Systems APAC" vs "Veeva" / "Shopify B2B E-Commerce" vs "Shopify"
    if sn and (cn.startswith(sn + " ") or cn == sn or fuzz.ratio(sn, cn) >= 90):
        return True
    return False


def hygiene_filter(candidates: list, seed_name: str, seed_domain: str) -> tuple[list, list]:
    """Returns (kept, dropped_with_reason)."""
    kept, dropped, seen_domains = [], [], set()
    for c in candidates:
        root = _root(c.get("domain") or "") or _norm_name(c.get("name") or "")
        if is_self(c, seed_name, seed_domain):
            dropped.append({**c, "drop_reason": "self/subsidiary/variant"})
        elif root in seen_domains:
            dropped.append({**c, "drop_reason": "duplicate domain"})
        else:
            seen_domains.add(root)
            kept.append(c)
    return kept, dropped
