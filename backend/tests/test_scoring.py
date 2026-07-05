"""
Phase 7 — unit tests for services/scanner.py scoring logic.

Run from the `backend/` directory (same convention as `uvicorn main:app`):
    pytest tests/test_scoring.py -v

Note on scale: the original build_plan.md/SPEC.md sketch used a 0-10 score
with SAFE/CAUTION/AVOID labels. The actual implementation (decisions.md,
Phase 3) uses a 0-100 score with Safe/Moderate/Risky/Dangerous labels
instead — these tests cover the real scanner.py, not the old sketch.
Thresholds under test: >=85 Safe, >=60 Moderate, >=35 Risky, else Dangerous.
"""

import pytest
from typing import Optional

from services.scanner import calculate_safety_score, derive_display_scores, score_to_label
from models.schemas import IngredientResult, SeverityLevel


def make_result(is_flagged: bool = False, severity: Optional[SeverityLevel] = None) -> IngredientResult:
    """Small helper — builds a minimal IngredientResult for scoring tests."""
    return IngredientResult(
        ingredient="test-ingredient",
        matched_chemical="Test Chemical" if is_flagged else None,
        severity=severity,
        concerns=[],
        is_flagged=is_flagged,
        research_url=None,
    )


# ─── calculate_safety_score ────────────────────────────────────────────────

def test_no_flagged_ingredients_full_score():
    results = [make_result(is_flagged=False) for _ in range(5)]
    score, label = calculate_safety_score(results)
    assert score == 100
    assert label == "Safe"


def test_empty_results_full_score():
    score, label = calculate_safety_score([])
    assert score == 100
    assert label == "Safe"


def test_single_high_severity():
    results = [make_result(is_flagged=True, severity=SeverityLevel.HIGH)]
    score, label = calculate_safety_score(results)
    assert score == 78  # 100 - 22
    assert label == "Moderate"


def test_five_critical_severity_capped_at_zero():
    # 5 * 35 = 175 deduction -> would go to -75, must clamp to 0, not negative
    results = [make_result(is_flagged=True, severity=SeverityLevel.CRITICAL) for _ in range(5)]
    score, label = calculate_safety_score(results)
    assert score == 0
    assert score >= 0
    assert label == "Dangerous"


def test_mixed_severities_correct_math():
    results = [
        make_result(is_flagged=True, severity=SeverityLevel.LOW),       # -5
        make_result(is_flagged=True, severity=SeverityLevel.MODERATE),  # -12
        make_result(is_flagged=True, severity=SeverityLevel.HIGH),      # -22
        make_result(is_flagged=True, severity=SeverityLevel.CRITICAL),  # -35
    ]
    score, label = calculate_safety_score(results)
    assert score == 26  # 100 - (5+12+22+35)
    assert label == "Dangerous"


def test_flagged_without_severity_causes_no_deduction():
    # is_flagged=True but severity=None should be skipped (matches
    # `if r.is_flagged and r.severity` guard in calculate_safety_score)
    results = [make_result(is_flagged=True, severity=None)]
    score, label = calculate_safety_score(results)
    assert score == 100
    assert label == "Safe"


def test_unflagged_ingredient_with_severity_set_causes_no_deduction():
    # Defensive case — severity present but is_flagged False should never happen
    # in real data (match_ingredient always pairs them), but scoring must not
    # deduct if is_flagged is False regardless.
    results = [make_result(is_flagged=False, severity=SeverityLevel.CRITICAL)]
    score, label = calculate_safety_score(results)
    assert score == 100
    assert label == "Safe"


@pytest.mark.parametrize(
    "score,expected_label",
    [
        (100, "Safe"),
        (85, "Safe"),      # boundary — inclusive
        (84, "Moderate"),
        (60, "Moderate"),  # boundary — inclusive
        (59, "Risky"),
        (35, "Risky"),     # boundary — inclusive
        (34, "Dangerous"),
        (0, "Dangerous"),
    ],
)
def test_label_thresholds(score, expected_label):
    # Tests the label boundaries directly against every integer score,
    # rather than via calculate_safety_score — not every 0-100 value is
    # reachable by summing SEVERITY_PENALTY combinations (5, 12, 22, 35).
    assert score_to_label(score) == expected_label


def test_calculate_safety_score_uses_score_to_label():
    # Sanity check that calculate_safety_score's label actually comes from
    # score_to_label, using a score that IS reachable (100 - 5*3 = 85).
    results = [make_result(is_flagged=True, severity=SeverityLevel.LOW) for _ in range(3)]
    score, label = calculate_safety_score(results)
    assert score == 85
    assert label == score_to_label(85) == "Safe"


# ─── derive_display_scores ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "score,expected_out_of_10,expected_stars",
    [
        (100, 10.0, 5.0),
        (66, 6.6, 3.3),
        (0, 0.0, 0.0),
        (73, 7.3, 3.6),
        (85, 8.5, 4.2),
    ],
)
def test_derive_display_scores(score, expected_out_of_10, expected_stars):
    score_out_of_10, star_rating = derive_display_scores(score)
    assert score_out_of_10 == expected_out_of_10
    assert star_rating == expected_stars


def test_derive_display_scores_never_negative_or_over_max():
    for score in (0, 1, 50, 99, 100):
        score_out_of_10, star_rating = derive_display_scores(score)
        assert 0.0 <= score_out_of_10 <= 10.0
        assert 0.0 <= star_rating <= 5.0