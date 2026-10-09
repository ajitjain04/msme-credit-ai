"""
Step 13 — Tests for backend/main.py's HTTP endpoints.

Every test here uses the `client` fixture from tests/conftest.py, which
wires FastAPI's TestClient to a THROWAWAY in-memory SQLite database (see
conftest.py's docstring) -- the real PostgreSQL database configured in
.env is never touched, so this whole file is safe to run repeatedly.

Pure verification only -- nothing here changes backend/main.py's logic.

How to run just this file:
    venv\\Scripts\\python.exe -m pytest tests/test_api.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

VALID_RISK_BANDS = {"Low Risk", "Medium Risk", "High Risk"}

# Mirrors backend/schemas.py's MSMEInput.model_config json_schema_extra
# "example" exactly -- one real, valid company, reused across tests
# instead of re-typing a new one in each test function.
VALID_PAYLOAD = {
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

# A second, deliberately different (but still GST-REGISTERED) company --
# older/younger age, more bounces, thinner cash buffer -- used only by the
# portfolio/fairness tests below, so they aren't evaluating 2 near
# -identical companies and risking every assessment landing in the same
# risk band by coincidence. Deliberately NOT has_gst_registration=False
# here: that path hits a separate, real bug (see
# test_evaluate_with_unregistered_gst_company below) that these two tests
# have nothing to do with -- mixing the two would make a portfolio-stats
# test fail for a reason unrelated to portfolio stats.
RISKIER_PAYLOAD = {
    **VALID_PAYLOAD,
    "company_name": "Risky Traders Co",
    "age_of_business_years": 1.0,
    # account_vintage_months can never exceed age_of_business_years * 12
    # (backend/schemas.py's validate_vintage_within_age()) -- VALID_PAYLOAD's
    # 48 months would violate that once age drops to 1.0 year, so this is
    # lowered to fit.
    "account_vintage_months": 10,
    "avg_monthly_outflow": 750000,
    "min_ending_balance_avg": 2000,
    "bounce_count_last_6m": 9,
    "cash_flow_volatility": 1.2,
    "gst_filing_regularity_score": 20.0,
    "gst_filing_delay_days_avg": 60.0,
}

# A GST-UNREGISTERED company (has_gst_registration=False, all 3 nullable
# GST fields explicitly null) -- a perfectly valid, realistic input per
# backend/schemas.py's own validation rules (docs/data_dictionary.md says
# ~15% of real companies have no GST registration). Used only by
# test_evaluate_with_unregistered_gst_company below.
UNREGISTERED_GST_PAYLOAD = {
    **VALID_PAYLOAD,
    "company_name": "Unregistered Traders",
    "has_gst_registration": False,
    "gst_filing_regularity_score": None,
    "annual_turnover_gst": None,
    "gst_filing_delay_days_avg": None,
}


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_evaluate_with_valid_data_returns_well_formed_response(client):
    response = client.post("/api/v1/evaluate", json=VALID_PAYLOAD)
    assert response.status_code == 200

    body = response.json()
    assert 300 <= body["credit_score"] <= 900
    assert 0.0 <= body["default_probability"] <= 1.0
    assert body["risk_band"] in VALID_RISK_BANDS
    assert len(body["top_positive_drivers"]) > 0
    assert len(body["top_negative_drivers"]) > 0


def test_evaluate_with_unregistered_gst_company(client):
    """A GST-unregistered company is perfectly valid input (passes
    backend/schemas.py's own validation -- see UNREGISTERED_GST_PAYLOAD's
    comment), so this SHOULD return 200 with a well-formed response, same
    as the GST-registered case above.

    KNOWN FAILING as of Step 13 (not fixed here -- tests only, per this
    step's scope): backend/main.py's _build_feature_row() puts Python
    `None` (not `np.nan`) into the 3 nullable GST feature columns for an
    unregistered company. The model/imputer pipeline tolerates that fine,
    but model/explainer.py's explain_company() separately does
    `float(row[feat])` on the RAW feature value when building each SHAP
    driver's display "value" -- and float(None) raises TypeError. If any
    of the 3 GST features lands in that company's top SHAP drivers (very
    plausible -- GST discipline is one of the label's main risk signals
    per docs/data_dictionary.md), POST /api/v1/evaluate crashes with a
    500 for every real unregistered company (~15% of the synthetic
    population). Fix belongs in backend/main.py's _build_feature_row()
    (use np.nan instead of None for these 3 fields) -- flagged, not
    fixed, in this tests-only step.
    """
    response = client.post("/api/v1/evaluate", json=UNREGISTERED_GST_PAYLOAD)
    assert response.status_code == 200

    body = response.json()
    assert 300 <= body["credit_score"] <= 900
    assert body["risk_band"] in VALID_RISK_BANDS


def test_evaluate_with_invalid_data_returns_422(client):
    invalid_payload = {
        **VALID_PAYLOAD,
        "age_of_business_years": -5.0,  # must be > 0
        "bounce_count_last_6m": -1,  # must be >= 0
    }
    response = client.post("/api/v1/evaluate", json=invalid_payload)
    assert response.status_code == 422


def test_get_company_after_evaluate_returns_matching_data(client):
    evaluate_response = client.post("/api/v1/evaluate", json=VALID_PAYLOAD)
    assert evaluate_response.status_code == 200
    evaluated = evaluate_response.json()
    company_id = evaluated["company_id"]

    history_response = client.get(f"/api/v1/company/{company_id}")
    assert history_response.status_code == 200

    history = history_response.json()
    assert history["company_id"] == company_id
    assert history["company_name"] == VALID_PAYLOAD["company_name"]
    assert history["business_category"] == VALID_PAYLOAD["business_category"]
    assert history["state"] == VALID_PAYLOAD["state"]
    assert history["employee_count"] == VALID_PAYLOAD["employee_count"]

    assert len(history["assessments"]) == 1
    assert history["assessments"][0]["credit_score"] == evaluated["credit_score"]
    assert history["assessments"][0]["risk_band"] == evaluated["risk_band"]


def test_get_company_not_found_returns_404(client):
    response = client.get("/api/v1/company/MSME-DOES-NOT-EXIST")
    assert response.status_code == 404


def test_portfolio_analytics_percentages_sum_to_100(client):
    # Evaluate 2 deliberately different companies first -- with zero
    # assessments, the percentages would trivially be 0/0/0, not ~100.
    client.post("/api/v1/evaluate", json=VALID_PAYLOAD)
    client.post("/api/v1/evaluate", json=RISKIER_PAYLOAD)

    response = client.get("/api/v1/analytics/portfolio")
    assert response.status_code == 200

    body = response.json()
    assert body["total_assessments"] == 2
    total_pct = body["low_risk_pct"] + body["medium_risk_pct"] + body["high_risk_pct"]
    assert total_pct == pytest.approx(100.0, abs=0.01)


def test_fairness_audit_returns_well_formed_response(client):
    # Don't assert specific DIR values -- that depends on data volume
    # (see model/fairness.py). Just check the response shape is correct.
    client.post("/api/v1/evaluate", json=VALID_PAYLOAD)
    client.post("/api/v1/evaluate", json=RISKIER_PAYLOAD)

    response = client.get("/api/v1/analytics/fairness")
    assert response.status_code == 200

    body = response.json()
    assert "computed_at" in body
    assert "min_cohort_size" in body
    assert isinstance(body["audits"], list)
    assert isinstance(body["excluded_small_cohorts"], list)

    for audit in body["audits"]:
        assert "cohort_dimension" in audit
        assert "cohort_value" in audit
        assert "flagged_low_dir" in audit

    for excluded in body["excluded_small_cohorts"]:
        assert "cohort_dimension" in excluded
        assert "cohort_value" in excluded
        assert "cohort_size" in excluded
