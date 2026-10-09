"""
Step 10 — One-time database seed script.

Creates the companies/assessments tables (if they don't already exist, via
backend/db_models.py's ORM models) and seeds the database with
N_SEED_COMPANIES companies pulled from data/processed/test.csv, each run
through Step 8's score_company() and Step 9's explain_company() -- so the
database isn't empty when the API (Step 11) and dashboard (Step 12) come
online. Does NOT retrain, re-tune, or change the model in any way.

IMPORTANT CAVEAT -- read this before wondering why the seeded companies
don't look like "MSME004821" etc:
data/processed/test.csv (produced by model/preprocessing.py) deliberately
has NO company_id or company_name column. Identifiers are dropped before
training on purpose (see docs/data_dictionary.md: an ID carries no
predictive meaning and the model could memorise it instead of learning
real patterns), and the 80/20 split was saved without the original row
index. That means this script CANNOT recover the seeded rows' real IDs or
names from data/synthetic/msme_alternative_data.csv -- it generates clearly
-labelled placeholder ones instead ("MSME-SEED-0001", "Seed Company 0001"),
easy to tell apart from the real "MSMEnnnnnn" IDs.

business_category and state ARE recovered exactly, though: they were
label-ENCODED by model/preprocessing.py, not dropped, so this script
decodes business_category_encoded / state_encoded back to their real
string values using model/artifacts/category_encodings.json -- the exact
mapping preprocessing used, inverted. All of the banking/GST/digital
numbers, the model's probability/score/band, and the SHAP explanation are
100% real -- it is only the company's "name tag" that's a placeholder.

How to run (after backend/database.py and backend/db_models.py exist):
    python scripts/init_db.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.db_models import Assessment, Company  # noqa: E402
from model.config import FEATURE_COLUMNS, RANDOM_SEED  # noqa: E402
from model.explainer import explain_company  # noqa: E402
from model.scoring import score_company  # noqa: E402

TEST_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
CATEGORY_ENCODINGS_PATH = PROJECT_ROOT / "model" / "artifacts" / "category_encodings.json"

N_SEED_COMPANIES = 20

# The 4 firmographic columns that live on Company (static profile) instead
# of Assessment (a point-in-time snapshot) -- see backend/db_models.py.
FIRMOGRAPHIC_COLUMNS = {
    "age_of_business_years",
    "business_category_encoded",
    "state_encoded",
    "employee_count",
}
# Everything else in FEATURE_COLUMNS is banking/GST/digital data, which
# DOES belong on the Assessment snapshot.
ASSESSMENT_FEATURE_COLUMNS = [c for c in FEATURE_COLUMNS if c not in FIRMOGRAPHIC_COLUMNS]


def load_category_decoders() -> dict[str, dict[int, str]]:
    """Inverts model/artifacts/category_encodings.json's {category_name:
    code} maps into {code: category_name} maps, so this script can recover
    the ORIGINAL business_category / state strings for each seed row from
    their encoded integer columns. This is an exact lookup, not a guess."""
    with open(CATEGORY_ENCODINGS_PATH) as f:
        encodings = json.load(f)
    return {
        column: {code: name for name, code in mapping.items()}
        for column, mapping in encodings.items()
    }


def _to_native(value: Any) -> Any:
    """Converts a pandas/numpy scalar into a plain Python int/float, and
    NaN specifically into None -- matching the intentional-missingness
    convention from docs/data_dictionary.md (NaN, not 0, for the 3 GST
    columns of unregistered firms) rather than writing a Python `nan`
    float into the database."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def build_company_and_assessment_kwargs(
    row: pd.Series, seed_index: int, decoders: dict[str, dict[int, str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Turns one row of test.csv into (company_kwargs, assessment_kwargs),
    running it through score_company() (Step 8) and explain_company()
    (Step 9) along the way. `row` is passed to both exactly as it comes
    from test.csv -- it already contains every column in FEATURE_COLUMNS,
    which is all either function needs."""
    company_id = f"MSME-SEED-{seed_index:04d}"

    company_kwargs = {
        "company_id": company_id,
        "company_name": f"Seed Company {seed_index:04d}",
        "age_of_business_years": _to_native(row["age_of_business_years"]),
        "business_category": decoders["business_category"][int(row["business_category_encoded"])],
        "state": decoders["state"][int(row["state_encoded"])],
        "employee_count": _to_native(row["employee_count"]),
    }

    score_result = score_company(row)
    explanation = explain_company(row)

    assessment_kwargs: dict[str, Any] = {
        col: _to_native(row[col]) for col in ASSESSMENT_FEATURE_COLUMNS
    }
    assessment_kwargs.update(
        {
            "company_id": company_id,
            "default_probability": score_result["default_probability"],
            "credit_score": score_result["credit_score"],
            "risk_band": score_result["risk_band"],
            "shap_top_drivers": {
                "top_positive_contributors": explanation["top_positive_contributors"],
                "top_negative_contributors": explanation["top_negative_contributors"],
            },
        }
    )
    return company_kwargs, assessment_kwargs


def main() -> None:
    print(f"Creating tables at {engine.url} (if they don't already exist)...")
    Base.metadata.create_all(bind=engine)

    decoders = load_category_decoders()
    test_df = pd.read_csv(TEST_CSV_PATH)
    seed_rows = test_df.sample(n=N_SEED_COMPANIES, random_state=RANDOM_SEED).reset_index(drop=True)
    print(f"Selected {len(seed_rows)} rows from {TEST_CSV_PATH} (random_state={RANDOM_SEED}).")

    db = SessionLocal()
    try:
        n_new_companies = 0
        n_new_assessments = 0

        for position, row in seed_rows.iterrows():
            seed_index = position + 1
            company_kwargs, assessment_kwargs = build_company_and_assessment_kwargs(
                row, seed_index, decoders
            )

            existing_company = db.get(Company, company_kwargs["company_id"])
            if existing_company is not None:
                # Re-running this script re-assesses the same 20 seed
                # companies -- exactly the "re-assessed later" scenario
                # backend/db_models.py's docstring describes: this adds a
                # NEW Assessment row, it does not touch the existing
                # Company row.
                db.add(Assessment(**assessment_kwargs))
                n_new_assessments += 1
                print(f"  {company_kwargs['company_id']}: already exists, added a new Assessment.")
            else:
                company = Company(**company_kwargs)
                company.assessments.append(Assessment(**assessment_kwargs))
                db.add(company)
                n_new_companies += 1
                n_new_assessments += 1
                print(
                    f"  {company_kwargs['company_id']}: new Company + Assessment "
                    f"(score={assessment_kwargs['credit_score']}, "
                    f"band={assessment_kwargs['risk_band']})."
                )

        db.commit()
        print(
            f"\nDone. Added {n_new_companies} new Company row(s) and "
            f"{n_new_assessments} new Assessment row(s) to {engine.url}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
