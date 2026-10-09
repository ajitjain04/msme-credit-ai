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
FastAPI + Pydantic, SQLAlchemy + SQLite, Streamlit, pytest.

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

Step 12c complete. Next: Step 12d (fairness/DIR auditing).

## Upgrade sequence (agreed order, do not resequence without asking)
1. ~~Step 12c: probability calibration~~ — complete.
2. **Step 12d: fairness / disparate impact ratio (DIR) auditing — next.**
3. Step 10b: PostgreSQL migration (replaces the SQLite database layer).
4. Step 12e: PDF report generator.
5. Step 12b: React/Next.js dashboard rewrite (replaces the Streamlit dashboard).
6. Step 13: tests.