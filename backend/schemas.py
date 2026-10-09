"""
Step 11 — Pydantic request/response models for the FastAPI backend.

These are pure data shapes + validation rules -- no database or model code
lives here (that's backend/crud.py and model/scoring.py / model/explainer.py
respectively).

WHAT MSMEInput DELIBERATELY LEAVES OUT (and why)
----------------------------------------------------------------------------
model.config.FEATURE_COLUMNS has 20 entries, but MSMEInput does not ask the
API caller for all 20 directly:

- `business_category_encoded` / `state_encoded` are replaced here by plain
  human-readable `business_category` / `state` strings (e.g. "retail",
  "Maharashtra"). The caller shouldn't need to know these get turned into
  internal integer codes at all -- backend/main.py encodes them using the
  exact mapping model/preprocessing.py saved to
  model/artifacts/category_encodings.json.
- `net_cash_margin`, `cash_buffer_ratio` and `gst_to_bank_turnover_ratio`
  are likewise left out. These are DERIVED ratios -- model/preprocessing.py
  computes them FROM the raw inflow/outflow/balance/turnover numbers, they
  are never independently observed. Asking the caller to supply both the
  raw numbers AND their own pre-computed ratio would let a buggy or
  malicious caller submit a ratio that doesn't match their own raw numbers.
  backend/main.py computes these the same way the training data was built
  -- by calling model.preprocessing.add_derived_ratios() on the raw fields
  below, not by retyping that formula a third time.

So MSMEInput mirrors the shape of the RAW synthetic dataset (before
model/preprocessing.py's encoding + derived-ratio steps), which is exactly
the kind of data a lender would actually have on hand for a new company.

VALIDATION BOUNDS: strict vs. loose, and why
----------------------------------------------------------------------------
Fields that are mathematically/logically bounded no matter what business
is being described (a ratio must be within 0-1, a percentage within
0-100, a count can't be negative) get a strict bound here. Fields that are
just "the range our SPECIFIC synthetic sample happened to cover" (e.g.
docs/data_dictionary.md's ₹50,000-₹1.5cr monthly inflow, or bounce counts
capped at 15) are left as loose non-negativity checks instead -- a real
company that happens to fall outside our synthetic sample's typical range
should still be scorable, not rejected by the API for being unusual.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATEGORY_ENCODINGS_PATH = PROJECT_ROOT / "model" / "artifacts" / "category_encodings.json"

with open(CATEGORY_ENCODINGS_PATH) as _f:
    # The exact {category_name: code} mapping model/preprocessing.py used
    # to build data/processed/train.csv / test.csv. Loaded once at import
    # time and reused for validation here AND for encoding in
    # backend/main.py, so there is exactly one copy of "what counts as a
    # valid business_category/state" in the whole backend.
    CATEGORY_ENCODINGS: dict[str, dict[str, int]] = json.load(_f)

VALID_BUSINESS_CATEGORIES = sorted(CATEGORY_ENCODINGS["business_category"].keys())
VALID_STATES = sorted(CATEGORY_ENCODINGS["state"].keys())


class ShapDriver(BaseModel):
    """One feature's contribution to a single prediction (Step 9's
    explain_company() output, one entry of top_positive/top_negative
    contributors)."""

    feature: str
    value: Optional[float] = Field(
        default=None,
        description=(
            "This feature's raw value for this company. None if it was genuinely "
            "missing -- in practice only the 3 GST columns (and the derived "
            "gst_to_bank_turnover_ratio) for a GST-unregistered company (see "
            "model.explainer._safe_feature_value()). Always prefer `display_value` "
            "below for showing this to a user -- it already handles None."
        ),
    )
    shap_value: float
    display_value: str = Field(
        ...,
        description=(
            "Human-readable version of `value`, ready to show directly to a user. "
            "For business_category_encoded/state_encoded this is the decoded category/state "
            "name (e.g. 'retail', not '2.00'); for a missing GST value this is "
            "'Not available (GST not registered)', never a crash or a literal 'None'; "
            "every other feature is just `value` formatted to 2 decimal places. Computed "
            "by backend/main.py via model.report_generator.format_driver_value() -- the "
            "exact same decoding logic the PDF report uses -- so the API, the React "
            "dashboard, the PDF, and the Streamlit dashboard all show identical text "
            "instead of each one re-implementing the same logic separately."
        ),
    )


class MSMEInput(BaseModel):
    """Request body for POST /api/v1/evaluate: one company's raw
    bank/GST/digital/firmographic data, in the human-readable shape a
    lender would actually have -- see the module docstring for what's
    deliberately excluded and why."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_name": "Shree Balaji Traders",
                "age_of_business_years": 6.5,
                "business_category": "retail",
                "state": "Maharashtra",
                "employee_count": 8,
                "avg_monthly_inflow": 600000,
                "avg_monthly_outflow": 540000,
                "min_ending_balance_avg": 60000,
                "bounce_count_last_6m": 0,
                "account_vintage_months": 48,
                "cash_flow_volatility": 0.25,
                "has_gst_registration": True,
                "gst_filing_regularity_score": 85.0,
                "annual_turnover_gst": 6500000,
                "gst_filing_delay_days_avg": 4.0,
                "upi_transaction_volume_ratio": 0.6,
                "pos_terminal_active_status": True,
                "digital_payment_adoption_score": 55.0,
            }
        }
    )

    # Omit to create a new company (the API generates an ID); provide an
    # existing one to re-assess that company instead (see
    # backend/db_models.py's one-to-many Company -> Assessment design).
    company_id: Optional[str] = Field(
        default=None, description="Existing company_id to re-assess, or omit to create a new company."
    )
    company_name: str = Field(..., min_length=1)

    # --- Firmographics (docs/data_dictionary.md section 1) ---
    age_of_business_years: float = Field(..., gt=0)
    business_category: str
    state: str
    employee_count: int = Field(..., ge=1)

    # --- Banking (docs/data_dictionary.md section 2) ---
    avg_monthly_inflow: float = Field(..., gt=0)
    avg_monthly_outflow: float = Field(..., ge=0)
    min_ending_balance_avg: float = Field(..., ge=0)
    bounce_count_last_6m: int = Field(..., ge=0)
    account_vintage_months: int = Field(..., ge=0)
    cash_flow_volatility: float = Field(..., ge=0)

    # --- Tax & compliance (docs/data_dictionary.md section 3) ---
    # The 3 GST fields are nullable: leave them unset (null) for a company
    # with has_gst_registration=False, matching the training data's
    # intentional-missingness convention exactly (NaN, not 0 -- see
    # docs/data_dictionary.md section 3). Enforced below.
    has_gst_registration: bool
    gst_filing_regularity_score: Optional[float] = Field(default=None, ge=0, le=100)
    annual_turnover_gst: Optional[float] = Field(default=None, ge=0)
    gst_filing_delay_days_avg: Optional[float] = Field(default=None, ge=0)

    # --- Digital footprint (docs/data_dictionary.md section 4) ---
    upi_transaction_volume_ratio: float = Field(..., ge=0, le=1)
    pos_terminal_active_status: bool
    digital_payment_adoption_score: float = Field(..., ge=0, le=100)

    @field_validator("business_category")
    @classmethod
    def validate_business_category(cls, value: str) -> str:
        if value not in CATEGORY_ENCODINGS["business_category"]:
            raise ValueError(f"business_category must be one of {VALID_BUSINESS_CATEGORIES}, got {value!r}")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        if value not in CATEGORY_ENCODINGS["state"]:
            raise ValueError(f"state must be one of {VALID_STATES}, got {value!r}")
        return value

    @model_validator(mode="after")
    def validate_gst_fields_match_registration(self) -> "MSMEInput":
        gst_fields = (
            self.gst_filing_regularity_score,
            self.annual_turnover_gst,
            self.gst_filing_delay_days_avg,
        )
        if self.has_gst_registration and any(f is None for f in gst_fields):
            raise ValueError(
                "has_gst_registration=True requires gst_filing_regularity_score, "
                "annual_turnover_gst and gst_filing_delay_days_avg to all be provided."
            )
        if not self.has_gst_registration and any(f is not None for f in gst_fields):
            raise ValueError(
                "has_gst_registration=False means this company has no GST returns -- "
                "leave gst_filing_regularity_score, annual_turnover_gst and "
                "gst_filing_delay_days_avg unset (null), matching how the training "
                "data represents unregistered firms (see docs/data_dictionary.md)."
            )
        return self

    @model_validator(mode="after")
    def validate_vintage_within_age(self) -> "MSMEInput":
        # Same relationship rule docs/data_dictionary.md and the Step 4 EDA
        # notebook check: an account can't be older than the business
        # itself.
        if self.account_vintage_months > self.age_of_business_years * 12:
            raise ValueError(
                "account_vintage_months cannot exceed age_of_business_years * 12 "
                f"({self.account_vintage_months} > "
                f"{self.age_of_business_years * 12:.1f})."
            )
        return self


class EvaluateResponse(BaseModel):
    """Response for POST /api/v1/evaluate: the result of one scoring
    event."""

    model_config = ConfigDict(from_attributes=True)

    company_id: str
    default_probability: float
    credit_score: int
    risk_band: str
    top_positive_drivers: list[ShapDriver]
    top_negative_drivers: list[ShapDriver]
    assessed_at: datetime


class AssessmentRecord(BaseModel):
    """One past assessment, as returned inside CompanyHistoryResponse."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: int
    assessed_at: datetime
    default_probability: float
    credit_score: int
    risk_band: str
    top_positive_drivers: list[ShapDriver]
    top_negative_drivers: list[ShapDriver]


class CompanyHistoryResponse(BaseModel):
    """Response for GET /api/v1/company/{company_id}: a company's static
    profile plus every assessment ever run on it, newest first."""

    model_config = ConfigDict(from_attributes=True)

    company_id: str
    company_name: str
    age_of_business_years: float
    business_category: str
    state: str
    employee_count: int
    created_at: datetime
    assessments: list[AssessmentRecord]


class FairnessCohortAudit(BaseModel):
    """One cohort's Disparate Impact Ratio (DIR) result, as computed by
    model.fairness.compute_dir_audit(). See
    GET /api/v1/analytics/fairness's module docstring (backend/main.py)
    and model/fairness.py for the full methodology and its important
    interpretation caveat."""

    model_config = ConfigDict(from_attributes=True)

    cohort_dimension: str
    cohort_value: str
    reference_dimension_value: str
    dir_value: Optional[float] = Field(
        default=None,
        description="DIR = this cohort's approval rate / the reference cohort's approval rate. "
        "null only if the reference cohort's approval rate is exactly 0.",
    )
    group_actual_default_rate: Optional[float] = Field(
        default=None,
        description="This cohort's ACTUAL observed default rate, from ground-truth labels only. "
        "null if no assessment in this cohort has a known outcome (e.g. all created via the live API). "
        "A low dir_value must be read alongside this number, never alone.",
    )
    cohort_size: int = Field(..., description="Total assessments in this cohort (used for dir_value).")
    cohort_size_with_known_outcome: int = Field(
        ..., description="Subset of cohort_size with a KNOWN ground-truth outcome (used only for group_actual_default_rate)."
    )
    flagged_low_dir: bool = Field(..., description="True if dir_value < 0.80 (the four-fifths rule).")


class ExcludedCohort(BaseModel):
    """A cohort too small to audit reliably, excluded from the fairness
    audit entirely (not scored, not saved)."""

    cohort_dimension: str
    cohort_value: str
    cohort_size: int


class FairnessAuditResponse(BaseModel):
    """Response for GET /api/v1/analytics/fairness: a fresh, on-demand
    Disparate Impact Ratio audit across the `state` and
    `business_category` cohorts. NOT cached -- each call re-runs the
    audit against the database's current assessments and saves a new
    periodic snapshot (backend.db_models.FairnessAuditLog)."""

    computed_at: datetime
    min_cohort_size: int = Field(
        ..., description="Cohorts with fewer than this many assessments were excluded as statistically unreliable."
    )
    audits: list[FairnessCohortAudit]
    excluded_small_cohorts: list[ExcludedCohort] = Field(default_factory=list)


class PortfolioAnalyticsResponse(BaseModel):
    """Response for GET /api/v1/analytics/portfolio: aggregate stats across
    every assessment in the database (not just distinct companies -- a
    company re-assessed twice contributes 2 assessments here, since risk
    band / score can change between assessments)."""

    total_companies: int = Field(..., description="Number of distinct companies with at least one assessment.")
    total_assessments: int = Field(..., description="Total number of assessment events across all companies.")

    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int
    low_risk_pct: float
    medium_risk_pct: float
    high_risk_pct: float

    average_credit_score: float
