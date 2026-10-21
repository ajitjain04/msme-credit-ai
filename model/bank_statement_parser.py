"""
Bank-statement CSV parser: turns a transaction list into 5 of the
evaluate form's banking fields, so a user doesn't have to type them.

OUR STANDARD CSV FORMAT (not any one bank's -- export/convert to this)
----------------------------------------------------------------------------
Header row, exactly these column names (case-insensitive, any order):

    date,description,debit,credit,balance

  date         YYYY-MM-DD, e.g. 2026-04-02
  description  free text (used to spot bounced / returned payments)
  debit        money OUT, a positive number; blank on a credit row
  credit       money IN, a positive number; blank on a debit row
  balance      running account balance after that transaction

Example:
    date,description,debit,credit,balance
    2026-04-02,NEFT-Customer Sharma Enterprises,,185000,385000
    2026-04-05,NEFT-Supplier Raw Materials,120000,,265000

HOW EACH OUTPUT FIELD IS COMPUTED
----------------------------------------------------------------------------
  avg_monthly_inflow      mean of each calendar month's total credits
  avg_monthly_outflow     mean of each calendar month's total debits
  min_ending_balance_avg  mean of each month's lowest balance value
  bounce_count_last_6m    rows in the last 6 months of the statement whose
                          description matches a bounce/return phrase
  account_vintage_months  whole months from the earliest to the latest date

SHORT / PARTIAL STATEMENTS
----------------------------------------------------------------------------
- Fewer than 6 months of data: the "last 6 months" window simply covers the
  whole statement, so every row is checked for bounces. Monthly averages use
  however many months the statement spans (e.g. 3 months -> mean of 3).
- Months between the first and last date with NO transactions count as 0
  inflow / 0 outflow in the averages (a quiet month is real information).
  They are skipped for min_ending_balance_avg (no balance was recorded).
- A partial first or last month (e.g. a statement ending on the 10th) is
  treated as a full month, which can pull the averages down slightly.
- account_vintage_months is the span of the STATEMENT, not the true account
  age -- it is a lower bound if the user only uploads recent months.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, BinaryIO, Union

import pandas as pd

REQUIRED_COLUMNS = ["date", "description", "debit", "credit", "balance"]
DATE_FORMAT = "%Y-%m-%d"
BOUNCE_WINDOW_MONTHS = 6

EXPECTED_FORMAT_HELP = (
    "Expected a CSV with the header row 'date,description,debit,credit,balance': "
    "date as YYYY-MM-DD, debit/credit as positive numbers (leave the other blank), "
    "and balance as the running balance after each transaction."
)

# Common Indian-bank phrasings for a bounced / returned / failed payment.
# Matched case-insensitively against the description.
BOUNCE_PATTERNS = [
    r"cheque\s+(?:returned|return|bounce|bounced|dishonou?red)",
    r"chq\s+(?:returned|return|bounce|bounced|dishonou?red)",
    r"(?:ecs|nach|ach|emi)\s+(?:return|returned|bounce|bounced)",
    r"insufficient\s+(?:funds?|balance)",
    r"bounce[d]?",
    r"dishonou?r",
    r"return\s+charges",
    r"payment\s+returned",
]
_BOUNCE_REGEX = re.compile("|".join(BOUNCE_PATTERNS), flags=re.IGNORECASE)


class BankStatementError(ValueError):
    """Raised for any malformed statement. The message is written to be
    shown directly to the user (the API returns it as a 400)."""


def _read_and_validate(file_or_path: Union[str, Path, BinaryIO]) -> pd.DataFrame:
    """Reads the CSV and returns a clean DataFrame with parsed dates and
    numeric debit/credit/balance, or raises BankStatementError."""
    try:
        df = pd.read_csv(file_or_path)
    except pd.errors.EmptyDataError:
        raise BankStatementError(f"The file is empty. {EXPECTED_FORMAT_HELP}") from None
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise BankStatementError(f"Could not read the file as a CSV ({exc}). {EXPECTED_FORMAT_HELP}") from None

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise BankStatementError(f"Missing required column(s): {', '.join(missing)}. {EXPECTED_FORMAT_HELP}")

    df = df[REQUIRED_COLUMNS].dropna(how="all")
    if df.empty:
        raise BankStatementError(f"The file has a header but no transactions. {EXPECTED_FORMAT_HELP}")

    df["date"] = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    if df["date"].isna().any():
        bad_row = int(df["date"].isna().to_numpy().argmax()) + 2  # +2: header + 1-based
        raise BankStatementError(f"Invalid date on CSV line {bad_row}; dates must be YYYY-MM-DD. {EXPECTED_FORMAT_HELP}")

    for column in ("debit", "credit", "balance"):
        converted = pd.to_numeric(df[column], errors="coerce")
        # Blank debit/credit is fine (-> 0); a non-blank value that isn't a number is not.
        if (converted.isna() & df[column].notna()).any() or (column == "balance" and converted.isna().any()):
            raise BankStatementError(f"Column '{column}' contains non-numeric or missing values. {EXPECTED_FORMAT_HELP}")
        df[column] = converted if column == "balance" else converted.fillna(0.0)

    if (df["debit"] < 0).any() or (df["credit"] < 0).any():
        raise BankStatementError(f"debit and credit must be positive numbers. {EXPECTED_FORMAT_HELP}")
    if ((df["debit"] > 0) & (df["credit"] > 0)).any():
        raise BankStatementError(f"A row has both a debit and a credit; only one may be filled. {EXPECTED_FORMAT_HELP}")

    df["description"] = df["description"].fillna("").astype(str)
    return df.sort_values("date").reset_index(drop=True)


def parse_bank_statement_csv(file_or_path: Union[str, Path, BinaryIO]) -> dict[str, Any]:
    """Parses a statement in our standard CSV format (see module docstring)
    and returns:

        {
          "avg_monthly_inflow": float,
          "avg_monthly_outflow": float,
          "min_ending_balance_avg": float,
          "bounce_count_last_6m": int,
          "account_vintage_months": int,
        }

    Raises BankStatementError (a ValueError) with a user-readable message
    if the file is malformed.
    """
    df = _read_and_validate(file_or_path)
    months = df["date"].dt.to_period("M")

    # Every calendar month from first to last, so a month with no
    # transactions counts as 0 rather than being skipped.
    all_months = pd.period_range(months.min(), months.max(), freq="M")
    monthly_in = df.groupby(months)["credit"].sum().reindex(all_months, fill_value=0.0)
    monthly_out = df.groupby(months)["debit"].sum().reindex(all_months, fill_value=0.0)
    monthly_min_balance = df.groupby(months)["balance"].min()

    first_date, last_date = df["date"].min(), df["date"].max()

    # Last 6 months of the statement, counted back from its final date. A
    # shorter statement just means the window covers every row.
    window_start = last_date - pd.DateOffset(months=BOUNCE_WINDOW_MONTHS)
    recent = df[df["date"] > window_start]
    bounce_count = int(recent["description"].str.contains(_BOUNCE_REGEX).sum())

    # Whole months between first and last date (minus one if the last day-of
    # -month hasn't reached the first's, e.g. Apr 20 -> Sep 10 is 4, not 5).
    vintage = (last_date.year - first_date.year) * 12 + (last_date.month - first_date.month)
    if last_date.day < first_date.day:
        vintage -= 1

    return {
        "avg_monthly_inflow": round(float(monthly_in.mean()), 2),
        "avg_monthly_outflow": round(float(monthly_out.mean()), 2),
        "min_ending_balance_avg": round(float(monthly_min_balance.mean()), 2),
        "bounce_count_last_6m": bounce_count,
        "account_vintage_months": max(vintage, 0),
    }


if __name__ == "__main__":
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_bank_statement.csv"
    print(parse_bank_statement_csv(sample))
