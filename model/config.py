"""
Shared settings for the whole project.

Per project rule, this is the ONLY place that holds feature lists, thresholds
and other shared constants. Other scripts (data generation, preprocessing,
training, the API, the dashboard) should import from here instead of
re-typing these values, so everything stays consistent if we ever change one.
"""

# Used everywhere we need randomness (data generation, train/test splits,
# model training) so results are reproducible: running the same code twice
# gives the exact same numbers.
RANDOM_SEED: int = 42

# Number of synthetic MSME rows to generate by default.
N_COMPANIES: int = 5_000

# Target share of companies labelled as "default" (credit_default_status = 1)
# in the synthetic dataset. See docs/data_dictionary.md, section 5.
TARGET_DEFAULT_RATE: float = 0.15

# Risk bands used to turn a predicted default probability into a 300-900
# credit score and a human-readable risk label. Do not change without asking
# (see CLAUDE.md).
RISK_BANDS = {
    "Low Risk": {"min_score": 750, "max_probability": 0.20},
    "Medium Risk": {"min_score": 600, "max_probability": 0.50},
    "High Risk": {"min_score": 300, "max_probability": 1.01},
}

# Columns that identify a row but carry no predictive information.
# These must NEVER be fed into the model as features.
ID_COLUMNS = ["company_id", "company_name"]

# The target column the model learns to predict.
TARGET_COLUMN = "credit_default_status"
