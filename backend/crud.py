"""
Step 11 — Plain database access functions (no FastAPI-specific code here:
no Depends, no HTTPException, no request/response models -- just a Session
in, plain Python objects/values out). backend/main.py's endpoints call
these; that keeps the "how do I query the database" logic in one place,
separate from "how do I handle an HTTP request".
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db_models import Assessment, Company


def create_company_and_assessment(
    db: Session, company_data: dict[str, Any], assessment_data: dict[str, Any]
) -> tuple[Company, Assessment]:
    """Inserts a new Company (only if `company_data["company_id"]` doesn't
    already exist -- otherwise reuses the existing one) and ALWAYS inserts
    a new Assessment row, linked to that company.

    This is what makes re-assessing an existing company work correctly:
    calling this twice with the same company_id gives you one Company row
    and two Assessment rows (its history), never two Company rows and
    never an overwritten Assessment.

    `company_data` must contain every backend.db_models.Company field
    except `created_at` (auto-filled). `assessment_data` must contain
    every backend.db_models.Assessment field except `assessment_id`,
    `company_id` and `assessed_at` (auto-filled / filled in here).
    """
    company = db.get(Company, company_data["company_id"])
    if company is None:
        company = Company(**company_data)
        db.add(company)

    assessment = Assessment(company_id=company_data["company_id"], **assessment_data)
    db.add(assessment)

    db.commit()
    db.refresh(company)
    db.refresh(assessment)
    return company, assessment


def get_company_with_history(db: Session, company_id: str) -> Optional[Company]:
    """Returns the Company (with its `.assessments` list sorted newest
    -first) for `company_id`, or None if no such company exists."""
    company = db.get(Company, company_id)
    if company is None:
        return None

    # Sort newest-first here rather than changing backend/db_models.py's
    # relationship() ordering -- this only reorders the in-memory list on
    # the object we're about to return, it changes nothing in the database.
    company.assessments.sort(key=lambda a: a.assessed_at, reverse=True)
    return company


def get_portfolio_stats(db: Session) -> dict[str, Any]:
    """Aggregates risk-band counts/percentages and the average credit
    score across EVERY assessment in the database (every re-assessment
    counts separately, since a company's risk band can change between
    assessments -- see PortfolioAnalyticsResponse's docstring)."""
    assessments = db.execute(select(Assessment)).scalars().all()
    total_assessments = len(assessments)

    if total_assessments == 0:
        return {
            "total_companies": 0,
            "total_assessments": 0,
            "low_risk_count": 0,
            "medium_risk_count": 0,
            "high_risk_count": 0,
            "low_risk_pct": 0.0,
            "medium_risk_pct": 0.0,
            "high_risk_pct": 0.0,
            "average_credit_score": 0.0,
        }

    total_companies = len({a.company_id for a in assessments})

    band_counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for assessment in assessments:
        band_counts[assessment.risk_band] += 1

    average_credit_score = sum(a.credit_score for a in assessments) / total_assessments

    return {
        "total_companies": total_companies,
        "total_assessments": total_assessments,
        "low_risk_count": band_counts["Low Risk"],
        "medium_risk_count": band_counts["Medium Risk"],
        "high_risk_count": band_counts["High Risk"],
        "low_risk_pct": band_counts["Low Risk"] / total_assessments * 100,
        "medium_risk_pct": band_counts["Medium Risk"] / total_assessments * 100,
        "high_risk_pct": band_counts["High Risk"] / total_assessments * 100,
        "average_credit_score": average_credit_score,
    }
