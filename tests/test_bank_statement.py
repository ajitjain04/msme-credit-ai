"""
Tests for model/bank_statement_parser.py and POST /api/v1/parse-bank-statement.

How to run just this file:
    venv\Scripts\python.exe -m pytest tests/test_bank_statement.py -v
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from model.bank_statement_parser import BankStatementError, parse_bank_statement_csv

SAMPLE_PATH = PROJECT_ROOT / "data" / "sample_bank_statement.csv"

# 3 months, no bounce-type rows. Hand-checked:
#   inflow  Jan 100000, Feb 50000, Mar 150000   -> mean 100000
#   outflow Jan 40000,  Feb 60000, Mar 20000    -> mean 40000
#   min bal Jan 60000,  Feb 50000, Mar 70000    -> mean 60000
#   vintage Jan 5 -> Mar 25 = 2 whole months
CLEAN_CSV = """date,description,debit,credit,balance
2026-01-05,Customer payment,,100000,100000
2026-01-20,Supplier,40000,,60000
2026-02-10,Customer payment,,50000,110000
2026-02-18,Supplier,60000,,50000
2026-03-05,Customer payment,,150000,200000
2026-03-25,Supplier,20000,,70000
"""


def _as_file(text: str) -> BytesIO:
    return BytesIO(text.encode("utf-8"))


def test_valid_csv_parses_to_expected_values():
    result = parse_bank_statement_csv(_as_file(CLEAN_CSV))
    assert result == {
        "avg_monthly_inflow": 100000.0,
        "avg_monthly_outflow": 40000.0,
        "min_ending_balance_avg": 60000.0,
        "bounce_count_last_6m": 0,
        "account_vintage_months": 2,
    }


def test_no_bounce_rows_returns_zero_not_crash():
    assert parse_bank_statement_csv(_as_file(CLEAN_CSV))["bounce_count_last_6m"] == 0


def test_sample_file_finds_two_bounces():
    result = parse_bank_statement_csv(SAMPLE_PATH)
    assert result["bounce_count_last_6m"] == 2
    assert result["account_vintage_months"] == 5
    assert result["avg_monthly_inflow"] == pytest.approx(380000.0)
    assert result["avg_monthly_outflow"] == pytest.approx(366033.33, abs=0.01)
    assert result["min_ending_balance_avg"] == pytest.approx(176403.33, abs=0.01)


def test_bounce_keywords_are_case_insensitive():
    text = CLEAN_CSV + "2026-03-26,CHEQUE RETURNED - Insufficient Funds,500,,69500\n"
    assert parse_bank_statement_csv(_as_file(text))["bounce_count_last_6m"] == 1


def test_missing_column_raises_clear_error():
    bad = "date,description,debit,credit\n2026-01-05,x,,100\n"
    with pytest.raises(BankStatementError) as excinfo:
        parse_bank_statement_csv(_as_file(bad))
    assert "balance" in str(excinfo.value)
    assert "date,description,debit,credit,balance" in str(excinfo.value)


def test_bad_date_and_empty_file_raise_clear_errors():
    bad_date = "date,description,debit,credit,balance\n05/01/2026,x,,100,100\n"
    with pytest.raises(BankStatementError, match="YYYY-MM-DD"):
        parse_bank_statement_csv(_as_file(bad_date))
    with pytest.raises(BankStatementError):
        parse_bank_statement_csv(_as_file(""))


def test_endpoint_parses_uploaded_csv(client):
    response = client.post(
        "/api/v1/parse-bank-statement",
        files={"file": ("statement.csv", CLEAN_CSV.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "avg_monthly_inflow": 100000.0,
        "avg_monthly_outflow": 40000.0,
        "min_ending_balance_avg": 60000.0,
        "bounce_count_last_6m": 0,
        "account_vintage_months": 2,
    }


def test_endpoint_returns_400_for_malformed_csv(client):
    response = client.post(
        "/api/v1/parse-bank-statement",
        files={"file": ("bad.csv", b"foo,bar\n1,2\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "Missing required column" in response.json()["detail"]
