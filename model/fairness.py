"""
Step 12d — Fairness auditing via the Disparate Impact Ratio (DIR).

WHAT THIS AUDITS, AND WHAT IT DOES NOT (read this before trusting a flag)
----------------------------------------------------------------------------
This audit groups companies by `state` and by `business_category` and
checks whether one group's approval rate looks suspiciously low compared
to another's. Those two columns are the closest thing this project has to
a "protected characteristic" style fairness audit -- but they are NOT
protected characteristics. `state` is geography, and `business_category`
describes the sector a company trades in; both are risk-relevant
BEHAVIOURS AND CIRCUMSTANCES (docs/data_dictionary.md section 1 already
notes sectors genuinely differ in margins, cash cycles and risk), not
attributes like gender, religion or caste -- which this synthetic dataset
does not contain at all, because no such data exists for it to contain.

So a flagged cohort here means one thing precisely: "this group's approval
rate differs from the reference group's by more than the four-fifths rule
allows." It does NOT by itself mean the model is discriminating unlawfully.
It could mean that, OR it could mean the group genuinely has a higher
default rate and the model is correctly pricing that risk. Telling those
two apart requires looking at the group's ACTUAL default rate alongside
the DIR -- which is exactly why this module computes and reports both
together, never DIR alone (per the literature review, Sect 3.5.2: "low
DIR values should be considered along with group-level default rates to
differentiate between discriminatory model structure and legitimate risk
differentiation").

THE DIR FORMULA (literature review, Eq. 4)
----------------------------------------------------------------------------
    DIR = P(approve | group) / P(approve | reference group)

"Approve" here means the company's risk band is Low or Medium Risk (i.e.
NOT High Risk) -- see APPROVED_BANDS below. A DIR below 0.80 ("the
four-fifths rule", a standard US EEOC fairness threshold reused in a lot
of ML-fairness literature) flags potential disparate impact.

HOW GROUND TRUTH (actual default rate) IS RECOVERED
----------------------------------------------------------------------------
The database stores predictions, not outcomes -- Assessment rows don't
carry a "did this company actually default" label, because for a live
API-scored company there's no such label (it hasn't happened yet, or
never will, since this is a synthetic demo). The ONLY place real
historical outcomes exist in this project is data/processed/test.csv's
`credit_default_status` column.

scripts/init_db.py seeded 20 Company/Assessment rows by copying feature
values DIRECTLY from test.csv rows, unchanged. So for each Assessment,
this module rebuilds the same feature "fingerprint" test.csv rows have
(every banking/GST/digital value, rounded for safe float comparison) and
looks it up in a {fingerprint: credit_default_status} table built from
test.csv. A match means "this assessment came from a seeded row with a
known real outcome"; no match means "this was scored live via the API (or
some other source) and has no ground truth" -- those are EXCLUDED from
the actual-default-rate calculation entirely, but still COUNTED in the
approval-rate/DIR calculation (per the brief), and the distinction is
reported explicitly via `cohort_size` (all assessments) vs.
`cohort_size_with_known_outcome` (the subset with a real label).

This module does NOT touch model/scoring.py, model/explainer.py or
model/calibration.py.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import crud  # noqa: E402
from backend.db_models import Assessment, FairnessAuditLog  # noqa: E402
from model.config import FEATURE_COLUMNS, TARGET_COLUMN  # noqa: E402

TEST_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"

# The 4 firmographic columns live on Company, not Assessment (see
# backend/db_models.py) -- the same split backend/main.py and
# scripts/init_db.py already use. Everything else in FEATURE_COLUMNS is a
# banking/GST/digital snapshot value stored directly on Assessment, which
# is what we match back to test.csv for ground truth.
_FIRMOGRAPHIC_COLUMNS = {
    "age_of_business_years",
    "business_category_encoded",
    "state_encoded",
    "employee_count",
}
ASSESSMENT_FEATURE_COLUMNS = [c for c in FEATURE_COLUMNS if c not in _FIRMOGRAPHIC_COLUMNS]

COHORT_DIMENSIONS = ("state", "business_category")
APPROVED_BANDS = {"Low Risk", "Medium Risk"}  # "approve" = NOT High Risk
DIR_THRESHOLD = 0.80  # the "four-fifths rule"
MIN_COHORT_SIZE = 5  # smaller cohorts are statistically unreliable -- excluded by default


def _round_or_none(value: Any) -> Optional[float]:
    """Normalises one feature value for fingerprint matching: None/NaN
    both become None (so a NaN GST column in test.csv and a NULL GST
    column on an Assessment compare equal), everything else is rounded to
    6 decimal places so the matching doesn't fail over float noise."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return round(float(value), 6)


def _build_fingerprint(get_value: Any, columns: list[str]) -> tuple:
    """Builds the "fingerprint" tuple used to match an Assessment row back
    to the test.csv row it was (if ever) seeded from. `get_value(col)`
    abstracts over the two sources this is called with: a pandas row
    (`lambda c: row[c]`) and an Assessment ORM object (`lambda c:
    getattr(assessment, c)`)."""
    return tuple(_round_or_none(get_value(col)) for col in columns)


def load_ground_truth_lookup() -> dict[tuple, int]:
    """Builds the {fingerprint: credit_default_status} lookup from
    data/processed/test.csv -- the only place this project has real
    historical outcomes. See the module docstring's "HOW GROUND TRUTH..."
    section."""
    test_df = pd.read_csv(TEST_CSV_PATH)
    lookup: dict[tuple, int] = {}
    for _, row in test_df.iterrows():
        fingerprint = _build_fingerprint(lambda col, row=row: row[col], ASSESSMENT_FEATURE_COLUMNS)
        lookup[fingerprint] = int(row[TARGET_COLUMN])
    return lookup


def _assessment_fingerprint(assessment: Assessment) -> tuple:
    return _build_fingerprint(lambda col: getattr(assessment, col), ASSESSMENT_FEATURE_COLUMNS)


def compute_dir_audit(
    db: Session,
    dimensions: tuple[str, ...] = COHORT_DIMENSIONS,
    min_cohort_size: int = MIN_COHORT_SIZE,
) -> dict[str, Any]:
    """Computes a fresh Disparate Impact Ratio audit across `dimensions`
    (each scored independently -- a company's `state` cohort and its
    `business_category` cohort are two separate rows, not combined), saves
    every resulting row as a periodic FairnessAuditLog snapshot (all
    sharing one `computed_at`), and returns:

        {
            "audit_logs": [FairnessAuditLog, ...],   # the saved rows
            "excluded_cohorts": [                     # cohorts too small to audit
                {"cohort_dimension": ..., "cohort_value": ..., "cohort_size": ...},
                ...
            ],
        }

    For each dimension: the cohort with the MOST assessments becomes the
    reference group (the most statistically reliable baseline); every
    OTHER eligible cohort gets one row comparing its approval rate to that
    reference's via DIR, alongside its own actual default rate (from
    ground truth only -- see module docstring). Cohorts below
    `min_cohort_size` are excluded entirely (listed in `excluded_cohorts`,
    not scored, not saved).
    """
    ground_truth_lookup = load_ground_truth_lookup()
    assessments = crud.get_all_assessments(db)
    computed_at = datetime.utcnow()

    audit_rows: list[dict[str, Any]] = []
    excluded_cohorts: list[dict[str, Any]] = []

    for dimension in dimensions:
        # Bucket every assessment into its cohort for this dimension,
        # recording whether it was "approved" and whether we know its
        # real outcome.
        cohort_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for assessment in assessments:
            cohort_value = getattr(assessment.company, dimension)
            fingerprint = _assessment_fingerprint(assessment)
            known_default = ground_truth_lookup.get(fingerprint)  # 0, 1, or None
            cohort_records[cohort_value].append(
                {
                    "approved": assessment.risk_band in APPROVED_BANDS,
                    "known_default": known_default,
                }
            )

        eligible_cohorts: dict[str, list[dict[str, Any]]] = {}
        for cohort_value, records in cohort_records.items():
            if len(records) < min_cohort_size:
                excluded_cohorts.append(
                    {
                        "cohort_dimension": dimension,
                        "cohort_value": cohort_value,
                        "cohort_size": len(records),
                    }
                )
            else:
                eligible_cohorts[cohort_value] = records

        if not eligible_cohorts:
            continue

        # Reference group = the most statistically reliable baseline.
        reference_value = max(eligible_cohorts, key=lambda v: len(eligible_cohorts[v]))
        reference_records = eligible_cohorts[reference_value]
        reference_approval_rate = sum(r["approved"] for r in reference_records) / len(reference_records)

        for cohort_value, records in eligible_cohorts.items():
            if cohort_value == reference_value:
                continue  # the reference group isn't scored against itself

            cohort_size = len(records)
            group_approval_rate = sum(r["approved"] for r in records) / cohort_size
            dir_value = (
                group_approval_rate / reference_approval_rate
                if reference_approval_rate > 0
                else None
            )

            known_outcomes = [r["known_default"] for r in records if r["known_default"] is not None]
            cohort_size_with_known_outcome = len(known_outcomes)
            group_actual_default_rate = (
                sum(known_outcomes) / cohort_size_with_known_outcome
                if cohort_size_with_known_outcome > 0
                else None
            )

            flagged_low_dir = dir_value is not None and dir_value < DIR_THRESHOLD

            if flagged_low_dir:
                default_rate_text = (
                    "UNKNOWN (no assessment in this cohort has a ground-truth outcome)"
                    if group_actual_default_rate is None
                    else f"{group_actual_default_rate:.1%} "
                    f"(from {cohort_size_with_known_outcome} of {cohort_size} assessments with known outcomes)"
                )
                print(
                    f"[FAIRNESS WARNING] {dimension}={cohort_value!r}: DIR={dir_value:.3f} "
                    f"(below the {DIR_THRESHOLD} four-fifths-rule threshold, vs. reference "
                    f"{dimension}={reference_value!r}). Actual default rate for this cohort: "
                    f"{default_rate_text}. Per the literature review's methodology, this low "
                    f"DIR must be read ALONGSIDE that default rate -- a genuinely higher "
                    f"default rate would make this legitimate risk differentiation, not "
                    f"discriminatory model structure; a comparable or lower default rate "
                    f"would not."
                )

            audit_rows.append(
                {
                    "computed_at": computed_at,
                    "cohort_dimension": dimension,
                    "cohort_value": cohort_value,
                    "reference_dimension_value": reference_value,
                    "group_approval_rate": group_approval_rate,
                    "reference_approval_rate": reference_approval_rate,
                    "dir_value": dir_value,
                    "group_actual_default_rate": group_actual_default_rate,
                    "cohort_size": cohort_size,
                    "cohort_size_with_known_outcome": cohort_size_with_known_outcome,
                    "flagged_low_dir": flagged_low_dir,
                }
            )

    saved_logs = crud.save_fairness_audit_batch(db, audit_rows) if audit_rows else []

    if excluded_cohorts:
        print(
            f"[FAIRNESS] Excluded {len(excluded_cohorts)} cohort(s) with fewer than "
            f"{min_cohort_size} assessments (too small to audit reliably): "
            + ", ".join(f"{c['cohort_dimension']}={c['cohort_value']!r} (n={c['cohort_size']})" for c in excluded_cohorts)
        )

    return {"audit_logs": saved_logs, "excluded_cohorts": excluded_cohorts}
