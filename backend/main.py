"""
Step 11 — FastAPI backend.

Exposes the tuned model (Step 7), the 300-900 credit score + risk band
conversion (Step 8) and SHAP explanations (Step 9) as a real HTTP API, and
persists every scoring event to the Step 10 database.

This file does NOT reimplement any model logic: score_company() and
explain_company() are imported and called exactly as Steps 8-9 wrote them.

How to run:
    venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload
Then open http://127.0.0.1:8000/docs for the interactive API docs.
"""

from __future__ import annotations

import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import crud  # noqa: E402
from backend.database import Base, engine, get_db  # noqa: E402
from backend.schemas import (  # noqa: E402
    CATEGORY_ENCODINGS,
    CompanyHistoryResponse,
    EvaluateResponse,
    FairnessAuditResponse,
    MSMEInput,
    PortfolioAnalyticsResponse,
)
from model.config import FEATURE_COLUMNS  # noqa: E402
from model.explainer import explain_company  # noqa: E402
from model.fairness import MIN_COHORT_SIZE, compute_dir_audit  # noqa: E402
from model.preprocessing import add_derived_ratios  # noqa: E402
from model.scoring import score_company  # noqa: E402

# Importing model.scoring and model.explainer above already loaded the
# tuned model (and built the SHAP explainer) exactly ONCE, at IMPORT time
# -- see their own module-level `_MODEL = joblib.load(...)` lines. Because
# Python only imports a module once per process, that happens before
# uvicorn ever starts accepting requests, and every request below reuses
# those same already-loaded objects instead of reloading anything.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup/shutdown hook. The heavy one-time work (loading the
    model, building the SHAP explainer) already happened above at import
    time -- this is where we do the OTHER one-time startup work: making
    sure the database tables exist, so the API works even if
    scripts/init_db.py was never run."""
    print("Startup: model + SHAP explainer already loaded (see imports above).")
    Base.metadata.create_all(bind=engine)
    print("Startup: database tables ready.")
    yield
    print("Shutdown.")


app = FastAPI(
    title="MSME Alternative Credit Assessment API",
    description=(
        "Scores MSMEs with thin credit files using alternative data "
        "(bank transactions, GST filings, UPI/digital payments), and "
        "explains each score with SHAP."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Any localhost origin, any port -- Step 12's Streamlit dashboard runs on a
# different port than this API, and may run on http or https during local
# development.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_feature_row(payload: MSMEInput) -> pd.Series:
    """Converts one validated MSMEInput into the exact FEATURE_COLUMNS
    -shaped row score_company() / explain_company() expect:
      1. encodes business_category / state using the SAME saved mapping
         model/preprocessing.py used (model/artifacts/category_encodings.json,
         loaded once in backend/schemas.py as CATEGORY_ENCODINGS);
      2. computes the 3 derived ratios by calling
         model.preprocessing.add_derived_ratios() -- reusing that exact
         formula instead of retyping it a third time.
    See backend/schemas.py's module docstring for why these aren't asked
    for directly in the request body.
    """
    raw = {
        "age_of_business_years": payload.age_of_business_years,
        "employee_count": payload.employee_count,
        "avg_monthly_inflow": payload.avg_monthly_inflow,
        "avg_monthly_outflow": payload.avg_monthly_outflow,
        "min_ending_balance_avg": payload.min_ending_balance_avg,
        "bounce_count_last_6m": payload.bounce_count_last_6m,
        "account_vintage_months": payload.account_vintage_months,
        "cash_flow_volatility": payload.cash_flow_volatility,
        "has_gst_registration": int(payload.has_gst_registration),
        "gst_filing_regularity_score": payload.gst_filing_regularity_score,
        "annual_turnover_gst": payload.annual_turnover_gst,
        "gst_filing_delay_days_avg": payload.gst_filing_delay_days_avg,
        "upi_transaction_volume_ratio": payload.upi_transaction_volume_ratio,
        "pos_terminal_active_status": int(payload.pos_terminal_active_status),
        "digital_payment_adoption_score": payload.digital_payment_adoption_score,
    }

    df = pd.DataFrame([raw])
    df = add_derived_ratios(df)
    df["business_category_encoded"] = CATEGORY_ENCODINGS["business_category"][payload.business_category]
    df["state_encoded"] = CATEGORY_ENCODINGS["state"][payload.state]

    return df.iloc[0][FEATURE_COLUMNS]


# banking/GST/digital snapshot fields that live on Assessment -- i.e.
# FEATURE_COLUMNS minus the 4 firmographic columns that live on Company
# instead (see backend/db_models.py and scripts/init_db.py, which uses the
# same split).
_FIRMOGRAPHIC_COLUMNS = {
    "age_of_business_years",
    "business_category_encoded",
    "state_encoded",
    "employee_count",
}
_ASSESSMENT_FEATURE_COLUMNS = [c for c in FEATURE_COLUMNS if c not in _FIRMOGRAPHIC_COLUMNS]


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check -- confirm the server is up before testing
    the real endpoints below."""
    return {"status": "ok"}


@app.post("/api/v1/evaluate", response_model=EvaluateResponse)
def evaluate_company(payload: MSMEInput, db: Session = Depends(get_db)) -> EvaluateResponse:
    """Scores one company end-to-end: runs the tuned model
    (model.scoring.score_company()), explains the result
    (model.explainer.explain_company()), saves both the company's profile
    and this assessment to the database, and returns the result.

    Provide `company_id` in the request body to re-assess an EXISTING
    company (adds a new entry to its history); omit it to create a new
    company (a fresh ID is generated)."""
    company_id = payload.company_id or f"MSME-API-{uuid.uuid4().hex[:8]}"

    feature_row = _build_feature_row(payload)
    score_result = score_company(feature_row)
    explanation = explain_company(feature_row)

    company_data = {
        "company_id": company_id,
        "company_name": payload.company_name,
        "age_of_business_years": payload.age_of_business_years,
        "business_category": payload.business_category,
        "state": payload.state,
        "employee_count": payload.employee_count,
    }
    assessment_data = {
        **{col: feature_row[col] for col in _ASSESSMENT_FEATURE_COLUMNS},
        "default_probability": score_result["default_probability"],
        "credit_score": score_result["credit_score"],
        "risk_band": score_result["risk_band"],
        "shap_top_drivers": {
            "top_positive_contributors": explanation["top_positive_contributors"],
            "top_negative_contributors": explanation["top_negative_contributors"],
        },
    }

    _, assessment = crud.create_company_and_assessment(db, company_data, assessment_data)

    return EvaluateResponse(
        company_id=company_id,
        default_probability=score_result["default_probability"],
        credit_score=score_result["credit_score"],
        risk_band=score_result["risk_band"],
        top_positive_drivers=explanation["top_positive_contributors"],
        top_negative_drivers=explanation["top_negative_contributors"],
        assessed_at=assessment.assessed_at,
    )


@app.get("/api/v1/company/{company_id}", response_model=CompanyHistoryResponse)
def get_company(company_id: str, db: Session = Depends(get_db)) -> CompanyHistoryResponse:
    """Returns a company's static profile plus every assessment ever run
    on it, newest first. 404s (not an empty 200) if the company_id doesn't
    exist."""
    company = crud.get_company_with_history(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found.")

    return CompanyHistoryResponse(
        company_id=company.company_id,
        company_name=company.company_name,
        age_of_business_years=company.age_of_business_years,
        business_category=company.business_category,
        state=company.state,
        employee_count=company.employee_count,
        created_at=company.created_at,
        assessments=[
            {
                "assessment_id": a.assessment_id,
                "assessed_at": a.assessed_at,
                "default_probability": a.default_probability,
                "credit_score": a.credit_score,
                "risk_band": a.risk_band,
                "top_positive_drivers": a.shap_top_drivers.get("top_positive_contributors", []),
                "top_negative_drivers": a.shap_top_drivers.get("top_negative_contributors", []),
            }
            for a in company.assessments
        ],
    )


@app.get("/api/v1/analytics/portfolio", response_model=PortfolioAnalyticsResponse)
def get_portfolio_analytics(db: Session = Depends(get_db)) -> PortfolioAnalyticsResponse:
    """Aggregates risk-band counts/percentages and the average credit
    score across every assessment in the database."""
    stats = crud.get_portfolio_stats(db)
    return PortfolioAnalyticsResponse(**stats)


@app.get("/api/v1/analytics/fairness", response_model=FairnessAuditResponse)
def get_fairness_audit(db: Session = Depends(get_db)) -> FairnessAuditResponse:
    """Step 12d — runs a FRESH Disparate Impact Ratio (DIR) audit on
    demand (not cached): every call re-scores `state` and
    `business_category` cohorts against the database's CURRENT
    assessments and saves a new periodic snapshot
    (backend.db_models.FairnessAuditLog). Cohorts with fewer than
    model.fairness.MIN_COHORT_SIZE assessments are excluded as
    statistically unreliable (listed separately, not scored).

    IMPORTANT: `state`/`business_category` are risk-relevant
    behaviours/circumstances, not protected characteristics -- see
    model/fairness.py's module docstring for the full methodology and
    why a flagged cohort here is a prompt to look at its actual default
    rate, not proof of discrimination on its own.
    """
    result = compute_dir_audit(db)
    audit_logs = result["audit_logs"]

    return FairnessAuditResponse(
        computed_at=audit_logs[0].computed_at if audit_logs else datetime.utcnow(),
        min_cohort_size=MIN_COHORT_SIZE,
        audits=audit_logs,
        excluded_small_cohorts=result["excluded_cohorts"],
    )
