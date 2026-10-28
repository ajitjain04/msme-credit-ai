"""
Tests for model/explanation_text.py (rule-based plain-English SHAP text) and
for the new `explanation` / `overall_summary` fields in the API responses.

How to run just this file:
    venv\\Scripts\\python.exe -m pytest tests/test_explanation_text.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.config import FEATURE_COLUMNS
from model.explanation_text import (
    FEATURE_EXPLANATIONS,
    PLAIN_TOPICS,
    generate_driver_explanation,
    generate_overall_summary,
    generate_plain_summary,
)
from tests.test_api import UNREGISTERED_GST_PAYLOAD, VALID_PAYLOAD


def test_every_feature_has_a_description():
    assert set(FEATURE_EXPLANATIONS) == set(FEATURE_COLUMNS)


def test_positive_shap_says_increased():
    text = generate_driver_explanation("bounce_count_last_6m", 0.8, "7.00")
    assert "increased" in text
    assert "strongly" in text
    assert "7.00" in text


def test_negative_shap_says_reduced():
    text = generate_driver_explanation("account_vintage_months", -0.3, "48.00")
    assert "reduced" in text
    assert "moderately" in text


def test_slight_magnitude():
    assert "slightly" in generate_driver_explanation("employee_count", 0.05, "8.00")


def test_none_value_for_gst_unregistered_company():
    text = generate_driver_explanation("gst_filing_regularity_score", 0.9, None)
    assert "not GST-registered" in text
    assert "None" not in text


def test_not_available_display_string_is_treated_as_missing():
    text = generate_driver_explanation(
        "gst_to_bank_turnover_ratio", -0.1, "Not available (GST not registered)"
    )
    assert "not GST-registered" in text
    assert "(Not available" not in text


def test_overall_summary_mentions_band_score_and_both_sides():
    drivers = [
        {"feature": "gst_filing_delay_days_avg", "shap_value": 0.9},
        {"feature": "cash_flow_volatility", "shap_value": -0.5},
    ]
    text = generate_overall_summary("Medium Risk", 721, 0.31, drivers)
    assert "Medium Risk" in text
    assert "721" in text
    assert "main concerns" in text
    assert "support the score" in text


def test_overall_summary_for_each_band_and_missing_side():
    only_positive = [{"feature": "bounce_count_last_6m", "shap_value": 1.2}]
    only_negative = [{"feature": "cash_flow_volatility", "shap_value": -0.4}]
    assert "High Risk" in generate_overall_summary("High Risk", 540, 0.67, only_positive)
    assert "Low Risk" in generate_overall_summary("Low Risk", 812, 0.08, only_negative)
    # No drivers at all must still return a non-empty sentence.
    assert generate_overall_summary("Low Risk", 800, 0.1, []).startswith("This business")


def _check_response_text(body: dict) -> None:
    assert isinstance(body["overall_summary"], str) and body["overall_summary"].strip()
    for driver in body["top_positive_drivers"] + body["top_negative_drivers"]:
        assert isinstance(driver["explanation"], str) and driver["explanation"].strip()


def test_evaluate_response_includes_explanations(client):
    response = client.post("/api/v1/evaluate", json=VALID_PAYLOAD)
    assert response.status_code == 200
    _check_response_text(response.json())


def test_evaluate_gst_unregistered_includes_explanations(client):
    response = client.post("/api/v1/evaluate", json=UNREGISTERED_GST_PAYLOAD)
    assert response.status_code == 200
    _check_response_text(response.json())


def test_company_history_includes_explanations(client):
    company_id = client.post("/api/v1/evaluate", json=VALID_PAYLOAD).json()["company_id"]
    history = client.get(f"/api/v1/company/{company_id}").json()
    _check_response_text(history["assessments"][0])


# --- Plain-English layer -----------------------------------------------------

def test_plain_summary_has_no_feature_names_or_numbers():
    drivers = [
        {"feature": "account_vintage_months", "shap_value": -0.4},
        {"feature": "gst_filing_regularity_score", "shap_value": -0.2},
        {"feature": "cash_flow_volatility", "shap_value": 0.6},
    ]
    text = generate_plain_summary("Medium Risk", drivers)
    assert "helped most by" in text and "held back most by" in text
    assert "_" not in text and "SHAP" not in text
    assert not any(ch.isdigit() for ch in text)  # no score / SHAP / % figures


def test_plain_summary_only_claims_what_the_signs_support():
    only_helping = generate_plain_summary("Low Risk", [{"feature": "bounce_count_last_6m", "shap_value": -0.3}])
    assert "held back" not in only_helping
    none = generate_plain_summary("High Risk", [])
    assert "helped" not in none and "held back" not in none and none.strip()


def test_every_feature_has_a_plain_topic():
    assert set(PLAIN_TOPICS) == set(FEATURE_COLUMNS)


def test_api_returns_plain_summary(client):
    body = client.post("/api/v1/evaluate", json=VALID_PAYLOAD).json()
    assert body["plain_summary"].strip() and "_" not in body["plain_summary"]
    company_id = body["company_id"]
    history = client.get(f"/api/v1/company/{company_id}").json()
    assert history["assessments"][0]["plain_summary"].strip()
