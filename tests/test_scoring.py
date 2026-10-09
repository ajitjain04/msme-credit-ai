"""
Step 13 — Tests for model/scoring.py: the probability -> score -> risk
-band conversion, and score_company()'s end-to-end behaviour.

Pure verification only -- nothing here retrains the model or changes
model/scoring.py's logic.

How to run just this file:
    venv\\Scripts\\python.exe -m pytest tests/test_scoring.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from model.scoring import assign_risk_band, probability_to_score, score_company
from model.train import load_data

VALID_RISK_BANDS = {"Low Risk", "Medium Risk", "High Risk"}


# ---------------------------------------------------------------------------
# probability_to_score(): the 4 documented fixed points.
# ---------------------------------------------------------------------------

def test_probability_to_score_at_zero_is_near_900():
    # Segment 1's fraction is exactly 0 here, so this is exact in practice,
    # but we only PROMISE "near 900" per model/scoring.py's docstring --
    # pytest.approx lets this test state that promise, not a stricter one.
    assert probability_to_score(0.0) == pytest.approx(900, abs=1)


def test_probability_to_score_at_low_medium_boundary_is_exactly_750():
    # model/scoring.py's own docstring promises this is EXACT, not
    # approximate -- the whole point of piecewise-linear interpolation
    # meeting at the boundary. Testing exact equality here actually
    # verifies that promise, which pytest.approx would weaken.
    assert probability_to_score(0.20) == 750


def test_probability_to_score_at_medium_high_boundary_is_exactly_600():
    assert probability_to_score(0.50) == 600


def test_probability_to_score_at_one_is_near_300():
    assert probability_to_score(1.0) == pytest.approx(300, abs=1)


def test_probability_to_score_is_monotonically_decreasing():
    # Higher default probability must never produce a HIGHER score.
    probabilities = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
    scores = [probability_to_score(p) for p in probabilities]
    assert scores == sorted(scores, reverse=True)


def test_probability_to_score_clips_out_of_range_inputs():
    # probability_to_score() is documented to np.clip its input to [0, 1]
    # rather than raising or returning something outside [300, 900].
    assert probability_to_score(-0.5) == probability_to_score(0.0)
    assert probability_to_score(1.5) == probability_to_score(1.0)


# ---------------------------------------------------------------------------
# assign_risk_band(): boundary values specifically -- off-by-one errors
# live exactly at 750 and 600.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "score, expected_band",
    [
        (900, "Low Risk"),
        (751, "Low Risk"),
        (750, "Low Risk"),  # the Low/Medium boundary itself is Low Risk (>=)
        (749, "Medium Risk"),  # one point below the boundary
        (601, "Medium Risk"),
        (600, "Medium Risk"),  # the Medium/High boundary itself is Medium Risk (>=)
        (599, "High Risk"),  # one point below the boundary
        (300, "High Risk"),
    ],
)
def test_assign_risk_band_at_and_around_boundaries(score, expected_band):
    assert assign_risk_band(score) == expected_band


# ---------------------------------------------------------------------------
# score_company(): end-to-end, on real synthetic companies from the actual
# test split (data/processed/test.csv via model.train.load_data()) --
# checking INTERNAL CONSISTENCY, not specific hardcoded scores (the model
# itself is out of scope for this test file; model/scoring.py's own job is
# just to convert whatever probability the model produces correctly).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_test_rows():
    """The first 3 rows of the real test split, as pandas Series -- the
    exact input shape score_company() documents accepting."""
    _, _, X_test, _ = load_data()
    return [X_test.iloc[i] for i in range(3)]


def test_score_company_returns_well_formed_result(sample_test_rows):
    for row in sample_test_rows:
        result = score_company(row)
        assert 0.0 <= result["default_probability"] <= 1.0
        assert 300 <= result["credit_score"] <= 900
        assert result["risk_band"] in VALID_RISK_BANDS


def test_score_company_score_matches_probability_to_score(sample_test_rows):
    # score_company()'s credit_score must be exactly what
    # probability_to_score() would independently produce from the SAME
    # (calibrated) probability it returned -- these two must never drift
    # apart, since score_company() is documented to call
    # probability_to_score() internally on its own calibrated probability.
    for row in sample_test_rows:
        result = score_company(row)
        assert result["credit_score"] == probability_to_score(result["default_probability"])


def test_score_company_risk_band_matches_assign_risk_band(sample_test_rows):
    for row in sample_test_rows:
        result = score_company(row)
        assert result["risk_band"] == assign_risk_band(result["credit_score"])
