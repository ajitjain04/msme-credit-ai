# Project: Explainable AI-based Alternative Credit Assessment for MSMEs

## Goal
Score MSMEs with thin credit files using alternative data (bank transactions,
GST filings, UPI/digital payments). Predict default probability, convert it to
a credit score (300–900), assign risk bands, and explain each score with SHAP.

## Risk bands (do not change without asking)
- Low Risk: score 750+, default probability < 0.20
- Medium Risk: score 600–749, probability 0.20–0.50
- High Risk: score < 600, probability > 0.50

## Tech stack
Python 3.11, pandas, scikit-learn, XGBoost/LightGBM, SHAP, Optuna,
FastAPI + Pydantic, SQLAlchemy + PostgreSQL (SQLite fallback if
`DATABASE_URL` isn't set — see `backend/database.py`), Streamlit, pytest.

## Folder layout
data/ (generation + datasets), model/ (ML pipeline), backend/ (FastAPI),
dashboard/ (Streamlit), tests/, docs/, notebooks/, scripts/ (one-off setup
scripts, e.g. database seeding).

## Coding rules
- The developer is a beginner: add clear comments and docstrings, keep code simple.
- Use random_state=42 everywhere for reproducibility.
- Use type hints. Keep feature lists and thresholds in model/config.py only.
- Explain changes in plain language after making them.
- Work on one step at a time; don't modify files from other steps unless asked.
- Update docs/PROGRESS_LOG.md with a new dated entry at the end of every session,
  in the same format already used in that file.

## Current step
Step 12c complete: probability calibration. Platt (sigmoid) scaling
adopted over isotonic (test Brier 0.1119 vs 0.1125) -- saved to
`model/artifacts/calibrator.joblib`, applied in `score_company()`.
Confirmed via a since-deleted diagnostic script that the resulting skewed
risk-band distribution (76.9% Low Risk) is correct, not a bug: it reflects
the dataset's true ~15% default rate, which `class_weight="balanced"` had
been distorting -- Step 8's original 58.9%/32.9% Medium/High split was
the inflated, wrong one. `model/artifacts/model.joblib` and Step 8's
`probability_to_score()` are both unchanged.

Step 12d complete: fairness auditing (Disparate Impact Ratio). Added
`model/fairness.py`'s `compute_dir_audit()`, a `FairnessAuditLog` table,
2 new crud functions, and `GET /api/v1/analytics/fairness`. Live-run
against the 21 real seeded assessments: flagged `Punjab` (DIR 0.741) and
`trading` (DIR 0.794), both with 0.0% actual default rate but sample
sizes (n=6, n=15) too small for a real conclusion -- mechanism confirmed
working, flags are provisional pending more data. 6 cohorts excluded for
n<5.

Step 10b: PostgreSQL migration. `backend/database.py` now reads
`DATABASE_URL` from a git-ignored `.env` (`.env.example` committed as the
template), falling back to the original SQLite file with a clear warning
if unset. Fixed a real version-specific bug while verifying: this
environment's SQLAlchemy (2.1.3) resolves a bare `postgresql://` URL to
the `psycopg` v3 dialect, not `psycopg2` (what's actually installed) —
the URL must say `postgresql+psycopg2://` explicitly. Both branches
(Postgres URL present / absent) verified via engine construction only (no
real DB connection attempted); real SQLite file confirmed untouched. Not
yet run against a real Postgres server. Next: user installs/starts
PostgreSQL, sets their real password in `.env`, runs
`python scripts/init_db.py` to seed it, then Step 12e.

## Upgrade sequence (agreed order, do not resequence without asking)
1. ~~Step 12c: probability calibration~~ — complete.
2. ~~Step 12d: fairness / disparate impact ratio (DIR) auditing~~ — complete.
3. ~~Step 10b: PostgreSQL migration~~ — code complete, user to run against a real Postgres server.
4. **Step 12e: PDF report generator — next.**
5. Step 12b: React/Next.js dashboard rewrite (replaces the Streamlit dashboard).
6. Step 13: tests.