"""
Step 6 — Train and compare baseline models.

Trains 4 baseline classifiers on data/processed/train.csv, evaluates them on
data/processed/test.csv, and saves the best one. No hyperparameter tuning
yet (that's Step 7) -- every model below uses standard/reasonable default
settings.

WHY ROC-AUC AND KS INSTEAD OF ACCURACY (read this first)
----------------------------------------------------------------------------
Our target `credit_default_status` is imbalanced: only ~15% of companies
default, ~85% don't. That makes plain accuracy a misleading scorecard.

A model that just predicts "0 (no default)" for EVERY single company would
score ~85% accuracy without learning anything at all -- it would be
completely useless for a lender, since it would approve every risky company
too. Accuracy rewards getting the big, easy majority class right and hides
how badly a model does on the minority class we actually care about (who's
going to default).

So instead we use:
- **ROC-AUC**: asks "if I pick one random defaulter and one random
  non-defaulter, how often does the model correctly rank the defaulter as
  riskier?" It's 0.5 for a random/useless model and 1.0 for a perfect one,
  and it doesn't care how many companies are in each class, so the 85/15
  imbalance doesn't distort it the way accuracy does.
- **Precision/Recall/F1 for the default (1) class specifically**: these look
  ONLY at how well the model finds and correctly flags actual defaulters,
  instead of being watered down by the easy 85% majority class.
- **KS (Kolmogorov-Smirnov) statistic**: a classic credit-scoring metric.
  It measures how well the model's predicted probabilities SEPARATE good
  companies from bad ones. Concretely: take all the predicted default
  probabilities for companies that actually defaulted, and all the
  predicted probabilities for companies that didn't -- KS is the biggest
  gap between those two groups' distributions (0 = the model can't tell
  them apart at all, i.e. same distribution; 1 = perfect separation, i.e.
  completely different distributions). Indian lenders and credit bureaus
  commonly expect a usable scorecard to have KS of roughly 0.3-0.5+.

How to run:
    python model/train.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import FEATURE_COLUMNS, RANDOM_SEED, TARGET_COLUMN  # noqa: E402

TRAIN_PATH = PROJECT_ROOT / "data" / "processed" / "train.csv"
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "model_metrics.json"

N_ESTIMATORS = 100  # standard default for tree-ensemble baselines

# LightGBM is an optional dependency (`pip install lightgbm`). The project
# allows either XGBoost or LightGBM, so if it isn't installed we skip it
# with a clear warning instead of crashing the whole comparison.
try:
    from lightgbm import LGBMClassifier

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


def load_data() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Loads the processed train/test CSVs and splits each into features
    (X) and target (y), using the feature list and target name from
    model/config.py -- never hardcoded here."""
    train_df = pd.read_csv(TRAIN_PATH)
    test_df = pd.read_csv(TEST_PATH)

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]
    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]
    return X_train, y_train, X_test, y_test


def build_models() -> dict[str, Any]:
    """Builds the 3-4 candidate models, all with random_state=42 and
    standard default parameters (no tuning yet -- that's Step 7).

    Logistic Regression and Random Forest can't handle NaN in scikit-learn,
    so each is wrapped in a Pipeline that imputes the (GST-only) missing
    values with the column median, fit ONLY on the training data. Because
    it lives inside the Pipeline, calling .fit(X_train) fits the imputer's
    medians on training data alone, and .predict(X_test) just applies those
    same medians to the test set -- so no information from the test set
    leaks into training.

    XGBoost and LightGBM handle NaN natively, so they train directly on the
    raw data with the missing GST values left intact -- imputing would
    throw away the useful "value is missing" signal for free.
    """
    models: dict[str, Any] = {}

    # --- a. Logistic Regression -------------------------------------------
    # Simple linear baseline. Needs imputation (no NaN support) and benefits
    # from scaling, since it's sensitive to features being on very
    # different scales (e.g. rupee amounts in the lakhs vs. a 0-1 ratio).
    models["Logistic Regression"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
        ]
    )

    # --- b. Random Forest --------------------------------------------------
    # Tree ensemble baseline. Needs imputation too (scikit-learn's forest
    # implementation doesn't accept NaN), but no scaling -- trees split on
    # raw thresholds regardless of a feature's scale.
    models["Random Forest"] = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=N_ESTIMATORS, random_state=RANDOM_SEED
                ),
            ),
        ]
    )

    # --- c. XGBoost ----------------------------------------------------
    # Handles NaN natively: trains on the raw data, GST NaNs and all.
    models["XGBoost"] = XGBClassifier(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
    )

    # --- d. LightGBM (if installed) ----------------------------------------
    if LIGHTGBM_AVAILABLE:
        models["LightGBM"] = LGBMClassifier(
            n_estimators=N_ESTIMATORS, random_state=RANDOM_SEED, verbose=-1
        )
    else:
        warnings.warn(
            "lightgbm is not installed -- skipping the LightGBM model. "
            "Run `pip install lightgbm` and re-run this script to include it."
        )

    return models


def compute_ks_statistic(y_true: pd.Series, y_pred_proba: np.ndarray) -> float:
    """Kolmogorov-Smirnov statistic: the maximum distance between the
    predicted-probability distribution of actual defaulters (y_true == 1)
    and actual non-defaulters (y_true == 0). See the module docstring above
    for what this means in plain English. 0 = no separation, 1 = perfect
    separation."""
    proba_defaulters = y_pred_proba[y_true == 1]
    proba_non_defaulters = y_pred_proba[y_true == 0]
    return float(ks_2samp(proba_defaulters, proba_non_defaulters).statistic)


def evaluate_model(
    name: str, model: Any, X_test: pd.DataFrame, y_test: pd.Series
) -> dict[str, Any]:
    """Evaluates a fitted model on the test set and returns a dict of
    metrics appropriate for an imbalanced credit-risk target (see module
    docstring for why accuracy is NOT used here)."""
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    cm = confusion_matrix(y_test, y_pred)

    return {
        "model_name": name,
        "roc_auc": float(roc_auc_score(y_test, y_pred_proba)),
        "precision_default": float(precision_score(y_test, y_pred, pos_label=1)),
        "recall_default": float(recall_score(y_test, y_pred, pos_label=1)),
        "f1_default": float(f1_score(y_test, y_pred, pos_label=1)),
        "ks_statistic": compute_ks_statistic(y_test, y_pred_proba),
        "confusion_matrix": cm.tolist(),  # [[TN, FP], [FN, TP]]
    }


def print_comparison_table(results: list[dict[str, Any]]) -> None:
    """Prints all models side by side, sorted by ROC-AUC (best first)."""
    table_df = pd.DataFrame(
        [
            {
                "Model": r["model_name"],
                "ROC-AUC": r["roc_auc"],
                "Precision (default)": r["precision_default"],
                "Recall (default)": r["recall_default"],
                "F1 (default)": r["f1_default"],
                "KS statistic": r["ks_statistic"],
            }
            for r in results
        ]
    ).sort_values("ROC-AUC", ascending=False)

    print("=" * 78)
    print("MODEL COMPARISON (sorted by ROC-AUC)")
    print("=" * 78)
    print(table_df.round(4).to_string(index=False))
    print()

    print("Confusion matrices (rows = actual, columns = predicted; "
          "format: [[TN, FP], [FN, TP]]):")
    for r in sorted(results, key=lambda r: r["roc_auc"], reverse=True):
        print(f"  {r['model_name']}: {r['confusion_matrix']}")
    print("=" * 78)


def main() -> None:
    X_train, y_train, X_test, y_test = load_data()

    models = build_models()
    results = []
    fitted_models = {}

    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)
        fitted_models[name] = model
        results.append(evaluate_model(name, model, X_test, y_test))

    print_comparison_table(results)

    # Pick the best model by ROC-AUC and save it.
    best_result = max(results, key=lambda r: r["roc_auc"])
    best_name = best_result["model_name"]
    best_model = fitted_models[best_name]

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)
    print(f"\nBest model: {best_name} (ROC-AUC = {best_result['roc_auc']:.4f})")
    print(f"Saved best model to {MODEL_PATH}")

    with open(METRICS_PATH, "w") as f:
        json.dump(
            {
                "best_model": best_name,
                "best_model_metrics": best_result,
                "all_model_metrics": results,
            },
            f,
            indent=2,
        )
    print(f"Saved metrics for all models to {METRICS_PATH}")


if __name__ == "__main__":
    main()
