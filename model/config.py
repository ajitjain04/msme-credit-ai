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

# The exact list of columns the model is trained on, in the order produced
# by model/preprocessing.py. This explicitly EXCLUDES the identifier
# columns (ID_COLUMNS) and the target (TARGET_COLUMN) -- per project rule,
# this is the one place feature lists live, so training, evaluation, SHAP
# explanations and the API all read from here instead of re-typing it.
#
# business_category and state are label-encoded (see
# model/preprocessing.py's CATEGORICAL_COLUMNS) into
# business_category_encoded and state_encoded. net_cash_margin,
# cash_buffer_ratio and gst_to_bank_turnover_ratio are the derived ratios
# from docs/data_dictionary.md.
FEATURE_COLUMNS = [
    "age_of_business_years",
    "business_category_encoded",
    "state_encoded",
    "employee_count",
    "avg_monthly_inflow",
    "avg_monthly_outflow",
    "min_ending_balance_avg",
    "bounce_count_last_6m",
    "account_vintage_months",
    "cash_flow_volatility",
    "has_gst_registration",
    "gst_filing_regularity_score",
    "annual_turnover_gst",
    "gst_filing_delay_days_avg",
    "upi_transaction_volume_ratio",
    "pos_terminal_active_status",
    "digital_payment_adoption_score",
    "net_cash_margin",
    "cash_buffer_ratio",
    "gst_to_bank_turnover_ratio",
]
