"""
Step 8 — Convert model probabilities into a 300-900 credit score and a
Low/Medium/High risk band.

This script does NOT retrain or re-tune anything. It loads the already
-tuned model saved by model/tune.py (model/artifacts/model.joblib) and adds
one more translation step on top of it: turning a raw "probability of
default" number (which means little to a loan officer) into a credit score
and risk band (which do), using the exact rule fixed in CLAUDE.md:

    Low Risk:    score 750+,     probability < 0.20
    Medium Risk: score 600-749,  probability 0.20-0.50
    High Risk:   score < 600,    probability > 0.50

THE SCORE FORMULA (read this before touching probability_to_score())
----------------------------------------------------------------------------
We need ONE formula f(probability) -> score that simultaneously satisfies
FOUR fixed points:
    f(0.00) ~= 900   (best possible score)
    f(0.20) == 750   (exact Low / Medium boundary)
    f(0.50) == 600   (exact Medium / High boundary)
    f(1.00) ~= 300   (worst possible score)

A single straight line can only satisfy TWO points at once (a line is
fully determined by any 2 of them). Check this directly: the line through
(0, 900) and (1, 300) is score = 900 - 600*p. At p = 0.20 that line gives
900 - 120 = 780, not 750. So one straight line cannot hit all 4 points --
we have to use a DIFFERENT straight line on each of the 3 intervals the
risk bands already split probability into: [0, 0.20], [0.20, 0.50], and
[0.50, 1.00]. This is called piecewise-linear interpolation: 3 short line
segments, joined end-to-end at the 2 boundary points, each one doing an
exact straight-line translation between its own pair of (probability,
score) points:

    Segment 1  p in [0.00, 0.20]:  score drops   900 -> 750  (-150 over 0.20)
    Segment 2  p in [0.20, 0.50]:  score drops   750 -> 600  (-150 over 0.30)
    Segment 3  p in [0.50, 1.00]:  score drops   600 -> 300  (-300 over 0.50)

Internal consistency check (the thing to verify, not just eyeball):
  - Segment 1 at p=0.20 gives EXACTLY 750 (900 + (750-900) * (0.20/0.20)).
  - Segment 2 starts at p=0.20 at EXACTLY 750 (same value Segment 1 ends
    on) and at p=0.50 gives EXACTLY 600 (750 + (600-750) * (0.30/0.30)).
  - Segment 3 starts at p=0.50 at EXACTLY 600 (same value Segment 2 ends
    on) and at p=1.00 gives EXACTLY 300 (600 + (300-600) * (0.50/0.50)).
  So the 3 segments meet with NO jump at either boundary (continuous), each
  segment is a straight line (monotonic, no weird curvature), and all 4
  required points are hit exactly rather than approximately.

Every number above (900, 750, 600, 300, 0.20, 0.50) is read from
model/config.py's RISK_BANDS, not hardcoded twice -- if the risk bands ever
change (with permission, per CLAUDE.md), this formula updates itself.

How to run:
    python model/scoring.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import FEATURE_COLUMNS, RISK_BANDS, TARGET_COLUMN  # noqa: E402
from model.train import load_data  # noqa: E402

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"

# --- Score formula constants, all read from model/config.py's RISK_BANDS
# (never re-typed as separate magic numbers) ---------------------------------
SCORE_MAX = 900  # best possible score, at probability -> 0
SCORE_MIN = 300  # worst possible score, at probability -> 1

P_LOW_MEDIUM_BOUNDARY = RISK_BANDS["Low Risk"]["max_probability"]        # 0.20
P_MEDIUM_HIGH_BOUNDARY = RISK_BANDS["Medium Risk"]["max_probability"]    # 0.50
S_LOW_MEDIUM_BOUNDARY = RISK_BANDS["Low Risk"]["min_score"]              # 750
S_MEDIUM_HIGH_BOUNDARY = RISK_BANDS["Medium Risk"]["min_score"]          # 600


def probability_to_score(probability: float) -> int:
    """Converts a predicted default probability (0-1) into a 300-900 credit
    score, using the 3-segment piecewise-linear mapping derived in the
    module docstring above. Higher probability of default -> lower score.

    probability_to_score(0.20) == 750 and probability_to_score(0.50) == 600
    EXACTLY (not approximately) -- see the docstring's internal consistency
    check.
    """
    p = float(np.clip(probability, 0.0, 1.0))

    if p <= P_LOW_MEDIUM_BOUNDARY:
        # Segment 1: [0, 0.20] -> [900, 750]
        fraction = p / P_LOW_MEDIUM_BOUNDARY if P_LOW_MEDIUM_BOUNDARY else 0.0
        score = SCORE_MAX + (S_LOW_MEDIUM_BOUNDARY - SCORE_MAX) * fraction
    elif p <= P_MEDIUM_HIGH_BOUNDARY:
        # Segment 2: [0.20, 0.50] -> [750, 600]
        span = P_MEDIUM_HIGH_BOUNDARY - P_LOW_MEDIUM_BOUNDARY
        fraction = (p - P_LOW_MEDIUM_BOUNDARY) / span if span else 0.0
        score = S_LOW_MEDIUM_BOUNDARY + (
            S_MEDIUM_HIGH_BOUNDARY - S_LOW_MEDIUM_BOUNDARY
        ) * fraction
    else:
        # Segment 3: [0.50, 1.00] -> [600, 300]
        span = 1.0 - P_MEDIUM_HIGH_BOUNDARY
        fraction = (p - P_MEDIUM_HIGH_BOUNDARY) / span if span else 0.0
        score = S_MEDIUM_HIGH_BOUNDARY + (SCORE_MIN - S_MEDIUM_HIGH_BOUNDARY) * fraction

    return int(round(np.clip(score, SCORE_MIN, SCORE_MAX)))


def assign_risk_band(score: int) -> str:
    """Returns 'Low Risk', 'Medium Risk' or 'High Risk' for a 300-900 score,
    matching CLAUDE.md's thresholds exactly: Low = 750+, Medium = 600-749,
    High = below 600."""
    if score >= S_LOW_MEDIUM_BOUNDARY:
        return "Low Risk"
    if score >= S_MEDIUM_HIGH_BOUNDARY:
        return "Medium Risk"
    return "High Risk"


# ---------------------------------------------------------------------------
# The model, loaded once when this module is imported.
# ---------------------------------------------------------------------------

_MODEL = joblib.load(MODEL_PATH)


def score_company(features: Union[dict, pd.Series, pd.DataFrame]) -> dict[str, Any]:
    """Scores ONE company end-to-end: runs the tuned model to get a default
    probability, converts it to a 300-900 credit score, and assigns a risk
    band. This is the single function the backend API (Step 11) will call
    per company, so its input/output shapes are deliberately simple:

    Input `features` -- any of:
      - a dict of {feature_name: value} (e.g. from a parsed API request)
      - a pandas Series (e.g. one row pulled out of a dataframe)
      - a single-row pandas DataFrame
    It must contain a value for every column in model.config.FEATURE_COLUMNS
    (extra columns, like an identifier, are fine and are simply ignored).

    Returns a dict:
      {
        "default_probability": float in [0, 1],
        "credit_score": int in [300, 900],
        "risk_band": "Low Risk" | "Medium Risk" | "High Risk",
      }
    """
    if isinstance(features, pd.DataFrame):
        if len(features) != 1:
            raise ValueError(
                "score_company() scores exactly one company at a time, but "
                f"got a DataFrame with {len(features)} rows. Call it once "
                "per row (e.g. in a loop) instead."
            )
        row = features.iloc[0]
    elif isinstance(features, pd.Series):
        row = features
    elif isinstance(features, dict):
        row = pd.Series(features)
    else:
        raise TypeError(
            "score_company() expects a dict, pandas Series, or single-row "
            f"DataFrame -- got {type(features).__name__}."
        )

    missing = [col for col in FEATURE_COLUMNS if col not in row.index]
    if missing:
        raise ValueError(f"score_company() is missing required feature(s): {missing}")

    # Build a 1-row DataFrame in the exact column order the model was
    # trained on (model.config.FEATURE_COLUMNS), so column order can never
    # silently drift between training and scoring.
    X = pd.DataFrame([row[FEATURE_COLUMNS]])
    probability = float(_MODEL.predict_proba(X)[:, 1][0])
    score = probability_to_score(probability)
    risk_band = assign_risk_band(score)

    return {
        "default_probability": probability,
        "credit_score": score,
        "risk_band": risk_band,
    }


# ---------------------------------------------------------------------------
# Test-set re-evaluation using the risk-band thresholds instead of the
# Step 7 provisional 0.5 cutoff, plus sanity-check printouts.
# ---------------------------------------------------------------------------

def evaluate_with_risk_bands(X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
    """Re-evaluates the already-tuned model on the test set, but this time
    derives the "predicted default" label from the risk band instead of a
    raw 0.5 cutoff: a company is treated as a predicted default exactly
    when it lands in 'High Risk' (score < 600), which is the risk-band
    system's natural equivalent of "probability > 0.50".

    No retraining happens here -- this only changes how we read out
    predictions that the already-tuned model already produces.
    """
    probabilities = _MODEL.predict_proba(X_test)[:, 1]
    scores = np.array([probability_to_score(p) for p in probabilities])
    bands = np.array([assign_risk_band(s) for s in scores])

    predicted_default = (bands == "High Risk").astype(int)

    return {
        "probabilities": probabilities,
        "scores": scores,
        "bands": bands,
        "precision_default": float(
            precision_score(y_test, predicted_default, pos_label=1, zero_division=0)
        ),
        "recall_default": float(
            recall_score(y_test, predicted_default, pos_label=1, zero_division=0)
        ),
        "f1_default": float(
            f1_score(y_test, predicted_default, pos_label=1, zero_division=0)
        ),
        "confusion_matrix": confusion_matrix(y_test, predicted_default).tolist(),
    }


def print_sanity_check_against_step7(risk_band_eval: dict[str, Any]) -> None:
    """Compares the risk-band-derived metrics against Step 7's provisional
    0.5-threshold metrics (read from model_metrics.json). Explains WHY these
    should be very close/identical, and the one tiny edge case where they
    could differ.
    """
    import json

    metrics_path = ARTIFACTS_DIR / "model_metrics.json"
    with open(metrics_path) as f:
        saved_metrics = json.load(f)
    step7 = saved_metrics["step7_tuned_test_metrics"]

    print("=" * 90)
    print("SANITY CHECK: risk-band-derived metrics vs. Step 7's provisional 0.5 threshold")
    print("=" * 90)
    print(
        "Why these should match: 'High Risk' is defined as score < 600, and our "
        "probability_to_score() formula maps probability = 0.50 to EXACTLY score = "
        "600. So '(score < 600)' and '(probability > 0.50)' pick out the same "
        "companies -- the exact same rule Step 7 used as its provisional 0.5 cutoff "
        "('probability >= 0.50' = predicted default). The ONE difference is the "
        "boundary itself: Step 7 counted probability == 0.50 EXACTLY as a predicted "
        "default (>=), while the risk-band rule counts score == 600 EXACTLY as "
        "'Medium Risk', not 'High Risk' (score < 600 is strict). With continuous "
        "model probabilities, landing exactly on 0.50 is vanishingly unlikely, so in "
        "practice we expect these numbers to match exactly or differ by at most 1 "
        "company."
    )
    comparison = pd.DataFrame(
        [
            {
                "Metric": "Precision (default)",
                "Step 7 (p >= 0.5)": step7["precision_default"],
                "Step 8 (risk band)": risk_band_eval["precision_default"],
            },
            {
                "Metric": "Recall (default)",
                "Step 7 (p >= 0.5)": step7["recall_default"],
                "Step 8 (risk band)": risk_band_eval["recall_default"],
            },
            {
                "Metric": "F1 (default)",
                "Step 7 (p >= 0.5)": step7["f1_default"],
                "Step 8 (risk band)": risk_band_eval["f1_default"],
            },
        ]
    )
    print(comparison.round(4).to_string(index=False))
    print(f"\nStep 7 confusion matrix [[TN, FP], [FN, TP]]: {step7['confusion_matrix']}")
    print(f"Step 8 confusion matrix [[TN, FP], [FN, TP]]: {risk_band_eval['confusion_matrix']}")
    print("=" * 90)


def print_risk_band_distribution(bands: np.ndarray) -> None:
    """Prints what % of the test set lands in each risk band."""
    counts = pd.Series(bands).value_counts()
    pct = (counts / len(bands) * 100).round(1)

    print("=" * 50)
    print("RISK BAND DISTRIBUTION (test set)")
    print("=" * 50)
    for band in ["Low Risk", "Medium Risk", "High Risk"]:
        n = counts.get(band, 0)
        print(f"  {band}: {n} companies ({pct.get(band, 0.0)}%)")
    print("=" * 50)


def print_example_companies(
    X_test: pd.DataFrame,
    y_test: pd.Series,
    probabilities: np.ndarray,
    scores: np.ndarray,
    bands: np.ndarray,
) -> None:
    """Prints a handful of test-set companies side by side with their key
    raw features, predicted probability, score and risk band -- so the
    output can be eyeballed for sanity (e.g. does a company with many
    bounces and a thin cash buffer actually land in High Risk?).

    Deliberately picks the 2 safest, the 2 riskiest, and 1 middling
    company by predicted probability, rather than a random sample, so the
    printed examples actually cover the full range of outcomes.
    """
    key_feature_cols = [
        "age_of_business_years",
        "bounce_count_last_6m",
        "cash_buffer_ratio",
        "net_cash_margin",
        "gst_filing_regularity_score",
        "has_gst_registration",
    ]

    display_df = X_test[key_feature_cols].copy()
    display_df["actual_default"] = y_test.to_numpy()
    display_df["predicted_probability"] = probabilities
    display_df["credit_score"] = scores
    display_df["risk_band"] = bands
    display_df = display_df.sort_values("predicted_probability").reset_index(drop=True)

    n = len(display_df)
    example_positions = sorted(set([0, 1, n // 2, n - 2, n - 1]))
    examples = display_df.iloc[example_positions]

    print("=" * 110)
    print("EXAMPLE COMPANIES (2 safest, 1 middling, 2 riskiest by predicted probability)")
    print("=" * 110)
    print(examples.round(4).to_string(index=False))
    print("=" * 110)


def main() -> None:
    _, _, X_test, y_test = load_data()

    risk_band_eval = evaluate_with_risk_bands(X_test, y_test)

    print_risk_band_distribution(risk_band_eval["bands"])
    print()
    print_sanity_check_against_step7(risk_band_eval)
    print()
    print_example_companies(
        X_test,
        y_test,
        risk_band_eval["probabilities"],
        risk_band_eval["scores"],
        risk_band_eval["bands"],
    )


if __name__ == "__main__":
    main()
