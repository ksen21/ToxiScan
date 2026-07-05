"""
Core matching + scoring logic for ToxiScan.
Splits raw ingredient text, matches against MongoDB `chemicals` collection,
and computes an overall safety score.
"""

import re
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.schemas import IngredientResult, SeverityLevel

# Maps whatever casing/wording exists in the DB to our canonical enum values
SEVERITY_ALIASES = {
    "low": SeverityLevel.LOW,
    "mild": SeverityLevel.LOW,
    "medium": SeverityLevel.MODERATE,
    "moderate": SeverityLevel.MODERATE,
    "high": SeverityLevel.HIGH,
    "severe": SeverityLevel.HIGH,
    "critical": SeverityLevel.CRITICAL,
    "extreme": SeverityLevel.CRITICAL,
}


def normalize_severity(raw_value) -> SeverityLevel:
    """Converts any DB severity string (any casing/wording) to a valid SeverityLevel."""
    if raw_value is None:
        return SeverityLevel.LOW
    key = str(raw_value).strip().lower()
    return SEVERITY_ALIASES.get(key, SeverityLevel.LOW)

# Points deducted per flagged ingredient, based on severity
SEVERITY_PENALTY = {
    SeverityLevel.LOW: 5,
    SeverityLevel.MODERATE: 12,
    SeverityLevel.HIGH: 22,
    SeverityLevel.CRITICAL: 35,
}


def split_ingredients(raw_text: str) -> List[str]:
    """
    Splits a raw ingredient label string into individual ingredient names.
    Handles comma-separated lists, trims whitespace, drops empty entries.
    """
    # Some labels use "/" or ";" as separators too — normalize to commas
    normalized = re.sub(r"[;/]", ",", raw_text)
    parts = [p.strip() for p in normalized.split(",")]
    return [p for p in parts if len(p) > 0]


async def match_ingredient(db: AsyncIOMotorDatabase, ingredient: str) -> IngredientResult:
    """
    Looks up a single ingredient against the chemicals collection.
    1. Tries an exact match (case-insensitive) on `name` or `aliases`.
    2. Falls back to a partial/substring match if no exact match is found —
       catches generic label terms like "Parabens" or "SLS" that don't
       exactly equal a specific chemical name in the DB.
    """
    escaped = re.escape(ingredient)

    # ── 1. Exact match ──────────────────────────────────────────────────────
    exact_query = {
        "$or": [
            {"name": {"$regex": f"^{escaped}$", "$options": "i"}},
            {"aliases": {"$regex": f"^{escaped}$", "$options": "i"}},
        ]
    }
    doc = await db.chemicals.find_one(exact_query)
    match_type = "exact"

    # ── 2. Partial/fuzzy match fallback ─────────────────────────────────────
    if not doc:
        # Only attempt fuzzy matching for reasonably specific terms (avoid
        # matching something tiny like "oil" against everything).
        if len(ingredient) >= 4:
            # Strip a trailing "s" so generic plural terms like "Parabens"
            # can match specific chemical names like "Butylparaben"
            root = ingredient[:-1] if ingredient.lower().endswith("s") else ingredient
            root_escaped = re.escape(root)

            partial_query = {
                "$or": [
                    # Case A: DB name/alias appears inside the ingredient text
                    # e.g. ingredient "Parabens (Butylparaben)" contains "Butylparaben"
                    {"name": {"$regex": escaped, "$options": "i"}},
                    {"aliases": {"$regex": escaped, "$options": "i"}},
                    # Case B: ingredient root appears inside the DB name/alias
                    # e.g. ingredient "Parabens" -> root "Paraben" is inside "Butylparaben"
                    {"name": {"$regex": root_escaped, "$options": "i"}},
                    {"aliases": {"$regex": root_escaped, "$options": "i"}},
                ]
            }
            doc = await db.chemicals.find_one(partial_query)
            match_type = "fuzzy"

    if doc:
        return IngredientResult(
            ingredient=ingredient,
            matched_chemical=doc["name"],
            severity=normalize_severity(doc.get("severity")),
            # DB field is `danger_type` (see chemical_template.json / seed_chemicals.py),
            # not `concerns` — fixed while wiring up Phase 6 research_url passthrough.
            concerns=doc.get("danger_type", []),
            is_flagged=True,
            research_url=doc.get("research_url"),
        )

    return IngredientResult(
        ingredient=ingredient,
        matched_chemical=None,
        severity=None,
        concerns=[],
        is_flagged=False,
        research_url=None,
    )


async def scan_ingredients(db: AsyncIOMotorDatabase, raw_text: str) -> List[IngredientResult]:
    """Splits + matches every ingredient in the raw text."""
    ingredients = split_ingredients(raw_text)
    results = [await match_ingredient(db, ing) for ing in ingredients]
    return results


def score_to_label(score: int) -> str:
    """
    Maps a 0-100 safety_score to its display label.
    Thresholds: >=85 Safe, >=60 Moderate, >=35 Risky, else Dangerous.
    Split out from calculate_safety_score so the boundaries can be
    unit-tested directly against any score, not just ones reachable
    by summing SEVERITY_PENALTY combinations.
    """
    if score >= 85:
        return "Safe"
    elif score >= 60:
        return "Moderate"
    elif score >= 35:
        return "Risky"
    else:
        return "Dangerous"


def calculate_safety_score(results: List[IngredientResult]) -> tuple[int, str]:
    """
    Starts at 100 and deducts points per flagged ingredient based on severity.
    Returns (score, label).
    """
    score = 100
    for r in results:
        if r.is_flagged and r.severity:
            score -= SEVERITY_PENALTY.get(r.severity, 10)

    score = max(0, min(100, score))
    label = score_to_label(score)

    return score, label


def derive_display_scores(score: int) -> tuple[float, float]:
    """
    Converts the internal 0-100 safety_score into frontend-friendly display
    values, without changing how the score itself is calculated:
    - score_out_of_10: e.g. 66 -> 6.6 (for "6.6/10" text)
    - star_rating: e.g. 66 -> 3.3 (out of 5 stars, supports half-stars)
    """
    score_out_of_10 = round(score / 10, 1)
    star_rating = round(score / 20, 1)
    return score_out_of_10, star_rating