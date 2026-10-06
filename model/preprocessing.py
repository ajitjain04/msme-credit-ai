"""
Step 5 — Preprocessing pipeline.

Turns the raw synthetic CSV (data/synthetic/msme_alternative_data.csv) into
model-ready train/test splits. This script does NOT train any model — it
only prepares the data for Step 6.

What it does, in order:
1. Loads the raw CSV.
2. Drops the identifier columns (company_id, company_name) -- never model
   inputs, per docs/data_dictionary.md.
3. Adds the 3 derived ratio features from the data dictionary's
   "Features we may derive later" section.
4. Leaves the 3 nullable GST columns as NaN (does NOT impute them) --
   XGBoost/LightGBM handle NaN natively, and `has_gst_registration` already
   tells the model *why* they're missing.
5. Label-encodes the 2 categorical columns (business_category, state) into
   integer codes, saving the code mapping so it can be reused later (e.g.
   by the API) to encode new companies the same way.
6. Splits into train/test (80/20), stratified on credit_default_status.
7. Saves data/processed/train.csv and data/processed/test.csv.

How to run:
    python model/preprocessing.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import (  # noqa: E402
    FEATURE_COLUMNS,
    ID_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMN,
)

RAW_DATA_PATH = PROJECT_ROOT / "data" / "synthetic" / "msme_alternative_data.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TRAIN_PATH = PROCESSED_DIR / "train.csv"
TEST_PATH = PROCESSED_DIR / "test.csv"

ARTIFACTS_DIR = PROJECT_ROOT / "model" / "artifacts"
CATEGORY_ENCODING_PATH = ARTIFACTS_DIR / "category_encodings.json"

# The 2 raw categorical columns we label-encode, and the new integer-coded
# column names we create for them. Kept here (not in config.py) because
# they're an implementation detail of HOW we encode, not a feature list.
CATEGORICAL_COLUMNS = {
    "business_category": "business_category_encoded",
    "state": "state_encoded",
}

TEST_SIZE = 0.20


def add_derived_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Adds the 3 derived ratio features from docs/data_dictionary.md.

    These describe a company's financial shape more directly than the raw
    rupee amounts do, which tends to help tree models split more cleanly.

    gst_to_bank_turnover_ratio will be NaN for unregistered firms, because
    annual_turnover_gst itself is NaN for them -- that's expected and
    intentional, exactly like the source GST columns (see data dictionary,
    section 3).
    """
    df = df.copy()
    df["net_cash_margin"] = (
        df["avg_monthly_inflow"] - df["avg_monthly_outflow"]
    ) / df["avg_monthly_inflow"]
    df["cash_buffer_ratio"] = df["min_ending_balance_avg"] / df["avg_monthly_outflow"]
    df["gst_to_bank_turnover_ratio"] = df["annual_turnover_gst"] / (
        12 * df["avg_monthly_inflow"]
    )
    return df


def encode_categoricals(
    df: pd.DataFrame, columns: dict[str, str]
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Label-encodes each categorical column into a new integer column.

    Why label/ordinal encoding instead of one-hot encoding:
    - Tree-based models (XGBoost/LightGBM) split on "is this value <= X?",
      so they don't need categories spread across separate 0/1 columns the
      way linear models do -- an integer code works fine for a tree to
      split on.
    - `business_category` (5 values) and `state` (15 values) would become
      20 extra 0/1 columns with one-hot encoding. That clutters the SHAP
      summary plots we want in a later step -- one bar per column, so one
      category would get split across many thin, hard-to-read bars instead
      of one clear "business_category" bar.
    - Label encoding assigns an arbitrary order (alphabetical here) to the
      categories. That's safe for trees because a tree can still carve out
      any individual code value with its own split; it does NOT imply the
      categories are secretly ordered (e.g. it does NOT mean "retail < food").

    Returns the encoded dataframe plus the mapping used, so the exact same
    mapping can be re-applied later (e.g. when the API scores a new
    company) instead of being re-derived and possibly coming out different.
    """
    df = df.copy()
    mappings: dict[str, dict[str, int]] = {}
    for raw_col, encoded_col in columns.items():
        categories = sorted(df[raw_col].dropna().unique())
        mapping = {category: code for code, category in enumerate(categories)}
        df[encoded_col] = df[raw_col].map(mapping)
        mappings[raw_col] = mapping
    return df, mappings


def preprocess(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Runs the full preprocessing pipeline on the raw dataframe and returns
    the processed dataframe (features + target, identifiers dropped) plus
    the category encoding mappings."""

    # Step 2: drop identifier columns. They carry no predictive signal and
    # must never reach the model.
    df = raw_df.drop(columns=ID_COLUMNS)

    # Step 3: derived ratio features.
    df = add_derived_ratios(df)

    # Step 4: the 3 nullable GST columns are already NaN for unregistered
    # firms (built that way in data/generate_data.py) and we deliberately
    # do NOT fill them in here -- XGBoost/LightGBM split around missing
    # values natively, and `has_gst_registration` stays in the feature list
    # as the explicit "why is this missing" signal.

    # Step 5: label-encode the categorical columns.
    df, category_mappings = encode_categoricals(df, CATEGORICAL_COLUMNS)
    df = df.drop(columns=list(CATEGORICAL_COLUMNS.keys()))

    return df, category_mappings


def split_train_test(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """80/20 train/test split, stratified on the target so the ~15% default
    rate is preserved in both splits."""
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=df[TARGET_COLUMN],
    )
    return train_df, test_df


def print_validation_summary(
    full_df: pd.DataFrame, train_df: pd.DataFrame, test_df: pd.DataFrame
) -> None:
    """Prints a short sanity-check summary of the processed data."""
    print("=" * 70)
    print("PREPROCESSING VALIDATION SUMMARY")
    print("=" * 70)

    feature_cols = [c for c in full_df.columns if c != TARGET_COLUMN]
    print(f"Final feature count: {len(feature_cols)}")
    print(f"Feature columns match model/config.py FEATURE_COLUMNS: "
          f"{set(feature_cols) == set(FEATURE_COLUMNS)}")

    print(f"\nTrain shape: {train_df.shape}")
    print(f"Test shape:  {test_df.shape}")

    overall_rate = full_df[TARGET_COLUMN].mean()
    train_rate = train_df[TARGET_COLUMN].mean()
    test_rate = test_df[TARGET_COLUMN].mean()
    print(f"\nDefault rate overall: {overall_rate:.2%}")
    print(f"Default rate in train: {train_rate:.2%} "
          f"(diff from overall: {abs(train_rate - overall_rate):.2%})")
    print(f"Default rate in test:  {test_rate:.2%} "
          f"(diff from overall: {abs(test_rate - overall_rate):.2%})")
    rate_preserved = (
        abs(train_rate - overall_rate) < 0.01 and abs(test_rate - overall_rate) < 0.01
    )
    print(f"Default rate preserved within ~1% in both splits: {rate_preserved}")

    leaked_ids = [c for c in feature_cols if c in ID_COLUMNS]
    print(f"\nNo identifier columns leaked into features: {len(leaked_ids) == 0}")

    print(f"\nMissing values in train (expected only in the 3 GST-derived "
          f"columns):")
    missing = train_df.isna().sum()
    missing = missing[missing > 0]
    for col, count in missing.items():
        print(f"  {col}: {count:,} ({count / len(train_df):.1%})")

    print("\nFinal feature list:")
    for col in feature_cols:
        print(f"  - {col}")
    print("=" * 70)


def main() -> None:
    raw_df = pd.read_csv(RAW_DATA_PATH)
    processed_df, category_mappings = preprocess(raw_df)

    train_df, test_df = split_train_test(processed_df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(TRAIN_PATH, index=False)
    test_df.to_csv(TEST_PATH, index=False)
    print(f"Saved {len(train_df):,} training rows to {TRAIN_PATH}")
    print(f"Saved {len(test_df):,} test rows to {TEST_PATH}")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATEGORY_ENCODING_PATH, "w") as f:
        json.dump(category_mappings, f, indent=2)
    print(f"Saved category encodings to {CATEGORY_ENCODING_PATH}")

    print_validation_summary(processed_df, train_df, test_df)


if __name__ == "__main__":
    main()
