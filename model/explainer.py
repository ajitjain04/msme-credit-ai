"""
Step 9 — SHAP explanations for the tuned model.

This script does NOT retrain or change the model at all. It loads the
already-tuned model from model/artifacts/model.joblib (saved by
model/tune.py) and explains its predictions two ways:

  GLOBAL: across the whole test set, which features matter most overall,
  and whether a high or low value of each one tends to push risk up or
  down (the "beeswarm" plot).

  LOCAL: for one specific company, which features personally pushed ITS
  score up or down, and by how much -- this is what the dashboard (Step 12)
  will show a loan officer as "why did this company get this score".

WHAT A SHAP VALUE ACTUALLY MEANS (plain-language version)
----------------------------------------------------------------------------
Think of the model's starting guess for ANY company, before it has looked
at that company's details, as a blank credit application sitting on a
desk -- some average, "I know nothing about you yet" risk level. A SHAP
value is how many points that specific company's answer to ONE question
on the application (e.g. "how many bounced payments?") moved the final
decision up or down from that starting guess. Add up every question's
nudge, starting guess included, and you get back exactly the model's final
answer for that company -- so SHAP values are literally the fully-itemised
receipt for one prediction, not just a vague "this feature seems important".

WHY shap.LinearExplainer (NOT shap.TreeExplainer) FOR THIS MODEL
----------------------------------------------------------------------------
Step 7's winning, tuned model is Logistic Regression -- a LINEAR model: its
raw output is just (coefficient . feature_values) + intercept. SHAP has a
dedicated explainer for exactly this shape of model, shap.LinearExplainer,
which computes EXACT SHAP values in closed form (no sampling/approximation
needed) because a linear model's contributions decompose perfectly by
construction. shap.TreeExplainer is a different, tree-specific algorithm
(it walks decision paths through a tree ensemble) and does not apply to a
linear model at all, and the generic shap.KernelExplainer would work but is
slower and only approximate -- so LinearExplainer is both the correct and
the cheapest choice here.

Because Logistic Regression needs imputed + scaled input (unlike
XGBoost/LightGBM, which take raw features with NaN directly), SHAP values
are computed on the TRANSFORMED features here -- see
build_shap_explainer() below. If a tree model ever wins Step 7's model
selection instead, build_shap_explainer() is written as a type-based branch
specifically so it can be extended with an `elif` for TreeExplainer -- no
other function in this file would need to change (see the comment inside
build_shap_explainer()).

How to run:
    python model/explainer.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional, Union

import matplotlib

matplotlib.use("Agg")  # write PNGs to disk; never try to pop up a GUI window

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import FEATURE_COLUMNS, RANDOM_SEED  # noqa: E402
from model.scoring import assign_risk_band, probability_to_score  # noqa: E402
from model.train import load_data  # noqa: E402

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"

IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
GLOBAL_BAR_PATH = IMAGES_DIR / "shap_global_importance.png"
BEESWARM_PATH = IMAGES_DIR / "shap_summary_beeswarm.png"
WATERFALL_PATH = IMAGES_DIR / "shap_waterfall_example.png"

# How many training rows SHAP uses as its "what does a typical company look
# like" reference distribution. 100 is the commonly recommended size for
# LinearExplainer/KernelExplainer-style background sets -- big enough to be
# representative, small enough to stay fast.
BACKGROUND_SAMPLE_SIZE = 100

TOP_N_CONTRIBUTORS = 5


# ---------------------------------------------------------------------------
# Building the right SHAP explainer for whatever model type is loaded.
# ---------------------------------------------------------------------------

def _build_transform_chain(preprocessing_steps: list[tuple[str, Any]]):
    """Chains a Pipeline's preprocessing steps (everything before the final
    classifier) into one function. For today's model (imputer -> scaler ->
    Logistic Regression), this applies the imputer, then the scaler -- both
    already FITTED on the training set by model/train.py / model/tune.py;
    nothing is refit here."""

    def transform(X: pd.DataFrame) -> np.ndarray:
        transformed = X
        for _, step in preprocessing_steps:
            transformed = step.transform(transformed)
        return transformed

    return transform


def build_shap_explainer(model: Any, X_background: pd.DataFrame):
    """Given the loaded model (today: a Pipeline ending in Logistic
    Regression) and a background sample of RAW features, returns:
      - explainer: the appropriate shap Explainer object
      - transform_fn: a function that turns raw features into whatever
        array `explainer` expects (identity for tree models, impute+scale
        for today's linear model)
      - clf: the final, bare classifier/regressor SHAP is actually
        explaining (useful later for sanity checks against
        clf.decision_function())

    This is the ONE place that needs a new branch if a different model
    type ever wins Step 7's model selection instead of Logistic Regression.
    """
    if isinstance(model, Pipeline):
        *preprocessing_steps, (_, clf) = model.steps
        transform_fn = _build_transform_chain(preprocessing_steps)
    else:
        # XGBoost/LightGBM train directly on raw features (NaN and all,
        # see model/train.py) -- no preprocessing to chain.
        clf = model
        transform_fn = lambda X: X  # noqa: E731

    background_transformed = transform_fn(X_background)

    if isinstance(clf, LogisticRegression):
        # Exact, closed-form SHAP values for a linear model -- see the
        # module docstring for why this (not TreeExplainer) is correct here.
        explainer = shap.LinearExplainer(clf, background_transformed)
    elif clf.__class__.__name__ in (
        "XGBClassifier",
        "LGBMClassifier",
        "RandomForestClassifier",
    ):
        # <<< If a tree model wins Step 7 instead, THIS branch activates
        # automatically -- nothing else in this file changes. >>>
        explainer = shap.TreeExplainer(clf, background_transformed)
    else:
        raise NotImplementedError(
            f"No SHAP explainer wiring defined for model type "
            f"{type(clf).__name__}. Add a branch above before explaining "
            "this kind of model."
        )

    return explainer, transform_fn, clf


def _raw_shap_values_and_base(
    explainer: Any, X_transformed: np.ndarray
) -> tuple[np.ndarray, float]:
    """Normalises whatever an explainer returns into a consistent shape:
    a (n_rows, n_features) array of SHAP values for the DEFAULT (class 1)
    outcome, and a single scalar base value.

    Why this is needed: shap.LinearExplainer on a single linear model
    already returns exactly that shape (checked below), but some explainers
    (e.g. shap.TreeExplainer on certain binary classifiers) instead return
    a LIST of two arrays/values, one per class -- this picks out index 1
    (the "default" class) in that case, so the rest of this file never has
    to care which explainer produced the numbers.
    """
    shap_values = explainer.shap_values(X_transformed)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    base_value = explainer.expected_value
    base_value = np.atleast_1d(base_value)
    base_value = float(base_value[1] if len(base_value) > 1 else base_value[0])

    return np.asarray(shap_values), base_value


# ---------------------------------------------------------------------------
# Module-level setup: load the model once, build one explainer, reuse both.
# Mirrors model/scoring.py's module-level `_MODEL` pattern.
# ---------------------------------------------------------------------------

_MODEL = joblib.load(MODEL_PATH)
_X_TRAIN_FULL, _, _, _ = load_data()
_BACKGROUND_RAW = _X_TRAIN_FULL.sample(BACKGROUND_SAMPLE_SIZE, random_state=RANDOM_SEED)
_EXPLAINER, _TRANSFORM_FN, _CLF = build_shap_explainer(_MODEL, _BACKGROUND_RAW)
_BASE_VALUE = _raw_shap_values_and_base(_EXPLAINER, _TRANSFORM_FN(_BACKGROUND_RAW.iloc[:1]))[1]


# ---------------------------------------------------------------------------
# LOCAL interpretability: explain one company.
# ---------------------------------------------------------------------------

def _coerce_to_series(features: Union[dict, pd.Series, pd.DataFrame]) -> pd.Series:
    """Accepts the same input shapes as model.scoring.score_company() and
    returns a single pandas Series, raising a clear error for anything
    else or anything missing a required feature."""
    if isinstance(features, pd.DataFrame):
        if len(features) != 1:
            raise ValueError(
                f"Expected exactly one row, got a DataFrame with {len(features)} rows."
            )
        row = features.iloc[0]
    elif isinstance(features, pd.Series):
        row = features
    elif isinstance(features, dict):
        row = pd.Series(features)
    else:
        raise TypeError(
            f"Expected a dict, pandas Series, or single-row DataFrame -- got "
            f"{type(features).__name__}."
        )

    missing = [col for col in FEATURE_COLUMNS if col not in row.index]
    if missing:
        raise ValueError(f"Missing required feature(s): {missing}")
    return row


def _safe_feature_value(value: Any) -> Optional[float]:
    """Converts one feature's raw value to float for display in a SHAP
    driver dict, WITHOUT crashing on a missing value.

    The 3 GST columns (gst_filing_regularity_score, annual_turnover_gst,
    gst_filing_delay_days_avg) and the derived gst_to_bank_turnover_ratio
    are intentionally missing for a GST-unregistered company (Step 5's
    design -- see docs/data_dictionary.md section 3): the live API's
    backend/main.py builds that row with a Python `None` for these,
    while reading the real training CSV gives `float('nan')` instead --
    this handles BOTH representations the same way, since they mean the
    exact same thing here.

    `float(None)` raises TypeError (the bug this function fixes -- see
    docs/PROGRESS_LOG.md's Step 13 entry); `float(float('nan'))` would
    have silently "succeeded" into a NaN that downstream JSON/display
    code still can't show sensibly. Returning `None` instead lets every
    downstream consumer (backend/schemas.py's ShapDriver, model/
    report_generator.py's format_driver_value()) treat "missing" as one
    explicit, deliberate value instead of a crash or a literal "nan".

    This ONLY affects what gets stored for DISPLAY -- it does not touch
    the SHAP value itself, which is computed separately (and correctly,
    via the imputed/transformed array) regardless of what this returns.
    """
    if value is None:
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(numeric_value) else numeric_value


def explain_company(
    features: Union[dict, pd.Series, pd.DataFrame], top_n: int = TOP_N_CONTRIBUTORS
) -> dict[str, Any]:
    """Explains ONE company's prediction with SHAP. This is the function
    the backend API (Step 11) and dashboard (Step 12) will call directly.

    Input: a dict / pandas Series / single-row DataFrame containing every
    column in model.config.FEATURE_COLUMNS (extra columns are ignored).

    Returns a JSON-serializable dict:
      {
        "default_probability": float,
        "base_value_logit": float,              # SHAP's starting point (log-odds), before this company's features are added
        "sum_shap_plus_base_logit": float,       # base_value_logit + sum of every feature's SHAP value below
        "top_positive_contributors": [           # push default probability UP (risk up, score down)
            {"feature": str, "value": <company's raw value, or None if missing>, "shap_value": float}, ...
        ],
        "top_negative_contributors": [           # push default probability DOWN (risk down, score up)
            {"feature": str, "value": <company's raw value, or None if missing>, "shap_value": float}, ...
        ],
      }

    "value" is None for a feature that was genuinely missing for this
    company -- in practice only the 3 nullable GST columns (and the
    derived gst_to_bank_turnover_ratio) for a GST-unregistered company,
    see _safe_feature_value() above. The SHAP value itself is still
    computed correctly in that case (via the imputed/transformed array);
    only the raw display value is None.

    SHAP values here are in LOG-ODDS space, matching the linear model's raw
    output (see the module docstring's "why LinearExplainer" section) --
    NOT directly in probability points. A positive SHAP value still always
    means "this pushed the company's risk up"; a negative one always means
    "this pushed it down". `sum_shap_plus_base_logit` reconstructs the
    model's exact log-odds output for this company -- see
    verify_shap_reconstruction() for the explicit proof.
    """
    row = _coerce_to_series(features)
    X_raw = pd.DataFrame([row[FEATURE_COLUMNS]])
    X_transformed = _TRANSFORM_FN(X_raw)

    shap_row, base_value = _raw_shap_values_and_base(_EXPLAINER, X_transformed)
    shap_row = shap_row[0]  # one row in, one row out

    probability = float(_MODEL.predict_proba(X_raw)[:, 1][0])

    contributions = [
        {"feature": feat, "value": _safe_feature_value(row[feat]), "shap_value": float(sv)}
        for feat, sv in zip(FEATURE_COLUMNS, shap_row)
    ]
    positive = sorted(
        (c for c in contributions if c["shap_value"] > 0),
        key=lambda c: c["shap_value"],
        reverse=True,
    )[:top_n]
    negative = sorted(
        (c for c in contributions if c["shap_value"] < 0),
        key=lambda c: c["shap_value"],
    )[:top_n]

    return {
        "default_probability": probability,
        "base_value_logit": base_value,
        "sum_shap_plus_base_logit": float(base_value + sum(c["shap_value"] for c in contributions)),
        "top_positive_contributors": positive,
        "top_negative_contributors": negative,
    }


def verify_shap_reconstruction(features: Union[dict, pd.Series, pd.DataFrame]) -> dict[str, Any]:
    """THE IMPORTANT SANITY CHECK: SHAP guarantees that for any one
    prediction, (sum of all its SHAP values) + (base value) exactly equals
    the model's raw output for that prediction. This function verifies that
    guarantee actually holds for our wired-up explainer -- if it didn't,
    that would mean the explainer is misconfigured (e.g. explaining the
    wrong intermediate output), not that SHAP itself is wrong.

    Checks it two ways: in log-odds space (the model's raw decision
    function) and, after applying the sigmoid, in probability space too.
    """
    row = _coerce_to_series(features)
    X_raw = pd.DataFrame([row[FEATURE_COLUMNS]])
    X_transformed = _TRANSFORM_FN(X_raw)

    explanation = explain_company(row)
    reconstructed_logit = explanation["sum_shap_plus_base_logit"]
    actual_logit = float(_CLF.decision_function(X_transformed)[0])

    reconstructed_probability = 1.0 / (1.0 + np.exp(-reconstructed_logit))
    actual_probability = float(_MODEL.predict_proba(X_raw)[:, 1][0])

    return {
        "actual_logit": actual_logit,
        "reconstructed_logit": reconstructed_logit,
        "logit_abs_diff": abs(actual_logit - reconstructed_logit),
        "actual_probability": actual_probability,
        "reconstructed_probability": reconstructed_probability,
        "probability_abs_diff": abs(actual_probability - reconstructed_probability),
        "matches_within_tolerance": abs(actual_logit - reconstructed_logit) < 1e-6,
    }


# ---------------------------------------------------------------------------
# GLOBAL interpretability: whole test set.
# ---------------------------------------------------------------------------

def compute_global_shap_values(X_test: pd.DataFrame) -> np.ndarray:
    """SHAP values for every row in the test set -- the basis for both the
    ranked-importance table and the two summary plots below."""
    X_transformed = _TRANSFORM_FN(X_test)
    shap_values, _ = _raw_shap_values_and_base(_EXPLAINER, X_transformed)
    return shap_values


def print_global_importance_table(shap_values: np.ndarray) -> None:
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    ranking = (
        pd.DataFrame({"feature": FEATURE_COLUMNS, "mean_abs_shap_value": mean_abs_shap})
        .sort_values("mean_abs_shap_value", ascending=False)
        .reset_index(drop=True)
    )
    print("=" * 70)
    print("GLOBAL FEATURE IMPORTANCE (mean |SHAP value|, log-odds, test set)")
    print("=" * 70)
    print(ranking.round(4).to_string(index=False))
    print("=" * 70)


def save_global_plots(shap_values: np.ndarray, X_test: pd.DataFrame) -> None:
    """Saves the bar (importance-only) and beeswarm (importance + direction)
    summary plots. We colour/label the beeswarm by each company's ORIGINAL,
    real-world feature value (e.g. an actual bounce count or ratio) rather
    than the standardized value Logistic Regression sees internally --
    purely a display choice, done by passing `features=X_test` separately
    from the `shap_values` array the plot is otherwise built from; it makes
    the picture readable without changing a single SHAP number."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    shap.summary_plot(
        shap_values, X_test[FEATURE_COLUMNS], plot_type="bar", show=False
    )
    plt.title("Global feature importance (mean |SHAP value|)")
    plt.tight_layout()
    plt.savefig(GLOBAL_BAR_PATH, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved global importance bar plot to {GLOBAL_BAR_PATH}")

    shap.summary_plot(shap_values, X_test[FEATURE_COLUMNS], show=False)
    plt.title("SHAP summary (importance + direction)")
    plt.tight_layout()
    plt.savefig(BEESWARM_PATH, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved SHAP beeswarm summary plot to {BEESWARM_PATH}")


def save_waterfall_plot(X_test: pd.DataFrame, row_index: int) -> None:
    """Saves a waterfall plot -- a visual version of explain_company()'s
    'starting point + each feature's nudge = final answer' story -- for one
    specific test-set company (by its position in X_test)."""
    row = X_test.iloc[row_index]
    X_raw = pd.DataFrame([row[FEATURE_COLUMNS]])
    X_transformed = _TRANSFORM_FN(X_raw)
    shap_row, base_value = _raw_shap_values_and_base(_EXPLAINER, X_transformed)

    explanation = shap.Explanation(
        values=shap_row[0],
        base_values=base_value,
        data=row[FEATURE_COLUMNS].to_numpy(),
        feature_names=FEATURE_COLUMNS,
    )
    shap.plots.waterfall(explanation, show=False)
    plt.tight_layout()
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(WATERFALL_PATH, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved SHAP waterfall plot (1 example company) to {WATERFALL_PATH}")


# ---------------------------------------------------------------------------
# Side-by-side local explanations for the safest/riskiest companies.
# ---------------------------------------------------------------------------

def print_side_by_side_examples(X_test: pd.DataFrame, y_test: pd.Series) -> None:
    """Picks the 2 safest and 2 riskiest test-set companies by predicted
    probability -- the same selection logic model/scoring.py used for its
    example printout in Step 8, re-applied here (same model, same test set,
    same sort -> same companies) -- and prints each one's explain_company()
    output plus the SHAP reconstruction sanity check, so the explanations
    can be read directly against each other."""
    probabilities = _MODEL.predict_proba(X_test[FEATURE_COLUMNS])[:, 1]
    order = np.argsort(probabilities)
    example_positions = list(order[:2]) + list(order[-2:])
    labels = ["SAFEST #1", "SAFEST #2", "RISKIEST #2", "RISKIEST #1"]

    print("=" * 100)
    print("LOCAL EXPLANATIONS: 2 safest + 2 riskiest test-set companies")
    print("=" * 100)

    for label, pos in zip(labels, example_positions):
        row = X_test.iloc[pos]
        explanation = explain_company(row)
        score = probability_to_score(explanation["default_probability"])
        band = assign_risk_band(score)
        check = verify_shap_reconstruction(row)

        print(f"\n--- {label} (actual default = {int(y_test.iloc[pos])}) ---")
        print(
            f"Probability: {explanation['default_probability']:.4f}  "
            f"Score: {score}  Risk band: {band}"
        )
        print("Top contributors pushing risk UP (score down):")
        for c in explanation["top_positive_contributors"]:
            print(f"    {c['feature']:<32} value={c['value']:<12.4f} SHAP={c['shap_value']:+.4f}")
        print("Top contributors pushing risk DOWN (score up):")
        for c in explanation["top_negative_contributors"]:
            print(f"    {c['feature']:<32} value={c['value']:<12.4f} SHAP={c['shap_value']:+.4f}")
        print(
            f"Reconstruction check: base value={explanation['base_value_logit']:.6f}  "
            f"actual logit={check['actual_logit']:.6f}  reconstructed={check['reconstructed_logit']:.6f}  "
            f"diff={check['logit_abs_diff']:.2e}  OK={check['matches_within_tolerance']}"
        )

    print("=" * 100)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    _, _, X_test, y_test = load_data()

    print(f"Using background sample of {BACKGROUND_SAMPLE_SIZE} training rows "
          f"(random_state={RANDOM_SEED}) as SHAP's reference distribution.")
    print(f"Explainer type: {type(_EXPLAINER).__name__} on {type(_CLF).__name__}\n")

    # --- GLOBAL ---
    shap_values_test = compute_global_shap_values(X_test[FEATURE_COLUMNS])
    print_global_importance_table(shap_values_test)
    save_global_plots(shap_values_test, X_test)

    # --- LOCAL: one example waterfall (riskiest test-set company) ---
    probabilities = _MODEL.predict_proba(X_test[FEATURE_COLUMNS])[:, 1]
    riskiest_index = int(np.argmax(probabilities))
    save_waterfall_plot(X_test, riskiest_index)

    # --- LOCAL: side-by-side safest/riskiest + sanity check ---
    print_side_by_side_examples(X_test, y_test)


if __name__ == "__main__":
    main()
