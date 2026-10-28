"""Tests for the static market-rates reference table (model/market_rates.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.market_rates import MARKET_RATES, RATES_AS_OF, get_disclaimer, get_market_rates
from tests.test_api import UNREGISTERED_GST_PAYLOAD, VALID_PAYLOAD


def test_all_six_banks_present_with_required_fields():
    rates = get_market_rates()
    assert [r["name"] for r in rates] == [
        "HDFC Bank",
        "State Bank of India",
        "ICICI Bank",
        "Axis Bank",
        "Bajaj Finserv",
        "Kotak Mahindra Bank",
    ]
    for entry in rates:
        assert entry["rate_range"].strip()
        assert entry["url"].startswith("https://")
        assert entry["note"].strip()
        assert entry["rate_min"] > 0


def test_table_is_a_fresh_copy_each_call():
    first = get_market_rates()
    first[0]["name"] = "tampered"
    assert get_market_rates()[0]["name"] == "HDFC Bank"
    assert MARKET_RATES[0]["name"] == "HDFC Bank"


def test_disclaimer_contains_as_of_date_and_bureau_warning():
    text = get_disclaimer()
    assert f"{RATES_AS_OF.day} {RATES_AS_OF.strftime('%B %Y')}" in text
    assert "Not a personalized offer" in text
    assert "real credit bureau" in text


def test_api_returns_identical_table_regardless_of_score(client):
    """Two very different applicants must get exactly the same table."""
    first = client.post("/api/v1/evaluate", json=VALID_PAYLOAD).json()
    second = client.post("/api/v1/evaluate", json=UNREGISTERED_GST_PAYLOAD).json()
    expected = get_market_rates()
    assert first["market_rates"] == expected
    assert second["market_rates"] == expected
    assert first["rates_as_of"] == RATES_AS_OF.isoformat()
    assert first["market_rates_disclaimer"] == get_disclaimer()

    history = client.get(f"/api/v1/company/{first['company_id']}").json()
    assert history["assessments"][0]["market_rates"] == expected
    assert "lender_matches" not in first
