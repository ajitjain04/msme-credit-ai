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
`DATABASE_URL` isn't set — see `backend/database.py`), Streamlit (being
replaced by the Next.js frontend, Step 12b), pytest. Frontend (in
progress): Next.js 15 + React 19 + TypeScript, App Router, Tailwind CSS,
axios, react-plotly.js (chosen over recharts -- matches the literature
review's "Plotly visualisations" spec and reuses the existing Python
gauge config from Step 12; `plotly.js`/`react-plotly.js` still need
adding to `frontend/package.json`).

## Folder layout
data/ (generation + datasets), model/ (ML pipeline), backend/ (FastAPI),
dashboard/ (Streamlit — being replaced), frontend/ (Next.js, replaces
dashboard/), tests/, docs/, notebooks/, scripts/ (one-off setup scripts,
e.g. database seeding).

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

Step 10b complete: PostgreSQL migration. `backend/database.py` reads
`DATABASE_URL` from a git-ignored `.env` (`.env.example` committed as the
template). Live-migrated for real: the `msme_credit` database on
`localhost:5432`, confirmed via the startup log's masked connection
string (not the SQLite fallback), and `scripts/init_db.py` successfully
reseeded 20 companies with calibrated scores (609-861 range, 13 Low Risk
/ 7 Medium Risk — consistent with Step 12c's post-calibration
distribution). `data/processed/msme_credit.db` kept untouched as a
backup/reference, not used going forward.

Step 12e: PDF report generator. Added `model/report_generator.py`'s
`generate_pdf_report()` (reportlab, one-page, builds entirely in a BytesIO
buffer), `GET /api/v1/company/{company_id}/report/pdf` in
`backend/main.py`, and a "Download PDF Report" button in the dashboard's
Tab 1. Reuses `dashboard/components/charts.py`'s `FEATURE_LABELS`/
`feature_label()`/`RISK_BAND_COLORS` rather than redefining them. Found +
fixed 2 real layout bugs (score/probability text crowding; footer
disclaimer colliding with the page number) via visual inspection of a
generated test PDF before handing off. Verified end-to-end via
`TestClient` against a throwaway DB (real evaluate -> real PDF -> correct
headers -> correct 404); not yet run for real.

Bug fix: `POST /api/v1/evaluate` failed on PostgreSQL ("schema np does not
exist") -- numpy.float64/int64 values from `model/scoring.py`/
`model/preprocessing.py` silently worked on SQLite but broke psycopg2
(numpy 2.0+'s `repr()` returns `"np.float64(...)"` text, which Postgres
tried to parse as a schema-qualified call). Fixed with a recursive
`_to_native()` sanitizer in `backend/crud.py`'s
`create_company_and_assessment()` -- the one boundary every DB write
crosses. Verified fixed: both a synthetic numpy-typed test and the REAL
`POST /evaluate` code path now store pure native Python types (confirmed
via throwaway in-memory DB, real Postgres untouched).
`model/report_generator.py` confirmed NOT affected (it only uses
f-string/`float()` formatting, never `repr()`).

PDF report fixes: (1) footer was confirmed PRESENT via `pypdf` ground
-truth parsing (not actually missing/off-page), but sat right at typical
printer hardware-margin clipping risk and was small/low-contrast --
moved up + made more legible. (2) `business_category_encoded`/
`state_encoded` were showing raw numeric codes ("2.00") instead of real
category names -- fixed by decoding them via
`model/artifacts/category_encodings.json` (same file Step 5 used) before
display, with a safe numeric fallback if a code is ever unrecognized.

Step 12e complete: live-verified end-to-end -- PDF downloads correctly
from both the dashboard button and the API directly, with correct
score/risk-band/probability, readable SHAP driver sentences (decoded
category/state names included), and the corrected footer.

Step 12b-1: Next.js frontend scaffolded (frontend/) -- TypeScript, App
Router, Tailwind, ESLint, axios added to package.json. Only a placeholder
homepage built so far (a button that calls GET /health and shows the raw
response) to prove frontend<->backend connectivity before any real UI.
Live-verified end-to-end: `npm install` and `npm run dev` succeeded, and
the placeholder homepage's health-check button successfully called the
real FastAPI `GET /health` and displayed the live JSON response.

GAUGE CHART DECISION RESOLVED: react-plotly.js chosen over recharts --
recharts has no native gauge primitive (would need a hand-rolled
RadialBarChart + custom SVG needle), while react-plotly.js lets the
credit-score gauge reuse almost the exact same
`go.Indicator(mode="gauge+number", gauge={...})` spec the Python
dashboard already has, and matches the literature review's Table 10
"Plotly visualisations" spec. Not yet actioned: `frontend/package.json`
still lists `recharts`, not `plotly.js`/`react-plotly.js` -- swapping
that in (and running `npm install`) is the next sub-step, before building
the real company-evaluation form + scorecard page.

## Upgrade sequence (agreed order, do not resequence without asking)
1. ~~Step 12c: probability calibration~~ — complete.
2. ~~Step 12d: fairness / disparate impact ratio (DIR) auditing~~ — complete.
3. ~~Step 10b: PostgreSQL migration~~ — complete.
4. ~~Step 12e: PDF report generator~~ — complete.
5. **Step 12b: React/Next.js dashboard rewrite (replaces the Streamlit dashboard) — in progress, sub-step 1 of N done.**
6. Step 13: tests.