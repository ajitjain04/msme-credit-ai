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
dashboard/ (Streamlit), tests/, docs/, notebooks/.

## Coding rules
- The developer is a beginner: add clear comments and docstrings, keep code simple.
- Use random_state=42 everywhere for reproducibility.
- Use type hints. Keep feature lists and thresholds in model/config.py only.
- Explain changes in plain language after making them.
- Work on one step at a time; don't modify files from other steps unless asked.
- Update docs/PROGRESS_LOG.md with a new dated entry at the end of every session,
  in the same format already used in that file.

## Current step
Step 5 complete: preprocessing pipeline. Next: Step 6 (model training).