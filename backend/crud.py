"""
Step 11 — Plain database access functions (no FastAPI-specific code here:
no Depends, no HTTPException, no request/response models -- just a Session
in, plain Python objects/values out). backend/main.py's endpoints call
these; that keeps the "how do I query the database" logic in one place,
separate from "how do I handle an HTTP request".
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db_models import Assessment, Company, FairnessAuditLog


def _to_native(value: Any) -> Any:
    """Recursively converts numpy scalar types into native Python
    float/int/bool, leaving everything else untouched. Walks into dicts
    and lists/tuples too (e.g. Assessment.shap_top_drivers is a dict
    containing a list of {"feature", "value", "shap_value"} dicts, and
    those "value"/"shap_value" numbers can be numpy floats just as easily
    as the top-level ones).

    WHY THIS EXISTS -- a real bug, not a hypothetical:
    model/scoring.py's score_company() and model/preprocessing.py's
    derived-ratio calculations (net_cash_margin, cash_buffer_ratio, etc.)
    return numpy.float64 values, not native Python floats -- pandas/numpy
    arithmetic on even a single row always produces numpy scalar types.
    numpy.float64 IS a subclass of Python's float, so SQLite's loose
    typing silently accepted it with no problem at all. psycopg2
    (PostgreSQL) does NOT recognize a numpy type as something it knows
    how to bind as a SQL parameter, and falls back to a repr()-based text
    substitution -- and as of numpy 2.0+, repr(np.float64(600000.0))
    returns the STRING "np.float64(600000.0)" (previously just
    "600000.0"). That string gets spliced into the SQL unquoted, and
    Postgres tries to parse "np" as a schema name and fails with
    `InvalidSchemaName: schema "np" does not exist`.
    """
    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_native(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


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

    Both dicts are run through `_to_native()` first (see its docstring):
    this is THE single boundary where numbers computed anywhere upstream
    (model/scoring.py, model/preprocessing.py, backend/main.py's
    `_build_feature_row()`, ...) cross into the database layer, so
    sanitizing numpy scalar types exactly HERE protects every current and
    future caller automatically -- instead of needing the same fix
    repeated (and possibly forgotten) in every function that happens to
    produce a number that eventually ends up in these two dicts.
    """
    company_data = _to_native(company_data)
    assessment_data = _to_native(assessment_data)

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


def get_all_assessments(db: Session) -> list[Assessment]:
    """Returns every Assessment row in the database -- the one shared
    query `get_portfolio_stats()` and Step 12d's `model.fairness.
    compute_dir_audit()` both build on, so the underlying SQL lives in
    exactly one place."""
    return list(db.execute(select(Assessment)).scalars().all())


def get_portfolio_stats(db: Session) -> dict[str, Any]:
    """Aggregates risk-band counts/percentages and the average credit
    score across EVERY assessment in the database (every re-assessment
    counts separately, since a company's risk band can change between
    assessments -- see PortfolioAnalyticsResponse's docstring)."""
    assessments = get_all_assessments(db)
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


def save_fairness_audit_batch(
    db: Session, audit_rows: list[dict[str, Any]]
) -> list[FairnessAuditLog]:
    """Inserts a batch of FairnessAuditLog rows -- ONE periodic snapshot,
    all sharing the same `computed_at` -- in a single commit. Each dict in
    `audit_rows` must contain every FairnessAuditLog field except `id`
    (auto-filled).

    Used by model.fairness.compute_dir_audit() once per audit run; never
    called per-assessment (see backend/db_models.py's FairnessAuditLog
    docstring for why)."""
    logs = [FairnessAuditLog(**row) for row in audit_rows]
    db.add_all(logs)
    db.commit()
    for log in logs:
        db.refresh(log)
    return logs


def get_latest_fairness_audit(db: Session) -> list[FairnessAuditLog]:
    """Returns every row from the MOST RECENT `computed_at` batch (the
    latest periodic fairness snapshot, across all cohort dimensions
    together) -- or an empty list if no audit has ever been run."""
    latest_computed_at = db.execute(
        select(func.max(FairnessAuditLog.computed_at))
    ).scalar_one_or_none()
    if latest_computed_at is None:
        return []

    return list(
        db.execute(
            select(FairnessAuditLog).where(FairnessAuditLog.computed_at == latest_computed_at)
        ).scalars().all()
    )
