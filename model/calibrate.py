"""
Step 12c — Build and compare TWO probability calibration mappings
(isotonic regression vs. Platt/sigmoid scaling), and keep whichever one
actually works better.

WHY THIS STEP EXISTS
----------------------------------------------------------------------------
Step 7's tuned model uses class_weight="balanced" to fix Step 6's problem
of barely ever predicting a default (see model/tune.py's module docstring).
That fix worked for RANKING (ROC-AUC) and recall, but it has a side effect:
balancing reweights the training loss as if defaults were ~50% of the
population instead of their true ~15% rate. The model's predicted
PROBABILITIES absorb that reweighting too -- they run systematically too
high, even though the model still RANKS companies correctly.

That matters here because Step 8's probability_to_score() formula treats
probability = 0.20 and 0.50 as EXACT, meaningful boundaries between
Low/Medium/High risk. Calibration fixes the absolute numbers by learning:
"when the model says X%, what fraction of companies like that ACTUALLY
defaulted, historically?" -- and using THAT instead of the raw number.

WHY TWO CALIBRATORS, NOT JUST ONE
----------------------------------------------------------------------------
A first pass using ONLY isotonic regression produced a concerning result:
79.9% of the test set landed in "Low Risk" (up from 8.2% raw), with
several reliability buckets having only 0-2 training rows in them.
Isotonic regression fits a flexible, step-wise curve with as many "knots"
as there are distinct probability values -- powerful, but prone to
overfitting exactly this kind of noisy, small-sample curve (~4,000
training rows split 5 ways). Platt scaling (sigmoid calibration) fits
only 2 numbers total (a slope and an intercept, via a 1-feature logistic
regression), which is far less flexible -- and far less able to overfit
-- making it the standard fallback when isotonic looks unstable on
limited data. So this script fits BOTH on the exact same out-of-fold
probabilities, evaluates both honestly on the test set, and keeps
whichever one actually deserves to be used.

WHY NOT sklearn.calibration.CalibratedClassifierCV
----------------------------------------------------------------------------
CalibratedClassifierCV wraps the base estimator in an ensemble of several
internal clones (one per CV fold) and averages their outputs. That wrapped
object is no longer a single, plain LogisticRegression with one fixed,
inspectable set of coefficients -- and model/explainer.py's
shap.LinearExplainer specifically needs exactly that to produce exact,
closed-form SHAP values. Wrapping would silently break Step 9.

So instead, this script builds the same IDEA by hand, as separate, plain
objects:
  1. model/artifacts/model.joblib -- UNCHANGED by this script. Still the
     single, plain Logistic Regression Pipeline from Step 7.
     model/explainer.py keeps explaining this exact object, exactly as
     before.
  2. model/artifacts/calibrator.joblib -- a NEW, separate, tiny object
     (either an IsotonicRegression or a PlattCalibrator, whichever wins
     below) that only ever sees one number in and one number out (raw
     probability -> calibrated probability). model/calibration.py applies
     it as an extra translation step AFTER the base model runs; it never
     touches the base model itself.

HOW THE MAPPINGS ARE BUILT, WITHOUT DATA LEAKAGE
----------------------------------------------------------------------------
Fitting a calibration curve on predictions the model made about its OWN
training rows would be circular: a model is unrealistically confident
about rows it was trained on. Instead:
  1. sklearn.model_selection.cross_val_predict runs 5-fold stratified CV on
     the TRAINING set: for each fold, a fresh clone of the model (same type
     + hyperparameters as the real tuned model, reused directly from
     model/tune.py's build_trial_model()) is trained on the OTHER 4 folds
     and used to predict the held-out fold. Every training row ends up
     with a probability from a model that never saw it -- "out-of-fold"
     (OOF) probabilities.
  2. BOTH calibrators are fit on the SAME (OOF probability, true label)
     pairs, so the comparison between them is apples-to-apples.
  3. The held-out TEST set is touched exactly once, at the very end,
     purely to report Brier scores / the reliability table / the risk-band
     distributions / the final selection -- it plays no role in fitting
     either calibrator.

Does NOT retrain the base model, and does NOT touch model/train.py,
model/tune.py, or model/explainer.py.

How to run:
    python model/calibrate.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import StratifiedKFold, cross_val_predict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.calibration import PlattCalibrator  # noqa: E402
from model.config import RANDOM_SEED  # noqa: E402
from model.scoring import assign_risk_band, probability_to_score  # noqa: E402
from model.train import load_data  # noqa: E402
from model.tune import build_trial_model  # noqa: E402

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
BEST_PARAMS_PATH = ARTIFACTS_DIR / "best_params.json"
CALIBRATOR_PATH = ARTIFACTS_DIR / "calibrator.joblib"

# Backup location, mirroring model/tune.py's STEP6_BACKUP_DIR pattern.
# model.joblib is NOT actually modified by this script (see module
# docstring), but we snapshot it anyway, per that same safeguard pattern,
# in case a later step ever changes that.
PRE_CALIBRATION_BACKUP_DIR = ARTIFACTS_DIR / "pre_calibration"
PRE_CALIBRATION_MODEL_PATH = PRE_CALIBRATION_BACKUP_DIR / "model.joblib"
PRE_CALIBRATION_BEST_PARAMS_PATH = PRE_CALIBRATION_BACKUP_DIR / "best_params.json"

N_CV_FOLDS = 5
N_RELIABILITY_BINS = 10
BAND_ORDER = ["Low Risk", "Medium Risk", "High Risk"]

# Sanity-check threshold for the "is this risk-band distribution absurdly
# skewed" warning (percentage points in a single band).
RISK_BAND_SKEW_WARNING_THRESHOLD = 70.0


# ---------------------------------------------------------------------------
# Safeguard: back up the pre-calibration artifacts.
# ---------------------------------------------------------------------------

def backup_pre_calibration_artifacts() -> None:
    """Copies the pre-calibration model.joblib + best_params.json to
    model/artifacts/pre_calibration/ before anything calibration-related
    is written. Idempotent -- does nothing if the backup already exists,
    so a second run of this script can't overwrite the true
    pre-calibration snapshot."""
    if PRE_CALIBRATION_MODEL_PATH.exists() and PRE_CALIBRATION_BEST_PARAMS_PATH.exists():
        print(
            f"Pre-calibration backup already exists at "
            f"{PRE_CALIBRATION_BACKUP_DIR} -- leaving it untouched."
        )
        return

    if not MODEL_PATH.exists() or not BEST_PARAMS_PATH.exists():
        raise FileNotFoundError(
            "Expected model/artifacts/model.joblib and best_params.json "
            "from Step 7 before calibrating. Run model/tune.py first."
        )

    PRE_CALIBRATION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODEL_PATH, PRE_CALIBRATION_MODEL_PATH)
    shutil.copy2(BEST_PARAMS_PATH, PRE_CALIBRATION_BEST_PARAMS_PATH)
    print(f"Backed up pre-calibration model + best_params to {PRE_CALIBRATION_BACKUP_DIR}")


# ---------------------------------------------------------------------------
# Rebuild the exact tuned-model type/hyperparameters, and get its
# out-of-fold training probabilities.
# ---------------------------------------------------------------------------

def build_calibration_model_template(
    X_train: pd.DataFrame, y_train: pd.Series
) -> tuple[Any, str]:
    """Rebuilds an UNFITTED model with the exact same type and
    hyperparameters as the real tuned model.joblib, by reading
    best_params.json and replaying it through model.tune.build_trial_model()
    -- the same function model/tune.py itself used to build the final
    model. This guarantees "same type/hyperparameters" by construction
    (reusing code), rather than by manually retyping parameters a second
    time and hoping they stay in sync.
    """
    with open(BEST_PARAMS_PATH) as f:
        best_params_blob = json.load(f)
    model_name = best_params_blob["model_name"]
    best_params = best_params_blob["best_params"]

    # Only used by the XGBoost/LightGBM branches of build_trial_model();
    # harmless to compute even though today's winner (Logistic Regression)
    # ignores it, and keeps this script correct if a tree model ever wins
    # in the future.
    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())

    fixed_trial = optuna.trial.FixedTrial(best_params)
    model_template = build_trial_model(fixed_trial, model_name, scale_pos_weight)
    return model_template, model_name


def get_out_of_fold_probabilities(
    model_template: Any, X_train: pd.DataFrame, y_train: pd.Series
) -> np.ndarray:
    """5-fold stratified cross_val_predict on the TRAINING set only.
    cross_val_predict clones `model_template` internally for each fold, so
    every row's probability comes from a fold that never trained on it --
    see the module docstring's "no data leakage" section."""
    cv = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    oof_probabilities = cross_val_predict(
        model_template, X_train, y_train, cv=cv, method="predict_proba"
    )[:, 1]
    return oof_probabilities


# ---------------------------------------------------------------------------
# Fitting the two calibrators, on the SAME out-of-fold probabilities.
# ---------------------------------------------------------------------------

def fit_isotonic_calibrator(oof_probabilities: np.ndarray, y_train: pd.Series) -> IsotonicRegression:
    """Isotonic regression: a flexible, non-decreasing step curve fit on
    (OOF probability, true label) pairs. out_of_bounds='clip' means a
    probability outside the range seen during fitting gets clamped to the
    nearest edge rather than extrapolating wildly."""
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(oof_probabilities, y_train)
    return calibrator


def fit_platt_calibrator(oof_probabilities: np.ndarray, y_train: pd.Series) -> PlattCalibrator:
    """Platt scaling: fits a plain 1-feature LogisticRegression on the
    SAME (OOF probability, true label) pairs isotonic regression used --
    see PlattCalibrator's docstring for why this is much less prone to
    overfitting on a small training set."""
    x = oof_probabilities.reshape(-1, 1)
    logistic_model = LogisticRegression()
    logistic_model.fit(x, y_train)
    return PlattCalibrator(logistic_model)


# ---------------------------------------------------------------------------
# Evaluation: Brier score, reliability table, risk-band distribution --
# for Raw, Isotonic and Platt, side by side. Test set touched once.
# ---------------------------------------------------------------------------

def evaluate_probabilities(name: str, probabilities: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
    """Brier score + risk-band distribution for one set of test-set
    probabilities (raw, isotonic-calibrated, or Platt-calibrated)."""
    brier = brier_score_loss(y_true, probabilities)
    bands = [assign_risk_band(probability_to_score(p)) for p in probabilities]
    band_dist = pd.Series(bands).value_counts(normalize=True).reindex(BAND_ORDER).fillna(0.0) * 100
    return {
        "name": name,
        "probabilities": probabilities,
        "brier": float(brier),
        "band_dist": band_dist,
        "max_band_pct": float(band_dist.max()),
    }


def build_reliability_table(
    y_true: np.ndarray, proba_by_name: dict[str, np.ndarray], n_bins: int = N_RELIABILITY_BINS
) -> pd.DataFrame:
    """For each of n_bins equal-width probability buckets (0-10%, 10-20%,
    ...), computes the bucket's mean PREDICTED probability vs. the ACTUAL
    observed default rate among rows that landed in that bucket -- for
    every probability set in `proba_by_name`, side by side. A
    well-calibrated set of probabilities has 'Pred' close to 'Actual' in
    every row with a meaningful N; a very small/zero N flags data
    sparsity, where that row's numbers should be treated cautiously
    (exactly the symptom that showed up for isotonic regression alone)."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bucket_labels = [f"{int(bin_edges[b] * 100)}-{int(bin_edges[b + 1] * 100)}%" for b in range(n_bins)]

    def bucket_stats(proba: np.ndarray) -> tuple[list[int], list[float], list[float]]:
        bucket_idx = np.clip(np.digitize(proba, bin_edges[1:-1], right=False), 0, n_bins - 1)
        n_list, mean_pred_list, actual_list = [], [], []
        for b in range(n_bins):
            mask = bucket_idx == b
            n = int(mask.sum())
            n_list.append(n)
            mean_pred_list.append(float(proba[mask].mean()) if n > 0 else np.nan)
            actual_list.append(float(y_true[mask].mean()) if n > 0 else np.nan)
        return n_list, mean_pred_list, actual_list

    table: dict[str, Any] = {"Bucket": bucket_labels}
    for name, proba in proba_by_name.items():
        n_list, mean_pred_list, actual_list = bucket_stats(proba)
        table[f"N ({name})"] = n_list
        table[f"Pred ({name})"] = mean_pred_list
        table[f"Actual ({name})"] = actual_list

    return pd.DataFrame(table)


def print_calibration_report(results: dict[str, dict[str, Any]], reliability_table: pd.DataFrame) -> None:
    print("=" * 100)
    print("BRIER SCORE on the test set (lower is better; 0 = perfect, 0.25 = always guessing 50%)")
    print("=" * 100)
    for name in ["Raw", "Isotonic", "Platt"]:
        print(f"  {name:<10}: {results[name]['brier']:.4f}")

    print("\n" + "=" * 100)
    print(f"RELIABILITY TABLE ({N_RELIABILITY_BINS} buckets): mean predicted probability vs. actual default rate")
    print("Well-calibrated: 'Pred' close to 'Actual' in rows with a meaningful N. A tiny/zero N means that")
    print("row's numbers are unreliable (too few test companies landed in that probability range).")
    print("=" * 100)
    print(reliability_table.round(4).to_string(index=False))

    print("\n" + "=" * 100)
    print("RISK BAND DISTRIBUTION (% of test set): Raw vs. Isotonic vs. Platt")
    print("=" * 100)
    comparison = pd.DataFrame(
        {name: results[name]["band_dist"] for name in ["Raw", "Isotonic", "Platt"]}
    ).reindex(BAND_ORDER)
    print(comparison.round(1).to_string())
    print("=" * 100)


def select_winning_calibrator(
    results: dict[str, dict[str, Any]],
    isotonic_calibrator: IsotonicRegression,
    platt_calibrator: PlattCalibrator,
) -> tuple[str, Any]:
    """Picks which calibrator to actually SAVE, between Isotonic and Platt
    (Raw is the baseline for comparison, never a save candidate): prefer
    the lower test-set Brier score, UNLESS that candidate's risk-band
    distribution is absurdly skewed (> RISK_BAND_SKEW_WARNING_THRESHOLD%
    piled into one band) while the other candidate is not -- a calibrator
    that dumps most companies into a single risk band isn't usable
    regardless of a marginally better Brier score. Prints the full
    reasoning either way, plus a sanity-check warning for every candidate
    (including Raw, for context) whose distribution is skewed.
    """
    print("\n" + "=" * 100)
    print("CALIBRATOR SELECTION")
    print("=" * 100)

    for name in ["Raw", "Isotonic", "Platt"]:
        result = results[name]
        skewed = result["max_band_pct"] > RISK_BAND_SKEW_WARNING_THRESHOLD
        flag = " <-- WARNING: risk band distribution is absurdly skewed" if skewed else ""
        selectable = "" if name == "Raw" else " (candidate)"
        print(
            f"  {name}{selectable}: test-set Brier = {result['brier']:.4f}, "
            f"largest single risk band = {result['max_band_pct']:.1f}%{flag}"
        )

    candidates = {"Isotonic": isotonic_calibrator, "Platt": platt_calibrator}
    lower_brier_name = min(("Isotonic", "Platt"), key=lambda n: results[n]["brier"])
    other_name = "Platt" if lower_brier_name == "Isotonic" else "Isotonic"

    lower_brier_skewed = results[lower_brier_name]["max_band_pct"] > RISK_BAND_SKEW_WARNING_THRESHOLD
    other_skewed = results[other_name]["max_band_pct"] > RISK_BAND_SKEW_WARNING_THRESHOLD

    if not lower_brier_skewed:
        winner_name = lower_brier_name
        print(
            f"\n-> {winner_name} WINS: it has the lower test-set Brier score "
            f"({results[winner_name]['brier']:.4f} vs. {results[other_name]['brier']:.4f}) "
            f"and its risk-band distribution is not absurdly skewed "
            f"(largest band = {results[winner_name]['max_band_pct']:.1f}%)."
        )
    elif not other_skewed:
        winner_name = other_name
        print(
            f"\n-> {lower_brier_name} has the lower Brier score "
            f"({results[lower_brier_name]['brier']:.4f} vs. {results[other_name]['brier']:.4f}), "
            f"BUT its risk-band distribution is absurdly skewed "
            f"({results[lower_brier_name]['max_band_pct']:.1f}% in one band) -- a calibrator "
            f"that pushes most companies into a single risk band isn't usable for scoring. "
            f"{other_name}'s distribution is not similarly skewed "
            f"(largest band = {results[other_name]['max_band_pct']:.1f}%), so {other_name} WINS instead."
        )
    else:
        winner_name = lower_brier_name
        print(
            f"\n-> WARNING: BOTH candidates have an absurdly skewed risk-band distribution "
            f"(Isotonic largest band = {results['Isotonic']['max_band_pct']:.1f}%, "
            f"Platt largest band = {results['Platt']['max_band_pct']:.1f}%). "
            f"Picking {winner_name} for the lower Brier score "
            f"({results[winner_name]['brier']:.4f}), but this result should be treated with "
            f"caution -- consider more training data, fewer reliability bins, or revisiting "
            f"class_weight='balanced' upstream in model/tune.py."
        )

    print("=" * 100)
    return winner_name, candidates[winner_name]


def main() -> None:
    backup_pre_calibration_artifacts()

    X_train, y_train, X_test, y_test = load_data()
    y_true_test = y_test.to_numpy()

    model_template, model_name = build_calibration_model_template(X_train, y_train)
    print(
        f"Calibrating for model type: {model_name} "
        f"(same type + hyperparameters as model/artifacts/model.joblib, "
        f"reused directly from model/tune.py)."
    )

    print(f"Running {N_CV_FOLDS}-fold stratified cross_val_predict on the TRAINING "
          f"set to get out-of-fold probabilities (no leakage)...")
    oof_probabilities = get_out_of_fold_probabilities(model_template, X_train, y_train)

    print("Fitting isotonic regression calibrator on the out-of-fold probabilities...")
    isotonic_calibrator = fit_isotonic_calibrator(oof_probabilities, y_train)

    print("Fitting Platt scaling (sigmoid) calibrator on the SAME out-of-fold probabilities...")
    platt_calibrator = fit_platt_calibrator(oof_probabilities, y_train)

    # The REAL deployed model, for an honest, one-time test-set evaluation
    # (not a freshly-refit clone).
    base_model = joblib.load(MODEL_PATH)
    raw_proba_test = base_model.predict_proba(X_test)[:, 1]
    isotonic_proba_test = isotonic_calibrator.predict(raw_proba_test)
    platt_proba_test = platt_calibrator.predict(raw_proba_test)

    results = {
        "Raw": evaluate_probabilities("Raw", raw_proba_test, y_true_test),
        "Isotonic": evaluate_probabilities("Isotonic", isotonic_proba_test, y_true_test),
        "Platt": evaluate_probabilities("Platt", platt_proba_test, y_true_test),
    }

    reliability_table = build_reliability_table(
        y_true_test,
        {"Raw": raw_proba_test, "Isotonic": isotonic_proba_test, "Platt": platt_proba_test},
    )

    print_calibration_report(results, reliability_table)

    winner_name, winner_object = select_winning_calibrator(results, isotonic_calibrator, platt_calibrator)

    joblib.dump(winner_object, CALIBRATOR_PATH)
    print(f"\nSaved the WINNING calibrator ({winner_name}) to {CALIBRATOR_PATH}")
    print(
        "model/artifacts/model.joblib was NOT modified -- it remains the exact "
        "same plain Logistic Regression Pipeline model/explainer.py's SHAP "
        "explainer expects."
    )


if __name__ == "__main__":
    main()
