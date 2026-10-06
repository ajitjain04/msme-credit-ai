"""
Generates the synthetic MSME dataset described in docs/data_dictionary.md.

This script does NOT use any real company data. It builds a believable
fake dataset of Indian MSMEs (bank + GST + UPI style "alternative data")
column by column, following the ranges, category mixes and relationships
written down in docs/data_dictionary.md.

How to run:
    python data/generate_data.py

Output:
    data/synthetic/msme_alternative_data.csv
    plus a short validation summary printed to the console.

Everything uses model.config.RANDOM_SEED, so running this script twice
produces exactly the same file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Let this script be run directly (``python data/generate_data.py``) even
# though it needs to import from the ``model`` package one level up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import N_COMPANIES, RANDOM_SEED, TARGET_DEFAULT_RATE  # noqa: E402

OUTPUT_PATH = PROJECT_ROOT / "data" / "synthetic" / "msme_alternative_data.csv"


def clip(array: np.ndarray, low: float, high: float) -> np.ndarray:
    """Short alias for numpy's clip, used everywhere below to keep values
    inside the ranges written in the data dictionary."""
    return np.clip(array, low, high)


def sigmoid(x: np.ndarray) -> np.ndarray:
    """The logistic S-curve: squashes any number into the range (0, 1).
    Used to turn a 'risk score' into a default probability."""
    return 1.0 / (1.0 + np.exp(-x))


# ---------------------------------------------------------------------------
# 1. Identifiers & firmographics
# ---------------------------------------------------------------------------

def generate_firmographics(rng: np.random.Generator, n: int) -> pd.DataFrame:
    """Builds company_id, company_name, age, category, state, employee_count."""

    company_id = [f"MSME{i:06d}" for i in range(1, n + 1)]

    # Simple building blocks for realistic-sounding Indian business names.
    prefixes = [
        "Shree", "Sai", "Balaji", "Annapurna", "Kaveri", "Lakshmi", "Ganesh",
        "Maruti", "Vishwakarma", "Shiv", "Om", "Krishna", "Hanuman", "Durga",
        "Sri", "New", "National", "Royal", "Classic", "Modern",
    ]
    cores = [
        "Traders", "Enterprises", "Industries", "Textiles", "Foods",
        "Engineering Works", "Electricals", "Agencies", "Exports",
        "Plastics", "Garments", "Associates", "Suppliers", "Stores",
        "Logistics", "Fabrics", "Metals", "Bakers", "Caterers", "Solutions",
    ]
    prefix_choice = rng.choice(prefixes, size=n)
    core_choice = rng.choice(cores, size=n)
    company_name = [f"{p} {c}" for p, c in zip(prefix_choice, core_choice)]

    # Age of business: right-skewed (lots of young/mid firms, a long tail of
    # old ones). A gamma distribution naturally looks like this.
    age = rng.gamma(shape=1.9, scale=3.3, size=n)
    age = clip(age, 0.5, 40.0)
    age = np.round(age, 1)

    categories = ["retail", "trading", "services", "manufacturing", "food"]
    category_weights = [0.30, 0.25, 0.20, 0.15, 0.10]
    business_category = rng.choice(categories, size=n, p=category_weights)

    states = [
        "Maharashtra", "Uttar Pradesh", "Tamil Nadu", "Gujarat", "Rajasthan",
        "Karnataka", "West Bengal", "Madhya Pradesh", "Bihar", "Telangana",
        "Andhra Pradesh", "Kerala", "Delhi", "Punjab", "Haryana",
    ]
    # Rough weighting: bigger MSME hubs get a larger share, tapering off.
    state_weights = np.array(
        [13, 11, 10, 9, 8, 8, 7, 6, 6, 5, 5, 4, 4, 2, 2], dtype=float
    )
    state_weights /= state_weights.sum()
    state = rng.choice(states, size=n, p=state_weights)

    # Employee count: most MSMEs are tiny, a few are bigger. Mixture of three
    # uniform bands matching the dictionary's ~70/25/5 split.
    band = rng.choice([0, 1, 2], size=n, p=[0.70, 0.25, 0.05])
    employee_count = np.empty(n, dtype=int)
    employee_count[band == 0] = rng.integers(1, 11, size=(band == 0).sum())
    employee_count[band == 1] = rng.integers(11, 51, size=(band == 1).sum())
    employee_count[band == 2] = rng.integers(51, 251, size=(band == 2).sum())

    return pd.DataFrame(
        {
            "company_id": company_id,
            "company_name": company_name,
            "age_of_business_years": age,
            "business_category": business_category,
            "state": state,
            "employee_count": employee_count,
        }
    )


# ---------------------------------------------------------------------------
# 2. Banking / transaction features
# ---------------------------------------------------------------------------

def generate_banking(
    rng: np.random.Generator, df: pd.DataFrame
) -> pd.DataFrame:
    """Builds the bank-statement-derived columns.

    A single hidden "financial health" score (z_health) per company drives
    several columns together, so they move realistically as a group instead
    of being independently random: a stressed firm has a worse outflow
    ratio, a thinner cash cushion, more volatile income AND more bounces,
    all at once.
    """
    n = len(df)

    # Category multipliers: typical business scale differs by sector.
    category_scale = df["business_category"].map(
        {
            "manufacturing": 1.6,
            "trading": 1.3,
            "retail": 1.0,
            "services": 0.9,
            "food": 0.7,
        }
    ).to_numpy()

    size_factor = (df["employee_count"].to_numpy() ** 0.55) * category_scale

    # avg_monthly_inflow: log-normal (common for incomes/revenues), scaled by
    # company size, then clipped to the dictionary's range.
    log_inflow = (
        np.log(230_000)
        + 0.55 * np.log(size_factor)
        + rng.normal(0, 0.55, n)
    )
    avg_monthly_inflow = clip(np.exp(log_inflow), 50_000, 15_000_000)

    # Hidden financial-health factor. Higher = healthier business.
    z_health = rng.normal(0, 1, n)

    # Outflow ratio: healthy firms spend less than they earn, stressed firms
    # spend more.
    outflow_ratio = clip(
        0.93 - 0.07 * z_health + rng.normal(0, 0.05, n), 0.75, 1.10
    )
    avg_monthly_outflow = avg_monthly_inflow * outflow_ratio

    # Cash cushion ratio: share of monthly inflow still sitting in the
    # account at its lowest point each month.
    cushion_ratio = clip(
        0.11 + 0.07 * z_health + rng.normal(0, 0.035, n), 0.0, 0.25
    )
    min_ending_balance_avg = clip(
        avg_monthly_inflow * cushion_ratio, 0, 30_00_0000
    )

    # Cash flow volatility: how much monthly inflow swings around its
    # average. Stressed/seasonal businesses swing more.
    cash_flow_volatility = clip(
        0.30 - 0.14 * z_health + rng.normal(0, 0.09, n), 0.05, 1.50
    )

    # Bounce count: driven by the SAME stress signals (outflow exceeding
    # inflow, thin cushion), turned into a Poisson "arrival rate" of bounced
    # payments over 6 months.
    overspend = np.maximum(outflow_ratio - 0.95, 0.0)
    thin_cushion = np.maximum(0.08 - cushion_ratio, 0.0)
    bounce_lambda = clip(
        0.16 + 9.0 * overspend + 34.0 * thin_cushion + rng.normal(0, 0.35, n),
        0.0,
        None,
    )
    bounce_count_last_6m = clip(rng.poisson(bounce_lambda), 0, 15)

    # Account vintage: can't exceed the business's own age, and is usually
    # a bit shorter than it (businesses sometimes switch/open new accounts).
    #
    # Bug fix (found during Step 4 EDA): the hard cap must be FLOOR(age * 12),
    # not ROUND(age * 12). Rounding the cap can round it UP (e.g. age=2.04
    # years -> 24.48 months -> rounds to 24... but age=2.06 -> 24.72 months
    # could round to 25, which is above the true age-in-months). Using the
    # same floored cap everywhere below guarantees
    # account_vintage_months <= age_of_business_years * 12 for every row,
    # with no exceptions.
    age_months_cap = np.floor(df["age_of_business_years"].to_numpy() * 12).astype(int)
    vintage_fraction = clip(rng.beta(5, 1.5, n), 0.2, 1.0)
    account_vintage_months = np.floor(age_months_cap * vintage_fraction).astype(int)
    # Belt-and-braces: never exceed the floored age cap, and never exceed
    # the dataset-wide upper bound of 240 months.
    account_vintage_months = np.minimum(account_vintage_months, age_months_cap)
    upper_bound = np.minimum(age_months_cap, 240)
    account_vintage_months = clip(account_vintage_months, 6, upper_bound)

    out = df.copy()
    out["avg_monthly_inflow"] = np.round(avg_monthly_inflow, 2)
    out["avg_monthly_outflow"] = np.round(avg_monthly_outflow, 2)
    out["min_ending_balance_avg"] = np.round(min_ending_balance_avg, 2)
    out["bounce_count_last_6m"] = bounce_count_last_6m
    out["account_vintage_months"] = account_vintage_months
    out["cash_flow_volatility"] = np.round(cash_flow_volatility, 3)

    # Keep the hidden health factor around only for the label step later
    # (it is NOT written to the CSV — it's not a real-world observable).
    out["_z_health"] = z_health
    return out


# ---------------------------------------------------------------------------
# 3. Tax & compliance features
# ---------------------------------------------------------------------------

def generate_gst(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """Builds GST registration + filing columns, with NaN for unregistered
    firms (not zero -- see docs/data_dictionary.md section 3)."""
    n = len(df)

    annual_bank_inflow = df["avg_monthly_inflow"].to_numpy() * 12

    # Registration likelihood rises sharply once annual turnover crosses the
    # ~Rs 40 lakh GST threshold. Services firms are a little less likely to
    # be registered at the margin (many fall under lighter obligations).
    threshold = 40_00_000.0
    base_p = sigmoid((annual_bank_inflow - threshold) / 12_00_000)
    services_penalty = np.where(df["business_category"] == "services", 0.10, 0.0)
    reg_p = clip(base_p + 0.30 - services_penalty, 0.02, 0.99)
    has_gst_registration = (rng.uniform(0, 1, n) < reg_p).astype(int)

    # Compliance "discipline" factor, mildly linked to financial health:
    # businesses in cash-flow trouble are a bit more likely to file late too.
    z_compliance = 0.35 * df["_z_health"].to_numpy() + rng.normal(0, 0.9, n)

    gst_filing_regularity_score = clip(
        82 + 9 * z_compliance + rng.normal(0, 7, n), 0, 100
    )
    # Delay days: higher when regularity is lower (negative correlation),
    # plus its own noise so the relationship isn't a perfect straight line.
    gst_filing_delay_days_avg = clip(
        9 - 0.42 * (gst_filing_regularity_score - 82) + rng.normal(0, 6, n),
        0,
        90,
    )

    # Declared GST turnover tracks bank inflow but isn't identical.
    turnover_multiplier = rng.uniform(0.7, 1.1, n)
    annual_turnover_gst = annual_bank_inflow * turnover_multiplier

    out = df.copy()
    out["has_gst_registration"] = has_gst_registration
    out["gst_filing_regularity_score"] = np.round(gst_filing_regularity_score, 1)
    out["annual_turnover_gst"] = np.round(annual_turnover_gst, 2)
    out["gst_filing_delay_days_avg"] = np.round(gst_filing_delay_days_avg, 1)

    # NaN out the three GST columns for unregistered firms -- intentional
    # missingness, not zero.
    not_registered = out["has_gst_registration"] == 0
    out.loc[not_registered, "gst_filing_regularity_score"] = np.nan
    out.loc[not_registered, "annual_turnover_gst"] = np.nan
    out.loc[not_registered, "gst_filing_delay_days_avg"] = np.nan

    return out


# ---------------------------------------------------------------------------
# 4. Digital footprint
# ---------------------------------------------------------------------------

def generate_digital(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """Builds UPI / POS / digital-adoption columns, which vary a lot by
    business category (retail & food are UPI-heavy, manufacturing is not)."""
    n = len(df)

    upi_ranges = {
        "retail": (0.40, 0.90),
        "food": (0.40, 0.90),
        "services": (0.25, 0.70),
        "trading": (0.10, 0.50),
        "manufacturing": (0.02, 0.30),
    }
    pos_prob = {
        "retail": 0.55,
        "food": 0.55,
        "services": 0.20,
        "trading": 0.10,
        "manufacturing": 0.10,
    }

    upi_ratio = np.empty(n)
    pos_status = np.empty(n, dtype=int)
    for category, (low, high) in upi_ranges.items():
        mask = (df["business_category"] == category).to_numpy()
        count = mask.sum()
        if count == 0:
            continue
        upi_ratio[mask] = rng.uniform(low, high, count)
        pos_status[mask] = (
            rng.uniform(0, 1, count) < pos_prob[category]
        ).astype(int)

    upi_ratio = clip(upi_ratio, 0.0, 0.95)

    digital_payment_adoption_score = clip(
        55 * upi_ratio + 25 * pos_status + rng.normal(0, 9, n), 0, 100
    )

    out = df.copy()
    out["upi_transaction_volume_ratio"] = np.round(upi_ratio, 3)
    out["pos_terminal_active_status"] = pos_status
    out["digital_payment_adoption_score"] = np.round(
        digital_payment_adoption_score, 1
    )
    return out


# ---------------------------------------------------------------------------
# 5. Target variable: credit_default_status
# ---------------------------------------------------------------------------

def generate_default_label(
    rng: np.random.Generator, df: pd.DataFrame, target_rate: float
) -> pd.DataFrame:
    """Implements the 5-step "hidden risk score -> probability -> coin flip"
    method from docs/data_dictionary.md, section 5."""
    n = len(df)

    # --- Step 1: risk signals, each roughly standardised -------------------

    cash_margin = (
        df["avg_monthly_inflow"] - df["avg_monthly_outflow"]
    ) / df["avg_monthly_inflow"]
    cushion_ratio = df["min_ending_balance_avg"] / df["avg_monthly_outflow"].clip(lower=1)
    volatility = df["cash_flow_volatility"].to_numpy()

    # Lower margin, thinner cushion, higher volatility => higher risk.
    cash_flow_risk = (
        -2.6 * cash_margin.to_numpy()
        - 2.2 * cushion_ratio.to_numpy()
        + 1.1 * volatility
    )

    # Bounces: diminishing effect (sqrt instead of raw count).
    bounce_risk = 0.85 * np.sqrt(df["bounce_count_last_6m"].to_numpy())

    # GST discipline: unregistered firms get a moderate "unknown" penalty
    # (not the worst possible), registered firms are judged on their actual
    # filing behaviour.
    regularity = df["gst_filing_regularity_score"].to_numpy()
    delay = df["gst_filing_delay_days_avg"].to_numpy()
    unregistered = df["has_gst_registration"].to_numpy() == 0

    regularity_filled = np.where(unregistered, 55.0, regularity)
    delay_filled = np.where(unregistered, 20.0, delay)
    gst_risk = (100 - regularity_filled) / 100 * 1.6 + (delay_filled / 90) * 0.9

    # Business maturity: risk drops fast early on, then levels off.
    age = df["age_of_business_years"].to_numpy()
    vintage = df["account_vintage_months"].to_numpy()
    age_risk = 1.3 * np.exp(-age / 4.0) + 0.4 * np.exp(-vintage / 36.0)

    # Minor signals: small effects only.
    digital_protection = -0.15 * (df["digital_payment_adoption_score"].to_numpy() / 100)
    category_bump = df["business_category"].map(
        {"food": 0.10, "retail": 0.0, "services": -0.05, "trading": 0.0, "manufacturing": -0.05}
    ).to_numpy()
    size_protection = -0.10 * np.log1p(df["employee_count"].to_numpy()) / np.log1p(250)
    state_noise = rng.normal(0, 0.03, n)  # state kept to a negligible effect

    minor_signals = digital_protection + category_bump + size_protection + state_noise

    # --- Step 2: interactions ----------------------------------------------

    thin_cushion_flag = np.maximum(0.08 - cushion_ratio.to_numpy(), 0.0)
    volatility_x_thin_cushion = 2.0 * volatility * thin_cushion_flag
    young_business_flag = np.exp(-age / 4.0)
    bounce_x_young = 0.6 * bounce_risk * young_business_flag

    interactions = volatility_x_thin_cushion + bounce_x_young

    # --- Combine with roughly equal weight on the four main signals -------

    hidden_risk_score = (
        0.75 * cash_flow_risk
        + 0.55 * bounce_risk
        + 1.0 * gst_risk
        + 1.0 * age_risk
        + interactions
        + minor_signals
    )

    # --- Step 3: random "unobserved shock" ----------------------------------
    hidden_risk_score = hidden_risk_score + rng.normal(0, 0.9, n)

    # --- Step 4: logistic transform, calibrated to hit target_rate ---------
    # We search for the intercept that makes the average predicted
    # probability equal to target_rate (simple bisection on a monotonic
    # function), then draw labels from that probability.
    def mean_rate_for_intercept(intercept: float) -> float:
        return sigmoid(hidden_risk_score + intercept).mean()

    low_b, high_b = -10.0, 10.0
    for _ in range(60):
        mid = (low_b + high_b) / 2
        if mean_rate_for_intercept(mid) < target_rate:
            low_b = mid
        else:
            high_b = mid
    intercept = (low_b + high_b) / 2

    default_probability = sigmoid(hidden_risk_score + intercept)

    # --- Step 5: weighted coin flip -----------------------------------------
    credit_default_status = (rng.uniform(0, 1, n) < default_probability).astype(int)

    out = df.copy()
    out["credit_default_status"] = credit_default_status
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

# Final column order, matching docs/data_dictionary.md exactly.
COLUMN_ORDER = [
    "company_id",
    "company_name",
    "age_of_business_years",
    "business_category",
    "state",
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
    "credit_default_status",
]


def generate_dataset(n: int = N_COMPANIES, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Runs all generation steps in order and returns the final dataframe."""
    rng = np.random.default_rng(seed)

    df = generate_firmographics(rng, n)
    df = generate_banking(rng, df)
    df = generate_gst(rng, df)
    df = generate_digital(rng, df)
    df = generate_default_label(rng, df, TARGET_DEFAULT_RATE)

    # Drop the hidden helper column -- it's not a real observable feature.
    df = df.drop(columns=["_z_health"])

    return df[COLUMN_ORDER]


def print_validation_summary(df: pd.DataFrame) -> None:
    """Prints a short sanity-check summary so we can eyeball the output
    without opening the CSV."""
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Rows: {len(df):,}")
    print(f"Columns: {df.shape[1]}")

    print("\nMissing values per column (should be 0, except the 3 GST columns\n"
          "for firms without GST registration):")
    missing = df.isna().sum()
    for col, count in missing.items():
        if count > 0:
            print(f"  {col}: {count:,} ({count / len(df):.1%})")
    if missing.sum() == 0:
        print("  (none)")

    default_rate = df["credit_default_status"].mean()
    print(f"\nDefault rate: {default_rate:.2%} (target ~{TARGET_DEFAULT_RATE:.0%})")

    print("\nKey numeric columns (mean / median):")
    for col in [
        "avg_monthly_inflow",
        "bounce_count_last_6m",
        "gst_filing_regularity_score",
        "age_of_business_years",
    ]:
        series = df[col]
        print(f"  {col}: mean={series.mean():,.2f}  median={series.median():,.2f}")

    print("\nBusiness category counts:")
    print(df["business_category"].value_counts().to_string())

    print("\nGST registration rate:", f"{df['has_gst_registration'].mean():.1%}")
    print("=" * 70)


def main() -> None:
    df = generate_dataset()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df):,} rows to {OUTPUT_PATH}")
    print_validation_summary(df)


if __name__ == "__main__":
    main()
