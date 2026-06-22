"""Fuzzy product matching: link NokNok products to competitor products.

Strategy:
  1. Normalize each product into a comparable key (brand + name + size).
  2. For each NokNok product, score every competitor product with
     rapidfuzz token-set ratio (order-independent), with bonuses for
     matching brand and size.
  3. Keep the best competitor match per (noknok product, competitor)
     above a confidence threshold.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

DEFAULT_THRESHOLD = 72.0  # 0-100; below this we don't auto-link

_STOPWORDS = {"the", "of", "with", "fresh", "pack", "value", "size"}
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def normalize(name: str, brand: str | None = None, size: str | None = None) -> str:
    """Produce a normalized matching key from a product's fields."""
    parts = " ".join(p for p in (brand or "", name or "", size or "") if p)
    text = parts.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    tokens = [t for t in text.split() if t not in _STOPWORDS]
    return " ".join(tokens)


@dataclass
class MatchCandidate:
    base_external_id: str
    competitor_external_id: str
    score: float


def score_pair(
    a_key: str,
    b_key: str,
    a_brand: str | None = None,
    b_brand: str | None = None,
    a_size: str | None = None,
    b_size: str | None = None,
) -> float:
    """Composite 0-100 similarity score for two products."""
    base = fuzz.token_set_ratio(a_key, b_key)
    bonus = 0.0
    if a_brand and b_brand and a_brand.lower() == b_brand.lower():
        bonus += 6
    if a_size and b_size and a_size.lower().replace(" ", "") == b_size.lower().replace(" ", ""):
        bonus += 8
    return min(100.0, base + bonus)


def best_matches(
    base_products: list[dict],
    competitor_products: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[MatchCandidate]:
    """For each base product, find the single best competitor product.

    Each dict needs: external_id, norm_key, brand, size.
    """
    results: list[MatchCandidate] = []
    for bp in base_products:
        best: MatchCandidate | None = None
        for cp in competitor_products:
            s = score_pair(
                bp["norm_key"], cp["norm_key"],
                bp.get("brand"), cp.get("brand"),
                bp.get("size"), cp.get("size"),
            )
            if best is None or s > best.score:
                best = MatchCandidate(bp["external_id"], cp["external_id"], s)
        if best and best.score >= threshold:
            results.append(best)
    return results
