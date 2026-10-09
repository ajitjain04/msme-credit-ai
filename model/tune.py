"""
Step 7 — Fix class imbalance, then tune hyperparameters with Optuna.

Step 6 found two problems in model/artifacts/model_metrics.json:
  1. The tree models (Random Forest, XGBoost, LightGBM) scored a LOWER
     test-set ROC-AUC than plain Logistic Regression -- unusual, and a sign
     something was holding them back.
  2. Recall on the default (1) class was very low everywhere (8-16%): the
     models were missing 84-92% of the companies that actually defaulted.
Both point at the same root cause: none of the 4 Step 6 models were told
the data is imbalanced (~15% default, ~85% non-default), so they all leaned
toward the easy, common answer ("not a default").

This script fixes that in two stages:

  STAGE 1 (quick fix): re-run the same 4 model types with class-imbalance
  handling switched ON (class_weight="balanced" / scale_pos_weight), scored
  with stratified cross-validation on the TRAINING SET ONLY, to see the
  before/after impact on recall and pick a winning model type.

  STAGE 2 (proper tuning): run Optuna hyperparameter search for the winning
  model type, again using cross-validation on the training set only. The
  held-out test set is touched exactly once, at the very end, purely to
  report the final tuned model's numbers.

WHY ROC-AUC IS THE OPTUNA OBJECTIVE (not precision/recall/F1)
----------------------------------------------------------------------------
Precision, recall and F1 all depend on a classification threshold (the cutoff
probability above which we call a company "high risk"). We haven't chosen
that threshold yet on purpose -- Step 8 will set it deliberately, based on
how predicted probabilities map onto the 300-900 credit score and the
Low/Medium/High risk bands. If we tuned hyperparameters to maximise
recall/F1 at an arbitrary threshold of 0.5 right now, we could easily pick
a model that happens to look good at 0.5 but would look worse at whatever
threshold Step 8 actually settles on.

ROC-AUC has no threshold in it at all -- it scores the model's RANKING of
companies from safest to riskiest, across every possible threshold at once.
That makes it a stable target to optimise during tuning, and the resulting
model's ranking quality will still be good no matter what threshold Step 8
eventually chooses.

SAFEGUARDS IN THIS SCRIPT
----------------------------------------------------------------------------
- Step 6's model.joblib and model_metrics.json are copied to
  model/artifacts/baseline_step6/ BEFORE anything in model/artifacts/ is
  overwritten (see backup_step6_artifacts()).
- model/preprocessing.py's output (data/processed/train.csv / test.csv) and
  model/config.py's FEATURE_COLUMNS / TARGET_COLUMN are reused exactly as
  they are -- this script adds no new preprocessing of its own. Imputation
  for Logistic Regression / Random Forest still happens inside a Pipeline,
  fit on the training fold only, exactly like in model/train.py.
- The test set (X_test, y_test) is not referenced anywhere above the
  "FINAL TEST-SET EVALUATION" section at the bottom of main() -- every
  model-type and hyperparameter decision above that point uses only
  cross-validation on the training set.

How to run (from the project's venv, which has optuna + lightgbm installed):
    python model/tune.py
Expect ~50 Optuna trials to print their progress live as they run.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import RANDOM_SEED  # noqa: E402
from model.train import compute_ks_statistic, load_data  # noqa: E402

# --- Optional dependencies: both ARE listed in requirements.txt and ARE
# installed in the project's venv (checked before writing this script).
# We still import them defensively -- if this script is ever run with a
# different interpreter that doesn't have them, we tell the user exactly
# what's missing and why, instead of installing anything ourselves.
try:
    import optuna
    from optuna.samplers import TPESampler
except ImportError as exc:
    raise ImportError(
        "optuna is not installed in the Python environment running this "
        "script. It IS listed in requirements.txt and IS installed in the "
        "project's venv (venv/Scripts/python.exe) -- make sure you're "
        "running this script with that interpreter "
        "(e.g. `venv\\Scripts\\python.exe model/tune.py` or after "
        "activating the venv), rather than a different Python install."
    ) from exc

try:
    from lightgbm import LGBMClassifier
except ImportError as exc:
    raise ImportError(
        "lightgbm is not installed in the Python environment running this "
        "script. It IS listed in requirements.txt and IS installed in the "
        "project's venv -- run this script with that interpreter instead "
        "of a different Python install."
    ) from exc

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "model_metrics.json"
BEST_PARAMS_PATH = ARTIFACTS_DIR / "best_params.json"

# Where Step 6's original model + metrics get backed up before this script
# overwrites model/artifacts/model.joblib and model_metrics.json.
STEP6_BACKUP_DIR = ARTIFACTS_DIR / "baseline_step6"
STEP6_BACKUP_MODEL_PATH = STEP6_BACKUP_DIR / "model.joblib"
STEP6_BACKUP_METRICS_PATH = STEP6_BACKUP_DIR / "model_metrics.json"

N_CV_FOLDS = 5
N_OPTUNA_TRIALS = 50

# Classification threshold used ONLY for the final test-set
# precision/recall/F1/confusion-matrix numbers printed at the end.
# PROVISIONAL -- Step 8 will choose this properly based on the credit-score
# / risk-band design. It is NOT used anywhere during model or
# hyperparameter selection above.
FINAL_REPORT_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Safeguard: back up Step 6's artifacts before we touch them.
# ---------------------------------------------------------------------------

def backup_step6_artifacts() -> dict[str, Any]:
    """Copies Step 6's model.joblib and model_metrics.json to
    model/artifacts/baseline_step6/ before this script overwrites the live
    model/artifacts/model.joblib and model_metrics.json.

    If a backup already exists, we do NOT overwrite it -- that would risk
    replacing the true Step 6 baseline with whatever this script already
    produced on an earlier run. Returns the (already-backed-up) Step 6
    metrics dict either way, for use in the comparison tables below.
    """
    if STEP6_BACKUP_MODEL_PATH.exists() and STEP6_BACKUP_METRICS_PATH.exists():
        print(
            f"Step 6 backup already exists at {STEP6_BACKUP_DIR} "
            f"-- leaving it untouched."
        )
    else:
        if not MODEL_PATH.exists() or not METRICS_PATH.exists():
            raise FileNotFoundError(
                "Expected model/artifacts/model.joblib and model_metrics.json "
                "from Step 6 before running Step 7 tuning. Run "
                "`python model/train.py` first."
            )
        STEP6_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODEL_PATH, STEP6_BACKUP_MODEL_PATH)
        shutil.copy2(METRICS_PATH, STEP6_BACKUP_METRICS_PATH)
        print(f"Backed up Step 6's model + metrics to {STEP6_BACKUP_DIR}")

    with open(STEP6_BACKUP_METRICS_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Stage 1: balanced (but untuned) versions of the 4 Step 6 model types.
# ---------------------------------------------------------------------------

def build_balanced_models(scale_pos_weight: float) -> dict[str, Any]:
    """The same 4 model types as model/train.py's build_models(), but each
    with class-imbalance handling switched on. Still standard/default
    hyperparameters otherwise -- this stage is about measuring the effect
    of balancing alone, before any tuning.
    """
    models: dict[str, Any] = {}

    models["Logistic Regression"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )

    models["Random Forest"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=100,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )

    # XGBoost has no class_weight option -- scale_pos_weight is its
    # equivalent: it multiplies up the loss contribution of the minority
    # (default=1) class by roughly (count of 0s / count of 1s).
    models["XGBoost"] = XGBClassifier(
        n_estimators=100,
        scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
    )

    # LightGBM offers both `is_unbalance=True` (automatic) and
    # `scale_pos_weight` (explicit, same formula as XGBoost). We use the
    # explicit scale_pos_weight so it's the exact same number as XGBoost's
    # (fair comparison) and so it's directly tunable by Optuna later.
    models["LightGBM"] = LGBMClassifier(
        n_estimators=100,
        scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_SEED,
        verbose=-1,
    )

    return models


def cross_validate_metrics(
    model_template: Any, X: pd.DataFrame, y: pd.Series, cv: StratifiedKFold
) -> dict[str, float]:
    """Runs stratified K-fold CV for one model and returns the average
    ROC-AUC, PR-AUC and default-class recall across folds, all computed with
    a fresh clone of `model_template` fit on each fold's training rows only
    (never touching the other folds, let alone the held-out test set).
    """
    roc_aucs, pr_aucs, recalls = [], [], []
    for train_idx, val_idx in cv.split(X, y):
        X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

        fold_model = clone(model_template)
        fold_model.fit(X_tr, y_tr)
        proba = fold_model.predict_proba(X_val)[:, 1]
        pred = (proba >= 0.5).astype(int)

        roc_aucs.append(roc_auc_score(y_val, proba))
        pr_aucs.append(average_precision_score(y_val, proba))
        recalls.append(recall_score(y_val, pred, pos_label=1, zero_division=0))

    return {
        "cv_roc_auc": float(np.mean(roc_aucs)),
        "cv_pr_auc": float(np.mean(pr_aucs)),
        "cv_recall_default": float(np.mean(recalls)),
    }


def print_stage1_comparison(
    step6_metrics: list[dict[str, Any]], balanced_cv_metrics: dict[str, dict[str, float]]
) -> None:
    """Prints Step 6's original test-set numbers next to Stage 1's balanced
    cross-validation numbers, so the before/after effect of class weighting
    on recall is visible at a glance."""
    step6_by_name = {m["model_name"]: m for m in step6_metrics}

    rows = []
    for name, cv_result in balanced_cv_metrics.items():
        step6 = step6_by_name.get(name, {})
        rows.append(
            {
                "Model": name,
                "Step 6 test ROC-AUC": step6.get("roc_auc"),
                "Step 6 test Recall(1)": step6.get("recall_default"),
                "Step 7 CV ROC-AUC": cv_result["cv_roc_auc"],
                "Step 7 CV PR-AUC": cv_result["cv_pr_auc"],
                "Step 7 CV Recall(1)": cv_result["cv_recall_default"],
            }
        )
    table_df = pd.DataFrame(rows).sort_values("Step 7 CV ROC-AUC", ascending=False)

    print("=" * 100)
    print("STAGE 1: Step 6 (unbalanced, test set) vs. Step 7 balanced-but-untuned (5-fold CV, train set only)")
    print("=" * 100)
    print(table_df.round(4).to_string(index=False))
    print(
        "\nNote: the 'Step 6 test' columns are the ORIGINAL held-out test-set numbers "
        "from model/artifacts/baseline_step6/model_metrics.json, shown for context only. "
        "The 'Step 7 CV' columns -- which decide the winning model type below -- come "
        "exclusively from cross-validation on the training set; the test set was not "
        "used to produce them."
    )
    print("=" * 100)


# ---------------------------------------------------------------------------
# Stage 2: Optuna tuning of the winning model type.
# ---------------------------------------------------------------------------

def build_trial_model(
    trial: "optuna.trial.BaseTrial", model_name: str, scale_pos_weight: float
) -> Any:
    """Given an Optuna trial (or an optuna.trial.FixedTrial replaying a
    specific set of params), builds the corresponding model with suggested
    hyperparameters. This is the one place the search space for each model
    type is defined.
    """
    if model_name == "Logistic Regression":
        c = trial.suggest_float("C", 1e-3, 1e2, log=True)
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        C=c,
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                ),
            ]
        )

    if model_name == "Random Forest":
        n_estimators = trial.suggest_int("n_estimators", 100, 500, step=50)
        max_depth = trial.suggest_int("max_depth", 3, 20)
        min_samples_split = trial.suggest_int("min_samples_split", 2, 20)
        min_samples_leaf = trial.suggest_int("min_samples_leaf", 1, 10)
        max_features = trial.suggest_categorical("max_features", ["sqrt", "log2", None])
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        min_samples_split=min_samples_split,
                        min_samples_leaf=min_samples_leaf,
                        max_features=max_features,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    if model_name == "XGBoost":
        return XGBClassifier(
            max_depth=trial.suggest_int("max_depth", 3, 10),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            n_estimators=trial.suggest_int("n_estimators", 100, 500, step=50),
            min_child_weight=trial.suggest_int("min_child_weight", 1, 10),
            subsample=trial.suggest_float("subsample", 0.5, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
            scale_pos_weight=trial.suggest_float(
                "scale_pos_weight", scale_pos_weight * 0.5, scale_pos_weight * 1.5
            ),
            random_state=RANDOM_SEED,
            eval_metric="logloss",
        )

    if model_name == "LightGBM":
        return LGBMClassifier(
            max_depth=trial.suggest_int("max_depth", 3, 10),
            num_leaves=trial.suggest_int("num_leaves", 15, 127),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            n_estimators=trial.suggest_int("n_estimators", 100, 500, step=50),
            min_child_samples=trial.suggest_int("min_child_samples", 5, 50),
            subsample=trial.suggest_float("subsample", 0.5, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
            scale_pos_weight=trial.suggest_float(
                "scale_pos_weight", scale_pos_weight * 0.5, scale_pos_weight * 1.5
            ),
            random_state=RANDOM_SEED,
            verbose=-1,
        )

    raise ValueError(f"No hyperparameter search space defined for '{model_name}'")


def make_objective(
    model_name: str,
    X: pd.DataFrame,
    y: pd.Series,
    cv: StratifiedKFold,
    scale_pos_weight: float,
) -> Callable[["optuna.trial.Trial"], float]:
    """Builds the Optuna objective function. It only ever sees the training
    set (X, y) -- the test set is never passed in here."""

    def objective(trial: "optuna.trial.Trial") -> float:
        model = build_trial_model(trial, model_name, scale_pos_weight)
        roc_aucs = []
        for train_idx, val_idx in cv.split(X, y):
            fold_model = clone(model)
            fold_model.fit(X.iloc[train_idx], y.iloc[train_idx])
            proba = fold_model.predict_proba(X.iloc[val_idx])[:, 1]
            roc_aucs.append(roc_auc_score(y.iloc[val_idx], proba))
        return float(np.mean(roc_aucs))

    return objective


# ---------------------------------------------------------------------------
# Final, single evaluation on the held-out test set.
# ---------------------------------------------------------------------------

def evaluate_on_test_set(
    model: Any, X_test: pd.DataFrame, y_test: pd.Series, threshold: float
) -> dict[str, Any]:
    """The ONE place the test set is used in this entire script. Computes
    the same metric definitions as model/train.py (ROC-AUC, precision/
    recall/F1 for the default class, confusion matrix, KS statistic via the
    shared compute_ks_statistic imported from model/train.py), plus PR-AUC."""
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)

    return {
        "threshold_used": threshold,
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "precision_default": float(precision_score(y_test, pred, pos_label=1, zero_division=0)),
        "recall_default": float(recall_score(y_test, pred, pos_label=1, zero_division=0)),
        "f1_default": float(f1_score(y_test, pred, pos_label=1, zero_division=0)),
        "ks_statistic": compute_ks_statistic(y_test, proba),
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
    }


def print_final_comparison(
    model_name: str,
    step6_metrics: list[dict[str, Any]],
    balanced_cv_metrics: dict[str, dict[str, float]],
    tuned_test_metrics: dict[str, Any],
) -> None:
    step6 = next((m for m in step6_metrics if m["model_name"] == model_name), {})
    balanced_cv = balanced_cv_metrics[model_name]

    print("=" * 100)
    print(f"3-WAY COMPARISON for the winning model type: {model_name}")
    print("=" * 100)
    comparison_df = pd.DataFrame(
        [
            {
                "Stage": "Step 6 baseline (test set, unbalanced, untuned)",
                "ROC-AUC": step6.get("roc_auc"),
                "PR-AUC": None,
                "Recall (default)": step6.get("recall_default"),
                "F1 (default)": step6.get("f1_default"),
                "KS": step6.get("ks_statistic"),
            },
            {
                "Stage": "Step 7 balanced, untuned (5-fold CV, train set)",
                "ROC-AUC": balanced_cv["cv_roc_auc"],
                "PR-AUC": balanced_cv["cv_pr_auc"],
                "Recall (default)": balanced_cv["cv_recall_default"],
                "F1 (default)": None,
                "KS": None,
            },
            {
                "Stage": "Step 7 tuned (final, test set, ONE-TIME evaluation)",
                "ROC-AUC": tuned_test_metrics["roc_auc"],
                "PR-AUC": tuned_test_metrics["pr_auc"],
                "Recall (default)": tuned_test_metrics["recall_default"],
                "F1 (default)": tuned_test_metrics["f1_default"],
                "KS": tuned_test_metrics["ks_statistic"],
            },
        ]
    )
    print(comparison_df.round(4).to_string(index=False))
    print(
        f"\nClassification threshold used for the final tuned model's "
        f"Recall/F1/confusion matrix: {tuned_test_metrics['threshold_used']} "
        f"-- PROVISIONAL. Step 8 will set this properly based on the "
        f"credit-score / risk-band design, not arbitrarily here."
    )
    print(f"Final tuned confusion matrix [[TN, FP], [FN, TP]]: "
          f"{tuned_test_metrics['confusion_matrix']}")
    print("=" * 100)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    # --- Safeguard: back up Step 6 before anything in model/artifacts/ is
    # overwritten. Also gives us Step 6's test-set numbers for the tables
    # below, read back from the backup (not re-derived).
    step6_backup = backup_step6_artifacts()
    step6_all_metrics = step6_backup["all_model_metrics"]

    # --- Load the exact same preprocessed train/test data and feature
    # list Step 6 used -- no new preprocessing is done in this script.
    X_train, y_train, X_test, y_test = load_data()

    scale_pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"Training set class balance -> scale_pos_weight = {scale_pos_weight:.3f} "
          f"({(y_train == 0).sum()} non-defaults / {(y_train == 1).sum()} defaults)")

    # One StratifiedKFold splitter, reused for BOTH the Stage 1 model-type
    # comparison AND the Stage 2 Optuna tuning of the winner, so every
    # ROC-AUC number in this script is measured on identical folds.
    cv = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)

    # --- STAGE 1: balanced-but-untuned models, scored with CV on train only.
    balanced_models = build_balanced_models(scale_pos_weight)
    balanced_cv_metrics: dict[str, dict[str, float]] = {}
    for name, model in balanced_models.items():
        print(f"Cross-validating balanced {name}...")
        balanced_cv_metrics[name] = cross_validate_metrics(model, X_train, y_train, cv)

    print_stage1_comparison(step6_all_metrics, balanced_cv_metrics)

    # --- MODEL SELECTION RULE: pick the winner by CV ROC-AUC alone. CV
    # PR-AUC and CV recall are supporting diagnostics only (already printed
    # above), not part of this decision.
    winner_name = max(balanced_cv_metrics, key=lambda n: balanced_cv_metrics[n]["cv_roc_auc"])
    print(f"\nWinning model type (by CV ROC-AUC): {winner_name}\n")

    # --- STAGE 2: Optuna hyperparameter tuning of the winner, CV on train only.
    sampler = TPESampler(seed=RANDOM_SEED)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    objective = make_objective(winner_name, X_train, y_train, cv, scale_pos_weight)
    study.optimize(objective, n_trials=N_OPTUNA_TRIALS)

    print(f"\nBest CV ROC-AUC found: {study.best_value:.4f}")
    print(f"Best hyperparameters: {study.best_params}")

    # Rebuild the winning model with its best hyperparameters by replaying
    # them through a FixedTrial (same build_trial_model() used during
    # search), then refit on the FULL training set.
    fixed_trial = optuna.trial.FixedTrial(study.best_params)
    final_model = build_trial_model(fixed_trial, winner_name, scale_pos_weight)
    final_model.fit(X_train, y_train)

    # --- FINAL TEST-SET EVALUATION: the test set is used exactly once,
    # right here, purely for reporting -- never for the decisions above.
    tuned_test_metrics = evaluate_on_test_set(
        final_model, X_test, y_test, FINAL_REPORT_THRESHOLD
    )

    print_final_comparison(
        winner_name, step6_all_metrics, balanced_cv_metrics, tuned_test_metrics
    )

    # --- Save the tuned model + hyperparameters + metrics. The Step 6
    # backup above already protects the original files from being lost.
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, MODEL_PATH)
    print(f"\nSaved tuned model to {MODEL_PATH}")

    with open(BEST_PARAMS_PATH, "w") as f:
        json.dump(
            {
                "model_name": winner_name,
                "best_params": study.best_params,
                "best_cv_roc_auc": study.best_value,
                "n_trials": N_OPTUNA_TRIALS,
                "n_cv_folds": N_CV_FOLDS,
                "random_state": RANDOM_SEED,
            },
            f,
            indent=2,
        )
    print(f"Saved best hyperparameters to {BEST_PARAMS_PATH}")

    with open(METRICS_PATH, "w") as f:
        json.dump(
            {
                "step6_baseline_test_metrics": step6_all_metrics,
                "step7_balanced_cv_metrics": balanced_cv_metrics,
                "step7_winning_model_type": winner_name,
                "step7_best_params": study.best_params,
                "step7_tuned_test_metrics": tuned_test_metrics,
                "note": (
                    "step6_baseline_test_metrics and step7_tuned_test_metrics "
                    "were both measured on data/processed/test.csv. "
                    "step7_balanced_cv_metrics is 5-fold stratified "
                    "cross-validation on data/processed/train.csv only. "
                    f"tuned_test_metrics' threshold ({FINAL_REPORT_THRESHOLD}) "
                    "is provisional -- Step 8 sets it properly."
                ),
            },
            f,
            indent=2,
        )
    print(f"Saved updated metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
