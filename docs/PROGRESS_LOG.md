# Progress Log

Daily record of work on the MSME alternative credit assessment project.
Newest entries at the top. A new dated section is added at the end of every session.

---

## 2026-10-06 — Step 5: Preprocessing pipeline

### Completed
- Created `model/preprocessing.py`: loads the raw synthetic CSV, drops
  `company_id`/`company_name`, adds the 3 derived ratio features
  (`net_cash_margin`, `cash_buffer_ratio`, `gst_to_bank_turnover_ratio`),
  label-encodes `business_category` and `state` into
  `business_category_encoded`/`state_encoded`, and splits into train/test
  (80/20, stratified on `credit_default_status`, `random_state=42`).
- Left the 3 nullable GST columns (and the new `gst_to_bank_turnover_ratio`)
  as NaN for unregistered firms — no imputation — since XGBoost/LightGBM
  handle NaN natively and `has_gst_registration` stays in the feature list
  as the explicit "missing because unregistered" signal.
- Chose label/ordinal encoding over one-hot for the 2 categorical columns:
  tree models split on integer codes fine, and one-hot would have added 18
  extra 0/1 columns that clutter future SHAP summary plots.
- Saved the category-to-code mapping to
  `model/artifacts/category_encodings.json`, so the same encoding can be
  reapplied later (e.g. by the API) instead of being re-derived.
- Added `FEATURE_COLUMNS` (20 columns, explicitly excluding identifiers and
  the target) to `model/config.py`, per the project rule that feature lists
  live only there.
- Saved `data/processed/train.csv` (4,000 rows) and `data/processed/test.csv`
  (1,000 rows).
- Ran the validation summary: 20 features, train/test shapes (4000,21) /
  (1000,21), default rate 14.80% in both the full set, train, and test
  (0.00% difference), no identifier columns in the feature list, and missing
  values confined to exactly the 3 GST columns + the derived GST ratio,
  for the same unregistered-firm rows.
- Updated `CLAUDE.md` current step to "Step 5 complete, next Step 6".

### Files created/changed
- `model/preprocessing.py`: created.
- `model/config.py`: added `FEATURE_COLUMNS`.
- `model/artifacts/category_encodings.json`: created.
- `data/processed/train.csv`, `data/processed/test.csv`: created.
- `CLAUDE.md`: updated current step.

### Decisions made
- Derived ratios are computed and saved into the processed CSVs (not
  recomputed at train time), so train/test files are fully self-contained.
- Encoding choice: label/ordinal encoding (alphabetical order per category)
  rather than one-hot, specifically for tree-model + SHAP friendliness.
- Output format: plain CSVs with features + target together (train.csv /
  test.csv), rather than separate pickled X/y arrays, so the files stay
  human-readable and easy to inspect/debug as a beginner.

### Next step
- Step 6: train a baseline XGBoost/LightGBM model on `data/processed/train.csv`,
  evaluate on `data/processed/test.csv` (expect ROC-AUC roughly 0.75-0.85
  per the data dictionary's design), then move on to SHAP explanations and
  the 300-900 credit score conversion.

---

## 2026-10-06 — Bug fix: account_vintage_months rounding (found in Step 4 EDA)

### Completed
- Fixed the `account_vintage_months` rounding bug found during Step 4 EDA in
  `data/generate_data.py`: the age-based cap now uses `floor(age_of_business_years * 12)`
  consistently everywhere, instead of rounding the cap and the vintage value
  separately (which could round the cap *up* past the true age-in-months for
  some rows).
- Regenerated `data/synthetic/msme_alternative_data.csv` with the same
  `random_state=42` and 5,000 rows. No other column's logic was touched.
- Re-ran the validation summary: default rate 14.80%, GST registration
  83.6%, business category counts, and missing-value counts all essentially
  unchanged from before the fix — confirming only the vintage calculation
  changed.
- Explicitly re-checked the constraint: **0 out of 5,000 rows** now violate
  `account_vintage_months <= age_of_business_years * 12` (was 12/5,000
  before the fix).

### Files created/changed
- `data/generate_data.py`: fixed vintage-cap rounding logic.
- `data/synthetic/msme_alternative_data.csv`: regenerated.

### Decisions made
- Used `floor()` instead of `round()` for the age-in-months cap, since
  rounding can push the cap above the true value; floor guarantees the cap
  is never larger than `age_of_business_years * 12`.

### Next step
- Re-run `notebooks/01_eda.ipynb` against the regenerated CSV to confirm
  Check 1 now passes, then proceed to Step 5: preprocessing
  (`model/preprocessing.py`).

**Update (same day):** re-ran `notebooks/01_eda.ipynb` top to bottom against
the corrected `data/synthetic/msme_alternative_data.csv` using
`jupyter nbconvert --execute`. Check 1 now shows **0 violations / PASS**.
Step 4's Section 5 now passes **5/5 checks** (all other sections unchanged:
default rate 14.80%, same 4 expected-by-design correlated pairs in the
heatmap). Updated the notebook's final summary cell to reflect the all-pass
result and re-saved the notebook with its outputs. Step 4 is now complete
with no open issues; ready to start Step 5.

---

## 2026-10-06 — Step 4: Exploratory Data Analysis (EDA)

### Completed
- Built `notebooks/01_eda.ipynb`, loading `data/synthetic/msme_alternative_data.csv`
  and checking it against `docs/data_dictionary.md`, with a beginner-friendly
  markdown explanation before each section. No cleaning/preprocessing — this
  notebook only observes and visualizes.
- Section 1: shape (5,000 rows x 20 cols), dtypes, and missing-value check —
  confirmed missing values appear in exactly the 3 GST columns and exactly
  for companies with `has_gst_registration == 0`.
- Section 2: target distribution — 741/5,000 defaults (14.82%), close to the
  15% design target.
- Section 3: histograms for 6 key numeric columns — right shapes, zero
  negative values in any of them.
- Section 4: `business_category` percentages close to targets; `state`
  distribution looks like a reasonable weighted spread.
- Section 5: 5 relationship sanity checks from the data dictionary, with
  printed pass/fail and actual numbers (see Decisions below — 4 passed,
  1 failed on a small rounding bug).
- Section 6: box plots + group means comparing 8 key features between
  default = 0 and default = 1 — defaulted companies show worse cash flow,
  more bounces, lower GST regularity, and younger age on average, as
  intended.
- Section 7: correlation heatmap + an automatic flag for any column pair
  with |correlation| > 0.9 — found 4 such pairs, all expected by design.
- Ran the full notebook end-to-end with `jupyter nbconvert --execute` (no
  errors), then filled in the final summary markdown cell with the actual
  findings and a verdict.

### Files created/changed
- `notebooks/01_eda.ipynb`: created and executed.

### Decisions made
- **Bug found:** Check 1 (`account_vintage_months <= age_of_business_years * 12`)
  failed for 12 of 5,000 rows (0.24%) — a floating-point rounding-order issue
  in `data/generate_data.py`'s vintage calculation, not a conceptual flaw.
  Decided to leave `data/generate_data.py` untouched for now (per the
  one-step-at-a-time rule) and fix it at the start of Step 5, regenerating
  the CSV before building the preprocessing pipeline on top of it.
- The 4 correlated column pairs found in Section 7 (inflow<->outflow,
  inflow<->GST turnover, GST turnover<->outflow, age<->account vintage) are
  expected consequences of the generator's design, not bugs. Noted as
  something to keep in mind in Step 5 — e.g. preferring the derived ratios
  over some raw pairs to reduce redundancy for SHAP later.
- Overall verdict: dataset is realistic and ready for Step 5 once the small
  Check 1 rounding bug is patched.

### Next step
- Step 5: fix the `account_vintage_months` rounding bug in
  `data/generate_data.py`, regenerate the CSV, then build the preprocessing
  pipeline (`model/preprocessing.py`) — encode categoricals, handle the
  intentional GST NaNs, and compute the derived ratios (net cash margin,
  cash buffer ratio, GST-to-bank turnover ratio).

---

## 2026-10-06 — Step 3: Synthetic data generation

### Completed
- Created `model/config.py` with shared settings: `RANDOM_SEED = 42`, `N_COMPANIES`,
  `TARGET_DEFAULT_RATE`, `RISK_BANDS`, `ID_COLUMNS`, `TARGET_COLUMN`.
- Wrote `data/generate_data.py`: generates all 20 columns from
  `docs/data_dictionary.md`, in 5 stages (firmographics → banking → GST →
  digital footprint → default label), using `numpy`/`pandas` with the shared
  random seed.
- Modelled realistic correlations instead of independent random columns:
  a hidden per-company "financial health" factor drives outflow ratio, cash
  cushion, volatility and bounce count together; GST filing delay is tied to
  the regularity score; UPI/POS/digital-adoption vary by business category;
  GST registration likelihood rises with annual turnover near the ₹40 lakh
  threshold; `account_vintage_months` is capped at `age_of_business_years × 12`.
  GST columns are `NaN` (not 0) for unregistered firms.
- Implemented the 5-step default-label method (risk signals → interactions →
  noise → logistic → weighted coin flip), with the intercept auto-calibrated
  by bisection so the realised default rate lands near the 15% target.
- Ran the script and validated the output: 5,000 rows × 20 columns, default
  rate 14.8%, GST registration 83.6%, bounce split 58/27/15 (zero/1–2/3+),
  every single-feature AUC ≤ 0.69, and a quick untuned GradientBoosting
  holdout AUC of 0.73 — all within the ranges the data dictionary calls for.
- Updated `CLAUDE.md`: current step set to Step 3, and added the standing
  rule to update this log every session.

### Files created/changed
- `model/config.py`: created (shared constants).
- `data/generate_data.py`: created (generation script).
- `data/synthetic/msme_alternative_data.csv`: generated (5,000 rows).
- `CLAUDE.md`: updated current step + added progress-log coding rule.

### Decisions made
- Used a hidden `_z_health` factor (dropped before saving) to correlate
  banking columns realistically, rather than generating them independently.
- Tuned risk-score weights (bounce weight lowered to 0.55, cash-flow weight
  to 0.75) specifically to keep every single feature's standalone AUC at or
  below ~0.70, so no one column lets the model "cheat".
- GST registration and bounce-count constants were hand-tuned by re-running
  the script and checking the printed distribution against the dictionary's
  target percentages.

### Next step
- Step 4: build the preprocessing pipeline (`model/preprocessing.py`) —
  encode categoricals, handle the intentional GST NaNs, and compute the
  derived ratios noted in the data dictionary (net cash margin, cash buffer
  ratio, GST-to-bank turnover ratio) — then move on to model training.

---

## 2026-10-06 — Step 2: Data dictionary

### Completed
- Designed the 20 columns of the synthetic dataset (`data/synthetic/msme_alternative_data.csv`)
  in five groups: identifiers & firmographics, banking, tax & compliance (GST),
  digital footprint, and the target.
- Gave every column a data type, a realistic Indian value range or category list (INR,
  GST rules, UPI usage by sector), and a reason why it matters for credit risk.
- Wrote down how the default label will be created: hidden risk score → probability →
  random draw.
- Started this progress log.

### Files created/changed
- `docs/data_dictionary.md`: created (was an empty placeholder).
- `docs/PROGRESS_LOG.md`: created.

### Decisions made
- Dataset size: 5,000 rows by default, configurable.
- Default definition: 90+ days past due within 12 months (RBI NPA style). Target
  default rate ≈ 15%.
- Label logic: weighted mix of cash flow health, bounces, GST discipline and business
  age (roughly equal weight), small effects from digital adoption, sector and size,
  plus interactions and random noise. The label is a Bernoulli draw from the resulting
  probability. Expected model ROC-AUC ≈ 0.75–0.85. No single feature should exceed AUC ~0.70.
- Firms without GST registration get **NaN** (not 0) in the three GST columns.
- `company_id` and `company_name` are identifiers, never model inputs.
- `state` gets only a tiny effect on default to avoid regional bias. Check with SHAP later.
- Derived ratios (net cash margin, cash buffer, GST-to-bank turnover) are computed in
  preprocessing and not stored in the CSV.

### Next step
- Step 3: write `data/generate_data.py` to produce the dataset following
  `docs/data_dictionary.md` (with `random_state=42`), then sanity-check the
  distributions, default rate and single-feature AUCs.
