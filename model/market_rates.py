"""
Typical business-loan rates in the market (static reference table).

This is NOT personalised. Every user sees the identical list on every call:
nothing here looks at the applicant's credit score or risk band. It is simply
a reference of indicative rates that banks/NBFCs publish for business loans,
copied from the sources in each entry's "url" as of RATES_AS_OF. Rates change,
so the dashboard tells users to confirm with the bank.

`rate_min` / `rate_max` are the same published numbers as `rate_range`, kept
as plain numbers so the frontend EMI calculator can pre-fill a rate when a
card is clicked. `rate_max` is None where the bank publishes no upper bound.

To refresh the table: edit MARKET_RATES and update RATES_AS_OF here only.

Run the built-in example:
    venv\\Scripts\\python.exe model/market_rates.py
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

# The date these rates were last copied from the banks' pages.
RATES_AS_OF = date(2026, 10, 28)

DISCLAIMER_TEMPLATE = (
    "Indicative rates published by banks, as of {as_of}. Not a personalized "
    "offer -- confirm current rates and eligibility directly with the bank. "
    "This assessment's credit score does not come from a real credit bureau."
)

MARKET_RATES: list[dict[str, Any]] = [
    {
        "name": "HDFC Bank",
        "rate_range": "10.75% - 22.50% p.a.",
        "rate_min": 10.75,
        "rate_max": 22.5,
        "note": "Processing fee up to 2%; fee waiver for MSEs up to Rs 5L (Udyam-registered)",
        "url": "https://hdfcbank.com/personal/products/loans/business-loan/rates-fees",
    },
    {
        "name": "State Bank of India",
        "rate_range": "From ~10.05% p.a.",
        "rate_min": 10.05,
        "rate_max": None,
        "note": "No published upper bound",
        "url": "https://sbi.co.in/web/business/sme/sme-loans",
    },
    {
        "name": "ICICI Bank",
        "rate_range": "~11.25% - 11.75% p.a.",
        "rate_min": 11.25,
        "rate_max": 11.75,
        "note": "Repo-linked (Repo + 6.00-6.50%); processing fee up to 2%",
        "url": "https://icicibank.com/business-banking/finance/index",
    },
    {
        "name": "Axis Bank",
        "rate_range": "11% - 25% p.a.",
        "rate_min": 11.0,
        "rate_max": 25.0,
        "note": "Per Axis's own business-loan calculator",
        "url": "https://axisbank.com/business-banking/small-business-banking/unsecured-loans/unsecured-instant-business-loan",
    },
    {
        "name": "Bajaj Finserv",
        "rate_range": "From ~14% p.a.",
        "rate_min": 14.0,
        "rate_max": None,
        "note": "Per Bajaj Finserv's published rate page",
        "url": "https://www.bajajfinserv.in/business-loan",
    },
    {
        "name": "Kotak Mahindra Bank",
        "rate_range": "~9.50% - 30.50% p.a.",
        "rate_min": 9.5,
        "rate_max": 30.5,
        "note": "Range depends on risk/collateral",
        "url": "https://kotak.com/en/business/loans/business-loan.html",
    },
]


def get_market_rates() -> list[dict[str, Any]]:
    """The same list every time (copies, so callers can't mutate the table)."""
    return [dict(entry) for entry in MARKET_RATES]


def get_disclaimer(as_of: Optional[date] = None) -> str:
    """The banner text, with the as-of date filled in (e.g. '28 October 2026')."""
    when = as_of or RATES_AS_OF
    return DISCLAIMER_TEMPLATE.format(as_of=f"{when.day} {when.strftime('%B %Y')}")


if __name__ == "__main__":
    print(get_disclaimer())
    for entry in get_market_rates():
        print(f"{entry['name']}: {entry['rate_range']}")
