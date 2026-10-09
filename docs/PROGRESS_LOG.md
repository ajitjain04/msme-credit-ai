# Progress Log

Daily record of work on the MSME alternative credit assessment project.
Newest entries at the top. A new dated section is added at the end of every session.

---

## 2026-10-09 — Step 12b-3: PDF button, Portfolio & Fairness pages (React) -- Step 12b complete

### Completed
- **PDF download button**: added `downloadCompanyPdfReport()` to
  `frontend/lib/api.ts` (fetches `GET /api/v1/company/{company_id}/report
  /pdf` with `responseType: "blob"`, then the standard browser
  blob->object-URL->temporary-`<a>`-click pattern) and wired a "Download
  PDF Report" button into `frontend/app/page.tsx`'s scorecard section,
  matching the existing button styling, with its own loading/error state.
- **Portfolio Overview page**: `frontend/app/portfolio/page.tsx` (new
  route) + `frontend/components/PortfolioPieChart.tsx` (1:1 port of
  `build_portfolio_pie_chart()`) -- stat cards (total companies, average
  score, % High Risk) + the risk-band donut chart + a manual Refresh
  button, matching `dashboard/app.py`'s Tab 3.
- **Fairness Audit page**: `frontend/app/fairness/page.tsx` (new route,
  no Streamlit equivalent existed) -- a plain-language DIR explainer, a
  cohort table pairing DIR with its actual default rate and cohort size
  (never DIR alone, same principle `backend/main.py`'s
  `get_fairness_audit()` docstring states), a red badge for
  `flagged_low_dir` cohorts, and the excluded-small-cohorts list.
- **Navigation**: added a top nav bar to `frontend/app/layout.tsx` (via
  `next/link`, so every page gets it and navigation is client-side) with
  links to Evaluate (`/`), Portfolio (`/portfolio`), and Fairness Audit
  (`/fairness`).
- **Bug fix: low-contrast table text on the Fairness Audit page.** Root
  cause was more specific than a copy-pasted muted class: 4 of the
  table's `<td>` cells (`cohort_value`, `dir_value`,
  `group_actual_default_rate`, `cohort_size`) had **no explicit Tailwind
  text-color class at all**, so they inherited `globals.css`'s
  `--foreground` CSS variable -- which is near-black in light mode but
  flips to near-white (`#ededed`) under `prefers-color-scheme: dark`.
  Every card/table on the page uses hardcoded light backgrounds
  (`bg-white`/`bg-gray-50`) that do NOT flip with that media query, so on
  a dark-mode system those 4 cells rendered near-white text on a light
  background -- invisible -- while the header row and the `text-gray-900`
  dimension column stayed readable because their colors were explicit.
  Fixed by adding `text-gray-900` to those 4 cells; the intentionally
  muted "Reference Cohort" column (`text-gray-500`) and the colored
  OK/flagged badges were left untouched, as asked.

### Verified end-to-end (real browser, real backend)
- PDF button downloads a real PDF matching the backend-generated report.
- Portfolio page: live stat cards (28 companies, avg score 792, 75% Low /
  25% Medium / 0% High at time of testing) and a working donut chart;
  Refresh re-fetches correctly.
- Fairness Audit page: DIR explainer renders, DIR is always paired with
  actual default rate (never shown alone), excluded small cohorts are
  listed, and the low-contrast fix holds up.

### Step 12b complete
The full React/Next.js dashboard now has feature parity with the
Streamlit dashboard (evaluation form, scorecard, SHAP explainability, PDF
download, portfolio overview) plus a Fairness Audit page Streamlit never
had -- matching the literature review's Table 10 architecture ("React/
Next.js dashboard with Plotly visualisations"). All 5 planned upgrades
(12c, 12d, 10b, 12e, 12b) from the agreed upgrade sequence are now done.

### Next step
Step 13: tests (`tests/test_api.py`, `tests/test_predictor.py`,
`tests/test_scoring.py`).

---

## 2026-10-09 — Step 12b-2: real evaluation form, scorecard & SHAP view (React)

### Completed
- **Built the real Next.js homepage**, replacing the Step 12b-1
  placeholder entirely: `frontend/components/EvaluationForm.tsx` (same
  fields/min/max/defaults as `dashboard/app.py`'s sidebar, grouped into
  the same 4 sections, laid out as a multi-column form instead of a
  cramped sidebar), `frontend/components/ScoreGauge.tsx` (1:1 port of
  `build_score_gauge()` via `react-plotly.js`), and
  `frontend/components/ShapDriverChart.tsx` (1:1 port of
  `build_shap_driver_chart()`, same tornado layout). Added
  `frontend/lib/types.ts` (TypeScript interfaces mirroring every
  `backend/schemas.py` shape), `frontend/lib/api.ts` (typed axios client +
  a shared `formatApiError()`), and `frontend/lib/featureLabels.ts` (ported
  `FEATURE_LABELS`/`feature_label()`/`RISK_BAND_COLORS` from
  `dashboard/components/charts.py`). `frontend/package.json` now actually
  lists `plotly.js`/`react-plotly.js` (not just `recharts`, which is
  removed). Portfolio Overview, Fairness Audit, and the PDF download
  button are intentionally not built yet (next sub-step).
- **Bug fix: encoded category/state values leaking into the UI.**
  `business_category_encoded`/`state_encoded` were displaying as raw
  numeric codes (e.g. "2.00") instead of readable names (e.g. "retail")
  in the SHAP driver sentences -- the same problem Step 12e's PDF fix
  solved, but that fix was local to `model/report_generator.py` only and
  never reached the API's actual JSON responses. Fixed at the source in
  `backend/main.py`: renamed `model/report_generator.py`'s
  `_format_driver_value()` to public `format_driver_value()` (same logic,
  zero duplication), added a `display_value: str` field to
  `backend/schemas.py`'s `ShapDriver`, and populated it via a new
  `_with_display_values()` helper at both `POST /api/v1/evaluate` and
  `GET /api/v1/company/{company_id}`. Also updated `dashboard/app.py`'s
  two driver sentences to use `display_value` instead of formatting the
  raw encoded number themselves. Result: React, the old Streamlit
  dashboard, and the PDF report now all show the exact same decoded text
  from one source instead of three separately-maintained fixes. Verified
  via `TestClient` against a throwaway in-memory DB: both endpoints'
  `business_category_encoded` driver now returns `display_value: "retail"`
  instead of a raw code; real Postgres untouched.
- **Debugging lesson, not a bug:** a reported "CORS 400" turned out to be
  a false alarm. The actual cause was the browser being on the Next.js
  dev server's **Network** URL (`http://192.168.1.14:3000`) instead of
  its **Local** URL (`http://localhost:3000`) -- the request's `Origin`
  header then didn't match the backend's intentionally-scoped
  localhost/127.0.0.1-only `allow_origin_regex`. No code was broken.
  Verified this *before* changing anything: sent a real CORS preflight
  (`OPTIONS /api/v1/evaluate`, `Origin: http://localhost:3000`) straight
  at the live ASGI app via `TestClient` and got back `200` with correct
  `access-control-*` headers, proving the existing regex already covered
  port 3000 correctly. Fixed by using the correct (Local) URL, not by
  editing `backend/main.py`'s CORS logic -- only added clarifying
  comments there documenting why the existing config already covers any
  localhost port.

### Verified end-to-end
Real browser session: filled in the evaluation form -> submitted ->
real FastAPI `/evaluate` call -> real model score -> gauge chart render
-> SHAP tornado chart render -> readable, correctly-decoded driver
sentences, all in the browser, no placeholder data.

### Next step
Step 12b-3: PDF download button, Portfolio Overview page, and Fairness
Audit page in the React frontend (the 3 pieces of Streamlit functionality
not yet ported).

---

## 2026-10-09 — Step 12b-1 (confirmed): react-plotly.js chosen; verified end-to-end

### Completed
- **Gauge/chart library decision resolved** (flagged as pending in the
  entry below): chose `react-plotly.js` over `recharts` for the frontend
  charting library, specifically to (a) match the literature review's
  Table 10 spec of "Plotly visualisations" directly, rather than
  substituting a different library, and (b) let the credit-score gauge
  reuse the existing `go.Indicator(mode="gauge+number", gauge={...})`
  config `dashboard/components/charts.py`'s `build_score_gauge()` already
  defines from Step 12, instead of hand-rolling a gauge recharts has no
  native primitive for.
- **Verified end-to-end for real:** `npm install` and `npm run dev`
  (Next.js dev server) both succeeded. The placeholder homepage's "Test
  API Connection" button successfully called `GET /health` on the real
  running FastAPI backend and displayed the live JSON response on the
  page — confirming the frontend↔backend connection works before any
  real UI gets built on top of it.

### Next step
- Add `plotly.js` + `react-plotly.js` to `frontend/package.json` (not yet
  reflected there) and `npm install` them, then build the real
  company-evaluation form + scorecard page, reusing the existing Python
  gauge spec as the starting point for its React port.

---

## 2026-10-09 — Step 12b-1: Next.js frontend scaffolded

### Completed
- Created `frontend/`: a hand-written Next.js scaffold matching what
  `create-next-app` would generate with TypeScript + Tailwind CSS + App
  Router + ESLint selected — `package.json`, `tsconfig.json`,
  `next-env.d.ts`, `next.config.mjs`, `tailwind.config.ts`,
  `postcss.config.mjs`, `eslint.config.mjs` (flat config, matching
  current `create-next-app` output), `app/layout.tsx`, `app/page.tsx`,
  `app/globals.css`.
- Added `axios` and `recharts` to `package.json`'s dependencies (not
  installed — no `npm install` run, per instructions).
- **Gauge chart library choice flagged, not decided:** the brief asked
  for either a justification of `recharts` or an honest tradeoff if
  `plotly.js`/`react-plotly.js` would genuinely fit better. Conclusion:
  `recharts` is clearly the better, more idiomatic fit for the SHAP
  tornado chart and the portfolio donut chart (both have natural recharts
  equivalents — `BarChart` with two series, `PieChart` with
  `innerRadius`). The credit-score **gauge** is the one exception worth
  flagging: recharts has no native gauge primitive at all (would need a
  hand-rolled `RadialBarChart` + custom SVG needle), whereas
  `react-plotly.js` would let that one chart reuse almost the exact same
  `go.Indicator(mode="gauge+number", gauge={...})` spec
  `dashboard/components/charts.py`'s `build_score_gauge()` already
  defines. Not resolved now — `recharts` was added as explicitly
  requested; this tradeoff is flagged for the next sub-step (building the
  real scorecard page), where the user can decide whether to also add
  `plotly.js` + `react-plotly.js` just for that one chart.
- Created `frontend/.env.local` (git-ignored) and
  `frontend/.env.local.example` (committed template), both setting
  `NEXT_PUBLIC_API_URL=http://localhost:8000` — the `NEXT_PUBLIC_`
  prefix is required for Next.js to inline the variable into the
  client-side JavaScript bundle at build time (explained in-file).
- Updated the project root `.gitignore` with
  `frontend/node_modules/`, `frontend/.next/`, `frontend/out/`,
  `frontend/.env.local`, plus 2 standard Next.js extras
  (`npm-debug.log*`, `.vercel`), all scoped under `frontend/`.
- Built **only** the minimal placeholder homepage requested:
  `app/page.tsx` is a `"use client"` component with a title, a short
  explanatory note, and one button that calls `GET /health` via `axios`
  and displays the raw JSON (or a clear connection-error message) on the
  page — purely to prove frontend↔backend connectivity before any real
  UI. No form, scorecard, or chart page built yet.
- Skipped `next/font`'s default Google Fonts (Geist) setup that
  `create-next-app` normally wires into `layout.tsx` — avoids a
  build-time network dependency on Google Fonts for no real benefit yet;
  noted in a comment as something to add back later if a specific look
  is wanted. Also skipped the default `public/` placeholder SVG assets
  (unused by our custom `page.tsx`, not part of the file list requested).

### Files created/changed
- `frontend/` (new): `package.json`, `tsconfig.json`, `next-env.d.ts`,
  `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`,
  `eslint.config.mjs`, `app/layout.tsx`, `app/page.tsx`,
  `app/globals.css`, `.env.local`, `.env.local.example`.
- `.gitignore`: added `frontend/` build-artifact/env entries.
- `CLAUDE.md`: tech stack, folder layout, current step updated.

### Decisions made
- Verified Node (v22.14.0) and npm (11.6.2) are available in this
  environment before scaffolding, but did NOT run `npm install` or
  `npm run dev`, per instructions.
- Used Tailwind CSS v3-style explicit config (`tailwind.config.ts` +
  `postcss.config.mjs` + `@tailwind` directives in `globals.css`) rather
  than Tailwind v4's newer CSS-first/no-config-file approach some very
  recent `create-next-app` versions default to — the brief explicitly
  listed `tailwind.config` among the expected files, and an explicit
  config file is more beginner-readable than v4's implicit setup.

### Next step
- User runs `npm install` then `npm run dev` inside `frontend/`, confirms
  the placeholder page loads and the "Test API Connection" button
  successfully reaches the FastAPI backend's `/health` endpoint (backend
  must be running separately). Then the next Step 12b sub-step: the real
  company-evaluation form + scorecard page, including the gauge-library
  decision flagged above.

---

## 2026-10-09 — Step 12e (complete): PDF report generator, live-verified

### Completed
- Built the downloadable one-page PDF credit-assessment report:
  `model/report_generator.py` (`reportlab`) and
  `GET /api/v1/company/{company_id}/report/pdf` (see the two detailed
  entries below for the full build + bug-fix history).
- Found and fixed two issues during review, before declaring this done:
  1. **Footer disclaimer** was present in the PDF (confirmed via `pypdf`
     text extraction) but positioned too close to the page edge (printer
     -margin clipping risk) and too faint to notice easily — repositioned
     and restyled for legibility.
  2. **`business_category`/`state`** were displaying as raw internal
     encoded numbers (e.g. `"2.00"`) instead of readable names — fixed by
     decoding them back to their real category/state names using
     `model/artifacts/category_encodings.json` before display, without
     touching `model/explainer.py`'s actual SHAP computation.
- **Verified end-to-end for real:** the PDF downloads correctly both from
  the dashboard's "Download PDF Report" button and from the API endpoint
  directly, and shows the correct score/risk-band/probability, readable
  plain-English SHAP driver sentences (including decoded category/state
  names), and the corrected, legible footer.

### Next step
- Step 12b: React/Next.js dashboard rewrite (replaces the Streamlit
  dashboard).

---

## 2026-10-09 — Bug fix: PDF report footer visibility + raw encoded category values

### Completed
- **Issue 1 (footer):** investigated whether the disclaimer/page-number
  footer was genuinely missing from `model/report_generator.py` or just
  rendering off-page. Installed `pypdf` temporarily (ground-truth PDF
  parsing, not just my own Read-tool rendering) and confirmed the footer
  text **was** present, on exactly 1 page, correctly extracted — so it
  was never literally missing or cut off by reportlab. However, it sat at
  y=38pt, right at the edge of the ~36pt hardware margin most printers
  refuse to print inside (real clipping risk if ever physically printed),
  and was small (7pt) + low-contrast (light gray) — an easy combination
  to overlook at a glance, which is the most likely explanation for it
  reading as "missing." Fixed by moving the whole footer block up
  (lowest baseline now y=44, safely clear of typical printer margins) and
  making it slightly larger/darker (7pt light gray → 8pt `#444444`) for
  legibility, without touching the driver-drawing logic that determines
  the footer's position is otherwise unaffected by.
- **Issue 2 (raw encoded values):** `business_category_encoded`/
  `state_encoded` were displaying their raw internal integer codes (e.g.
  "Business Category: 2.00") instead of a real category name — correct
  input to SHAP, meaningless to a report reader. Added
  `_format_driver_value()`, which decodes exactly these 2 features back
  to their real name (e.g. "retail", "Maharashtra") via
  `model/artifacts/category_encodings.json` — the SAME file Step 5's
  `model/preprocessing.py` used to encode them in the first place, loaded
  once and inverted at import time. Every other feature's display is
  completely unchanged (still a plain formatted number). Falls back to
  showing the raw number if a code is ever unrecognized (shouldn't happen
  in practice) rather than crashing the report.
- `model/explainer.py` (the actual SHAP computation) was **not** touched,
  per the brief — only how `model/report_generator.py` *displays* these
  2 features' already-computed values.
- **Verified both fixes together, without running the real server:**
  regenerated a test PDF with `business_category_encoded`/`state_encoded`
  among the top drivers, confirmed via `pypdf` text extraction that
  `"Business Category: retail"` and `"State: Maharashtra"` appear (and
  `"2.00"`/`"8.00"` do NOT), that the footer disclaimer + "Page 1 of 1"
  are present, and visually re-inspected the rendered PDF. Also
  unit-tested `_format_driver_value()` directly, including its fallback
  path for an unrecognized code. Deleted all test PDFs and uninstalled
  the temporary `pypdf` verification dependency afterward (never added
  to `requirements.txt` — it was a diagnostic tool, not a project
  dependency).

### Files created/changed
- `model/report_generator.py`: added `_format_driver_value()` +
  `_ENCODED_FEATURE_DECODERS`; `_driver_sentence()` now takes an
  already-formatted display string instead of a raw float; footer
  repositioned/restyled.
- `model/explainer.py`: confirmed untouched, per the brief.

### Decisions made
- Diagnosed the footer issue with `pypdf` (independent ground truth)
  rather than trusting only my own earlier visual inspection — confirmed
  it was a legibility/margin-safety problem, not the literal "missing
  code" or "off-page" bug the brief anticipated, and said so plainly
  rather than just silently making cosmetic tweaks.
- Kept the category-decoding fallback (unrecognized code → raw number)
  rather than raising an error, consistent with this project's general
  preference for a report that still generates (with one imperfect value)
  over one that fails outright.

### Next step
- User regenerates a real PDF report (via the dashboard's "Download PDF
  Report" button or the API endpoint directly) for a company whose top
  drivers include `business_category_encoded`/`state_encoded`, confirms
  both fixes look right, then Step 12b: React/Next.js dashboard rewrite.

---

## 2026-10-09 — Bug fix: numpy scalar types breaking PostgreSQL inserts

### Completed
- **Bug found by the user against the real Postgres database:**
  `POST /api/v1/evaluate` failed with
  `psycopg2.errors.InvalidSchemaName: schema "np" does not exist` — did
  NOT fail on SQLite. Root cause: `model/scoring.py`'s `score_company()`
  and the pandas/numpy arithmetic behind `model/preprocessing.py`'s
  derived ratios (`net_cash_margin`, `cash_buffer_ratio`, etc.) produce
  `numpy.float64`/`numpy.int64` values, not native Python ones — any
  pandas Series lookup returns numpy scalars, even for one row.
  `numpy.float64` **is** a `float` subclass, so SQLite's loose typing
  silently accepted it with no problem; psycopg2 doesn't recognize numpy
  types and falls back to a `repr()`-based substitution — and as of
  numpy 2.0+, `repr(np.float64(600000.0))` returns the **string**
  `"np.float64(600000.0)"` (confirmed directly: numpy 2.4.6 in this
  venv), which lands in the SQL unquoted and Postgres tries to parse
  `np` as a schema name.
- **Fix:** added a recursive `_to_native()` sanitizer to `backend/crud.py`,
  called at the top of `create_company_and_assessment()` — the single
  boundary every database write already passes through — converting any
  `numpy.floating`/`numpy.integer`/`numpy.bool_` found anywhere inside
  `company_data`/`assessment_data` (including nested, e.g. inside
  `shap_top_drivers`'s list of driver dicts) into native Python
  `float`/`int`/`bool`. `model/scoring.py` and `model/preprocessing.py`
  were NOT touched, per the brief.
- **Checked `model/report_generator.py` (Step 12e) for the same risk, as
  requested:** confirmed it's NOT affected. It only ever inserts numbers
  via f-string formatting (`f"{value:.2f}"`, `f"{credit_score} / 900"`)
  or explicit `float()` casts — both use Python's `str()`/`format()`
  protocol, which already renders numpy scalars as clean numbers (e.g.
  `"600000.0"`), never `repr()`'s `"np.float64(600000.0)"` text. Verified
  this distinction directly in the real venv (numpy 2.4.6) before
  concluding it's a non-issue there.
- **Verified the fix two ways, without touching the real Postgres
  database:**
  1. A synthetic test feeding `create_company_and_assessment()` dicts
     built entirely of numpy scalars (including nested ones inside
     `shap_top_drivers`) — confirmed every stored ORM attribute is a
     native Python type afterward, and that re-assessing the same
     company still works correctly post-fix.
  2. The REAL production path: `POST /api/v1/evaluate` through
     `TestClient` against a throwaway in-memory SQLite database (not the
     real one) — confirmed the actually-stored `net_cash_margin`,
     `cash_buffer_ratio`, `bounce_count_last_6m` and `credit_score`
     values are all native Python `float`/`int`, not numpy types.

### Files created/changed
- `backend/crud.py`: added `_to_native()`; `create_company_and_assessment()`
  now sanitizes both input dicts before building ORM objects.
- `model/scoring.py`, `model/preprocessing.py`: confirmed untouched, per
  the brief.

### Decisions made
- Sanitized at the `crud.py` boundary rather than at each source
  (`model/scoring.py`, `model/preprocessing.py`, `backend/main.py`'s
  `_build_feature_row()`) because this is the ONE place every current
  and future database write already passes through — fixing it here
  protects every caller automatically, including ones written later,
  instead of requiring the same fix to be remembered and repeated at
  every place a number happens to originate.
- `_to_native()` is recursive (walks dicts/lists) specifically because
  `shap_top_drivers` is itself a nested structure containing numbers
  that needed the exact same fix — a shallow, top-level-only sanitizer
  would have missed that.
- Did not add sanitization to `save_fairness_audit_batch()`: traced
  `model/fairness.py`'s `compute_dir_audit()` and confirmed its computed
  values (`group_approval_rate`, `dir_value`, etc.) are built from plain
  Python `sum()`/`len()` arithmetic on Python `bool`/`int` values, never
  numpy arrays — so there's no equivalent risk there today. `_to_native()`
  itself remains available as a general, reusable helper if that ever
  changes.

### Next step
- User re-tests `POST /api/v1/evaluate` against the real PostgreSQL
  database to confirm the fix resolves the original error, then Step 12b:
  React/Next.js dashboard rewrite.

---

## 2026-10-09 — Step 12e: Downloadable PDF credit-assessment report

### Completed
- Added `reportlab` to `requirements.txt` and installed it locally to
  verify the code below actually works (a declared dependency, not part
  of "don't run the deliverable" — the server/endpoint itself was not
  started; see verification notes below).
- Created `model/report_generator.py`'s `generate_pdf_report(company_data,
  score_result, explanation_result)`: builds a one-page PDF entirely in a
  `BytesIO` buffer (never a temp file) — header (title, company name/ID,
  assessment date), a colored risk-band badge + large credit score +
  default probability %, a horizontal-bar visualization of the top 5
  positive and top 5 negative SHAP drivers (bar length scaled by
  `|SHAP value|`, relative across both sections so they're visually
  comparable) with one plain-English sentence per driver, and a footer
  disclaimer (synthetic data, student project, not a real lending
  decision) + page number. Input shapes deliberately mirror
  `score_company()`'s/`explain_company()`'s own return dicts, so
  `backend/main.py` doesn't need to reshape anything.
- **Reused, not redefined**, `dashboard/components/charts.py`'s
  `FEATURE_LABELS`/`feature_label()` and `RISK_BAND_COLORS` (that module
  is pure Python with no Streamlit import, so importing it from
  `model/report_generator.py` is safe) — correcting the brief's framing
  slightly: the lookup actually lives in `dashboard/components/charts.py`,
  not `dashboard/app.py`, which only *uses* it.
- Added `GET /api/v1/company/{company_id}/report/pdf` to
  `backend/main.py`: reuses `crud.get_company_with_history()` (the same
  query the existing history endpoint uses, not duplicated) to find the
  company's most recent assessment (`.assessments[0]`, already sorted
  newest-first), 404s if the company doesn't exist or has no assessments,
  and returns the PDF via `StreamingResponse` with a
  `Content-Disposition: attachment; filename="credit_report_<id>.pdf"`
  header.
- Added a "Download PDF Report" button to `dashboard/app.py`'s Tab 1,
  appearing once an evaluation exists: fetches the PDF via the new
  endpoint and caches the bytes in `st.session_state`, keyed by
  **(company_id, assessed_at)** — not company_id alone — so re-assessing
  the same company correctly fetches a fresh PDF instead of silently
  reusing a stale cached one from an earlier assessment.
- **Verified thoroughly, without starting the real server:**
  - Generated real test PDFs with realistic fake data (including edge
    cases: empty driver lists, missing `assessed_at`, all 3 risk bands)
    and confirmed valid `%PDF-`/`%%EOF` byte structure each time.
  - **Visually inspected a rendered test PDF and found 2 real layout
    bugs** before handing off: the large score text crowded the default
    -probability line below it, and the single-line footer disclaimer
    collided with the right-aligned page number. Fixed both (more
    vertical spacing; disclaimer wrapped onto 2 lines) and re-verified
    visually — clean layout confirmed.
  - Ran a full round trip through FastAPI's `TestClient` against a
    throwaway in-memory database (not the real Postgres one):
    `POST /evaluate` → real `score_company()`/`explain_company()` →
    `GET /report/pdf` → 200, correct `Content-Type`/
    `Content-Disposition` headers, valid PDF bytes; a nonexistent
    company correctly 404s. Confirmed `backend.main` still imports
    cleanly with all 5 routes (including the new one) registered.
  - Test PDF files and the one-off test script were deleted afterward;
    nothing was written to the real database or any permanent file.

### Files created/changed
- `requirements.txt`: added `reportlab`.
- `model/report_generator.py`: created.
- `backend/main.py`: added the `GET .../report/pdf` endpoint + import.
- `dashboard/app.py`: added `fetch_pdf_report()`, the `pdf_report_cache`
  session-state entry, and the download button in Tab 1.
- `model/scoring.py`, `model/explainer.py`, `model/calibration.py`:
  confirmed untouched — only their existing functions' outputs are
  consumed, per the brief.

### Decisions made
- Used reportlab's low-level `canvas.Canvas` (direct x/y drawing) rather
  than its `platypus` flowable-document API, since the layout is a fixed,
  simple one-page design, not a multi-page flowing document — simpler to
  reason about for this use case.
- PDF caching in the dashboard keys on `(company_id, assessed_at)`
  specifically to avoid a real correctness bug: keying on `company_id`
  alone would silently serve a stale PDF after a re-assessment, since the
  same company can be scored again with a new `assessed_at`.

### Next step
- User restarts the API (`uvicorn backend.main:app --reload`) and
  dashboard (`streamlit run dashboard/app.py`), evaluates a company, and
  tests the "Download PDF Report" button and/or the endpoint directly via
  curl. Then Step 12b: React/Next.js dashboard rewrite.

---

## 2026-10-09 — Step 10b (live run): Migration confirmed working against real PostgreSQL

### Completed
- **Successfully migrated from SQLite to PostgreSQL for real** — the
  `msme_credit` database on `localhost:5432` (the code/wiring itself was
  built in the previous entry below).
- Verified via the startup log showing the **masked Postgres connection
  string** (not the SQLite fallback warning), confirming
  `backend/database.py` correctly picked up the real `DATABASE_URL` from
  `.env`.
- Ran `scripts/init_db.py` against the new Postgres database: it
  successfully seeded 20 companies with their calibrated scores —
  **score range 609-861, 13 Low Risk / 7 Medium Risk** — consistent with
  Step 12c's post-calibration distribution (no High Risk companies in
  this particular sample, which is plausible given calibration shifted
  the overall distribution toward Low Risk).
- `data/processed/msme_credit.db` (the SQLite file) was kept untouched as
  a backup/reference and is no longer used going forward — all reads/
  writes now go through the real Postgres database.

### Files created/changed
- `.env`: real password set locally by the user (git-ignored, never seen
  by the assistant).

### Next step
- Step 12e: PDF report generator.

---

## 2026-10-09 — Step 10b: PostgreSQL migration

### Completed
- Added `psycopg2-binary` to `requirements.txt` (confirmed `python-dotenv`
  was already there from Step 1, and both packages were already present
  in the venv).
- Created `.env` (git-ignored — confirmed `.env` was already in
  `.gitignore` from Step 1, no change needed) with a placeholder password,
  and `.env.example` (committed, same content, visible placeholder) so a
  teammate knows which variable to set without ever seeing a real
  password.
- Rewrote `backend/database.py`: loads `DATABASE_URL` from `.env` via
  `python-dotenv`; if unset, prints a clear warning and falls back to the
  original SQLite file (`data/processed/msme_credit.db`) instead of
  crashing; prints exactly which database is in use at import time, with
  the password masked via regex either way. No other logic changed —
  `Base`, `get_db()`, and every ORM model/crud function/endpoint are
  untouched and work identically against either database.
- **Found and fixed a real version-specific bug while verifying (not
  something the brief anticipated):** this environment's installed
  SQLAlchemy (2.1.3) resolves a *bare* `postgresql://` URL to the newer
  `psycopg` (v3) dialect by default, not `psycopg2` — even though
  `psycopg2-binary` is what's actually installed and what the brief
  specifies. Importing with a bare URL failed with
  `ModuleNotFoundError: No module named 'psycopg'`. Fixed by making the
  driver explicit in both `.env` and `.env.example`:
  `postgresql+psycopg2://...` instead of `postgresql://...` — confirmed
  this resolves to the `psycopg2` dialect correctly afterward.
- **Verified both branches without running anything or touching the real
  database:** with `.env` present, `backend.database` imports cleanly,
  prints the masked Postgres URL, and `engine.dialect` correctly reports
  `postgresql`/`psycopg2` (engine construction only — SQLAlchemy doesn't
  actually connect until a query runs, and none was run, so no real
  Postgres server was needed for this check). With `.env` temporarily
  renamed away (simulating a teammate who hasn't set theirs up) and
  restored immediately after, the SQLite fallback branch triggered
  correctly with its warning message and the right file path. Confirmed
  the real `data/processed/msme_credit.db`'s file size/timestamp
  unchanged throughout, and that `backend.main` (all 4 existing
  endpoints, including Step 12d's fairness one) still imports and
  registers its routes correctly against the new `database.py`.

### Files created/changed
- `requirements.txt`: added `psycopg2-binary`.
- `.env`: created (git-ignored, placeholder password).
- `.env.example`: created (committed template).
- `backend/database.py`: rewritten per the brief above.
- `CLAUDE.md`: tech stack + current step + upgrade sequence updated.

### Decisions made
- Used `postgresql+psycopg2://` (explicit driver) rather than bare
  `postgresql://` in both env files, specifically to avoid the dialect
  -resolution bug found above — flagged as a "found, not assumed" issue
  since the original brief's example URL used the bare form.
- Password masking uses a small regex (`_mask_password()`) rather than a
  third-party library, since the one thing it needs to hide is simple and
  consistent (everything between the first `:` after `://` and the next
  `@`).
- `scripts/init_db.py` was deliberately left untouched — per the brief,
  old SQLite data is not auto-migrated; re-running that script against
  the new Postgres connection (once configured) reseeds it fresh, and the
  SQLite file remains as an untouched backup/reference.

### Next step
- User installs/starts a local PostgreSQL server, creates the
  `msme_credit` database, sets their real password in `.env`, then runs
  `python scripts/init_db.py` to seed the new Postgres database fresh.
  Then Step 12e: PDF report generator.

---

## 2026-10-09 — Step 12d (live run): Fairness/DIR audit against real seeded data

### Completed
- Ran `GET /api/v1/analytics/fairness` for real against the 21 seeded
  assessments in `data/processed/msme_credit.db` (the mechanism itself —
  `model/fairness.py`'s `compute_dir_audit()`, the `FairnessAuditLog`
  table, the endpoint — was added per the literature review's Gap 4; see
  the previous entry below for the implementation).
- **Live results:**
  - **Flagged:** `state='Punjab'`, DIR = 0.741 (vs. reference
    `Maharashtra`), actual default rate **0.0%** (n=6, 6/6 known
    outcomes).
  - **Flagged:** `business_category='trading'`, DIR = 0.794 (vs.
    reference `retail`), actual default rate **0.0%** (n=15, 15/15 known
    outcomes).
  - **Excluded** 6 cohorts for `n < 5` (too small to audit reliably):
    Tamil Nadu (3), Bihar (3), Andhra Pradesh (3), Telangana (3),
    Rajasthan (1), food (3).

### Decisions made / limitations noted for the final report
- **Sample size limitation:** both flagged cohorts (n=6, n=15) are too
  small to distinguish genuine model bias from ordinary sampling noise.
  The audit mechanism is confirmed working correctly end-to-end — it
  correctly pairs each DIR with its cohort's actual default rate per the
  paper's Sect 3.5.2 methodology, never reporting DIR alone — but drawing
  real fairness conclusions from these specific numbers would need a
  production-scale dataset with hundreds of assessments per cohort, which
  this 21-company seeded database does not provide. This run validates
  the *mechanism*, not a fairness conclusion about the model itself.
- **Reaffirmed interpretation caveat:** `state`/`business_category` are
  behavioural/circumstantial proxies, not protected characteristics —
  this synthetic dataset contains no gender, religion or caste data at
  all. This audit shows whether the model penalizes risk-relevant cohort
  differences, not protected-attribute discrimination directly.

### Next step
- Proceed to Step 10b: PostgreSQL migration. Re-run this fairness audit
  periodically as more assessments accumulate, since both flags above are
  provisional pending a larger sample.

---

## 2026-10-09 — Step 12d: Fairness auditing (Disparate Impact Ratio)

### Completed
- Added `FairnessAuditLog` to `backend/db_models.py`: a periodic
  AGGREGATE snapshot table (no foreign key to Assessment/Company — a row
  describes a whole cohort at one moment, not one scoring event). Fields:
  `id`, `computed_at`, `cohort_dimension`, `cohort_value`,
  `reference_dimension_value`, `group_approval_rate`,
  `reference_approval_rate`, `dir_value` (nullable), plus
  `group_actual_default_rate` (nullable), `cohort_size`,
  `cohort_size_with_known_outcome` (added beyond the literal spec,
  to make the known-vs-unknown-ground-truth distinction explicit in the
  schema itself, not just the printed output), `flagged_low_dir`.
- Created `model/fairness.py`'s `compute_dir_audit(db)`: groups
  assessments by `state` and `business_category` (via `Company`),
  picks each dimension's largest cohort as the reference group, computes
  DIR (`group_approval_rate / reference_approval_rate`, "approve" =
  NOT High Risk) for every other eligible cohort, flags any DIR < 0.80,
  and ALWAYS prints the cohort's actual default rate alongside a flag
  (never DIR alone), per the literature review's Sect 3.5.2 methodology.
  Cohorts below `MIN_COHORT_SIZE` (5) are excluded and reported
  separately, not scored.
- **Ground truth recovery**: since Assessment rows store predictions,
  not outcomes, `load_ground_truth_lookup()` rebuilds a feature
  "fingerprint" (every banking/GST/digital value, NaN/None-normalized,
  rounded to 6dp) for every `data/processed/test.csv` row and matches
  each Assessment back to it. A match (companies seeded by
  `scripts/init_db.py`, whose feature values were copied unchanged from
  test.csv) recovers a real `credit_default_status`; no match (e.g. a
  company scored live via the API) means "ground truth unknown" —
  excluded from `group_actual_default_rate` but still counted in
  `group_approval_rate`/DIR, exactly as specified.
- Added `backend/crud.py` functions: `get_all_assessments()` (factored
  out of `get_portfolio_stats()`'s existing query so both it and the new
  fairness code share one query — "reuse existing patterns, don't
  duplicate SQL"), `save_fairness_audit_batch()`,
  `get_latest_fairness_audit()`.
- Added `GET /api/v1/analytics/fairness` to `backend/main.py`: triggers a
  fresh (uncached) `compute_dir_audit()` run, returns each eligible
  cohort's DIR/default rate/flag/size plus the list of excluded small
  cohorts. Added `FairnessCohortAudit`/`ExcludedCohort`/
  `FairnessAuditResponse` to `backend/schemas.py`.
- **The literature review's caveat is stated explicitly** as the top
  comment in `model/fairness.py` (and echoed in `FairnessAuditLog`'s
  docstring): `state`/`business_category` are risk-relevant
  behaviours/circumstances, not protected characteristics like gender or
  religion (which this synthetic dataset doesn't contain) — a flagged
  cohort is a prompt to check its actual default rate, not proof of
  discrimination by itself.
- **Verified end-to-end on a throwaway in-memory database** (never the
  real `data/processed/msme_credit.db`, confirmed unchanged afterward):
  built 3 states × 2 categories of fake companies with varying risk
  bands, including one real `test.csv` row (with a known default) seeded
  in as an Assessment to test ground-truth matching. Result matched
  expectations exactly: `Bihar` correctly flagged (DIR 0.190 vs.
  reference `Maharashtra`) with its real 100% actual default rate shown
  alongside (1 of 6 assessments had a known outcome); `Delhi` (n=3) and
  `services` (n=3) correctly excluded as too small. Also confirmed via a
  separate check that Pydantic's `from_attributes` correctly converts a
  list of ORM-like objects into `FairnessCohortAudit` instances inside
  the nested `FairnessAuditResponse`. `backend.main` imports cleanly with
  the new route registered.

### Files created/changed
- `backend/db_models.py`: added `FairnessAuditLog`.
- `backend/crud.py`: added `get_all_assessments()`,
  `save_fairness_audit_batch()`, `get_latest_fairness_audit()`;
  `get_portfolio_stats()` refactored to reuse `get_all_assessments()`.
- `model/fairness.py`: created.
- `backend/schemas.py`: added `FairnessCohortAudit`, `ExcludedCohort`,
  `FairnessAuditResponse`.
- `backend/main.py`: added `GET /api/v1/analytics/fairness`.
- `CLAUDE.md`: current step + upgrade sequence updated.
- `model/scoring.py`, `model/explainer.py`, `model/calibration.py`:
  confirmed untouched (hashed before/after) — not part of this step, per
  the brief.

### Decisions made
- "Reference group" is re-picked fresh on every audit run (the current
  largest cohort), not fixed — it can change over time as more companies
  get assessed, and `reference_dimension_value` records which one was
  used for each specific snapshot.
- The reference cohort itself is never scored against itself (no DIR=1.0
  row) — only "every OTHER cohort in that dimension" gets a row, per the
  brief.
- `compute_dir_audit()`'s `min_cohort_size` defaults to 5 (not 1), so the
  function is sensibly safe to call standalone without the caller having
  to remember to pass a threshold; the API endpoint relies on that
  default rather than re-specifying it.

### Next step
- User restarts the API server (`uvicorn backend.main:app --reload`) —
  its existing `lifespan` startup hook calls `Base.metadata.create_all()`,
  which will create the new `fairness_audit_logs` table automatically,
  no manual migration needed. Then exercise
  `GET /api/v1/analytics/fairness` against the real seeded data, review
  any flagged cohorts' actual default rates, and proceed to Step 10b:
  PostgreSQL migration.

---

## 2026-10-09 — Step 12c (conclusion): Calibration adopted; skew confirmed real, not a bug

### Completed
- **Final calibration result:** isotonic regression vs. Platt (sigmoid)
  scaling were fit on the same 5-fold out-of-fold training probabilities
  and compared on the held-out test set. **Platt won** (test Brier
  0.1119 vs. isotonic's 0.1125) and was adopted.
- **Root problem confirmed:** Step 7's `class_weight="balanced"` model
  produced badly miscalibrated raw probabilities — e.g. the 50-60%
  predicted bucket had only a 20.8% actual observed default rate, a
  large overstatement. This is exactly what calibration is for, and
  Platt scaling fixed it.
- **Investigated the skewed risk-band distribution** that calibration
  produced (76.9% Low Risk, vs. Step 8's original 8.2%) using the
  diagnostic script from the previous entry
  (`model/calibrate_experiment.py`, since deleted — its job was done):
  retrained the identical model **without** `class_weight="balanced"`
  and compared its raw probabilities against both balanced options.
  **Result: the unweighted model's raw probabilities showed nearly
  identical skew (78.8% Low Risk)**, with equally strong reliability
  numbers (predicted probability closely tracked actual observed default
  rate in every well-populated bucket). This rules out class balancing as
  the cause of the skew.
- **Conclusion: the skew is correct, not a bug.** The test set's true
  default rate is 14.8% — 85.2% of companies genuinely do not default —
  so a well-calibrated model correctly assigns most companies to Low
  Risk. **Step 8's original distribution (58.9% Medium, 32.9% High) was
  the actually wrong one**, inflated by `class_weight="balanced"`'s
  probability distortion; calibration has now corrected it. Risk-band
  boundaries and `probability_to_score()` (Step 8) are unchanged — they
  now simply operate on honest, calibrated probabilities instead of
  distorted ones.

### Files created/changed
- `model/artifacts/calibrator.joblib`: final artifact — Platt (sigmoid)
  scaling, applied in `model/scoring.py`'s `score_company()` before the
  credit-score formula.
- `model/artifacts/model.joblib`: **unchanged** — still Step 7's balanced
  model, still the single plain Logistic Regression `model/explainer.py`'s
  SHAP explainer needs.
- `model/calibrate_experiment.py`: deleted (diagnostic script; its
  conclusion is recorded here, the script itself was disposable).

### Decisions made
- Chose Platt over isotonic purely on test-set Brier score (0.1119 vs.
  0.1125), consistent with `model/calibrate.py`'s selection rule (lower
  Brier wins unless absurdly skewed relative to the other candidate —
  here neither was, so the better Brier score decided it).
- Did **not** revisit `class_weight="balanced"` in `model/tune.py` after
  the diagnostic ruled it out as the cause of the skew — no further
  action needed there.
- The large risk-band shift from Step 8 (58.9%/32.9% Medium/High) to now
  (76.9% Low Risk) is a **feature of fixing the probabilities**, not a
  regression: it reflects the dataset's true ~15% default rate rather
  than class-weighting's inflated one.

### Next step
- Step 13: tests (`tests/test_api.py`, `tests/test_predictor.py`,
  `tests/test_scoring.py`), now against the final, calibrated
  `score_company()` output.

---

## 2026-10-09 — Step 12c (diagnostic): is class_weight="balanced" the real root cause?

### Completed
- Both isotonic and Platt calibration (previous entries) turned out
  absurdly skewed on the real run (76-80% "Low Risk" either way) — two
  different calibration methods failing the same way on the same raw
  probabilities points at the probabilities themselves, not the
  calibration method.
- Created `model/calibrate_experiment.py` (new, read-only diagnostic
  script — not executed by the assistant, the user will run it):
  trains **only** a Logistic Regression with the exact same Optuna
  -found `C` from `best_params.json`, but **without**
  `class_weight="balanced"`, on the same training data, then compares
  its raw probabilities against Step 7's balanced model (raw AND
  Platt-calibrated) on Brier score, ROC-AUC, risk-band distribution, and
  the same 10-bucket reliability table.
- Reused `model/calibrate.py`'s own
  `build_calibration_model_template()`/`get_out_of_fold_probabilities()`/
  `fit_platt_calibrator()`/`evaluate_probabilities()`/
  `build_reliability_table()` directly rather than reimplementing any of
  them — the Platt column is refit fresh inside this script (not read
  from the possibly-isotonic `calibrator.joblib` currently on disk), so
  the comparison is self-contained and trustworthy regardless of which
  calibrator last won.
- Ends with an explicit, criteria-based recommendation (adopt / adopt
  with caveat / don't adopt) based on: is the unweighted model's largest
  risk band ≤ 60%, is its Brier score at least as good as the better of
  the two balanced options, and is its ROC-AUC within ±0.03 of the ~0.74
  this project has seen throughout.
- **Verified without running the real experiment:** syntax-checked the
  file; confirmed it imports cleanly with `main()` not invoked; hashed
  `model/tune.py`, `model/calibrate.py`, `model/artifacts/model.joblib`,
  `best_params.json`, and `calibrator.joblib` before and after import —
  all 5 hashes identical, confirming nothing was touched; separately
  verified the lightweight helper functions directly (`load_best_c()`
  returns the real Optuna `C`; `build_unweighted_logistic_regression()`
  produces a Pipeline with `class_weight=None`) without fitting any
  model or running the actual experiment.

### Files created/changed
- `model/calibrate_experiment.py`: created. No other file touched —
  `model/tune.py` and all existing artifacts are untouched by design.

### Decisions made
- Deliberately did NOT reuse `model.tune.build_trial_model()` for the
  unweighted model (its Logistic Regression branch hardcodes
  `class_weight="balanced"`) — built the Pipeline directly instead,
  mirroring the same imputer→scaler→LogisticRegression shape, with the
  same `C`, differing only in the one parameter under test.
- This script never calls `joblib.dump()` or writes to
  `model/artifacts/` at all — intentionally a pure diagnostic with no
  side effects, so running it carries zero risk to the working pipeline.

### Next step
- **User runs `python model/calibrate_experiment.py`** and reviews the
  printed recommendation. If it recommends adopting the unweighted
  approach, the suggested follow-up (a separate, future decision) is to
  re-run `model/tune.py`'s Optuna search without
  `class_weight="balanced"` and reassess whether calibration is still
  needed at all.

---

## 2026-10-09 — Step 12c (bug fix): PlattCalibrator pickling location

### Completed
- **Bug found by the user:** `PlattCalibrator` (added in the previous
  entry below) was defined inside `model/calibrate.py`, the script run
  directly via `python model/calibrate.py`. joblib/pickle records a
  class's location as the module it was defined in at save time — when a
  script is run directly, that module is `__main__`, not
  `model.calibrate`. So a `calibrator.joblib` saved that way would fail
  to load from any OTHER script (e.g. `scripts/init_db.py`, the API) with
  `AttributeError: Can't get attribute 'PlattCalibrator' on <module
  '__main__'>`.
- **Fix:** moved the `PlattCalibrator` class definition into
  `model/calibration.py` — the one module every caller (`score_company()`,
  `calibrate.py` itself, and anything that later loads `calibrator.joblib`)
  already imports normally (never runs directly as `__main__`) — and
  updated `model/calibrate.py` to `from model.calibration import
  PlattCalibrator` instead of defining it locally. This makes the pickled
  class always resolve to the stable path `model.calibration.PlattCalibrator`,
  regardless of which script loads the file later.
- **Verified without running the real script:** confirmed
  `model.calibrate.PlattCalibrator is model.calibration.PlattCalibrator`
  (the exact same class object via the import); then reproduced the bug
  scenario directly — fit a `PlattCalibrator` on fake data in one Python
  process, `joblib.dump()` it, confirmed it pickled under
  `model.calibration` (not `__main__`), then loaded it back in a
  **completely separate, fresh process** and called `.predict()`
  successfully. Deleted the temp file afterward; the real
  `calibrator.joblib` was not touched.

### Files created/changed
- `model/calibration.py`: `PlattCalibrator` class added (moved from
  `model/calibrate.py`); docstrings updated to reflect its new home.
- `model/calibrate.py`: `PlattCalibrator` definition removed; now imports
  it from `model.calibration` instead. No other logic changed.
- `CLAUDE.md`: current step updated.

### Decisions made
- No change needed to `apply_calibration()`'s own logic — it already
  only calls `.predict()` generically, so moving the class didn't require
  touching that function, only where the class lives.

### Next step
- **User re-runs `python model/calibrate.py` once more** to regenerate
  `calibrator.joblib` with the corrected, stable class location (same
  isotonic-vs-Platt comparison and auto-selection as before — only the
  pickling bug is different). Then confirm `scripts/init_db.py` and/or the
  API can load it successfully, and proceed to Step 13: tests.

---

## 2026-10-09 — Step 12c (continued): Isotonic vs. Platt calibration comparison

### Completed
- The first calibration pass (isotonic regression alone, previous entry
  below) was run and found genuinely problematic: **79.9% of the test set
  landed in "Low Risk"** (up from 8.2% raw), with several reliability
  buckets having only 0-2 training rows — isotonic regression's flexible,
  step-wise curve overfitting the limited (~4,000-row) training set.
- Rewrote `model/calibrate.py` to fit **both** isotonic regression and
  **Platt/sigmoid scaling** on the exact same out-of-fold training
  probabilities (same `cross_val_predict` call as before, now feeding
  two separate `.fit()` calls instead of one):
  - Added `PlattCalibrator`: a thin wrapper around a plain 1-feature
    `LogisticRegression` (the standard manual Platt-scaling
    implementation — fits only a slope + intercept, 2 numbers total vs.
    isotonic's many "knots"), exposing the same `.predict()` interface as
    `IsotonicRegression` so `model/calibration.py` can treat whichever
    one wins identically.
  - `evaluate_probabilities()` and `build_reliability_table()` now
    compute Brier score / the 10-bucket reliability table / the risk-band
    distribution for **Raw, Isotonic, and Platt side by side** (not just
    before/after).
  - Added `select_winning_calibrator()`: picks the lower-test-set-Brier
    candidate between Isotonic/Platt, **unless** that candidate's
    risk-band distribution is absurdly skewed (> 70% in one band) while
    the other isn't — in which case the non-skewed one wins instead,
    with the reasoning printed either way (including the "both skewed"
    edge case, printed as an explicit warning rather than silently
    picking one).
  - `model/calibration.py`'s docstrings updated to say "whichever
    calibrator won" instead of assuming isotonic specifically; its
    `apply_calibration()` logic itself needed no code changes, since
    both calibrators expose the same `.predict()` interface.
- **Verified without running the real script:** syntax-checked all 3
  touched files; confirmed `model.calibrate` still imports cleanly
  (module-level only, `main()` not invoked); functionally tested
  `PlattCalibrator` end-to-end on throwaway fake data in an isolated
  script — fit, joblib pickle/round-trip, and `.predict()` all correct,
  producing a sensible monotonic curve comparable to isotonic's — then
  deleted the temp file. The real `model/artifacts/calibrator.joblib`
  (already present from the first isotonic-only run) was not touched by
  any of these checks.

### Files created/changed
- `model/calibrate.py`: substantially rewritten (fits + evaluates + picks
  between 2 calibrators instead of 1; added `PlattCalibrator`,
  `evaluate_probabilities()`, `select_winning_calibrator()`; generalized
  `build_reliability_table()`/`print_calibration_report()` to 3-way).
- `model/calibration.py`: docstring/comment wording updated only (no
  logic change — already calibrator-agnostic).
- `CLAUDE.md`: current step updated.

### Decisions made
- Selection rule implemented as "lower Brier wins, UNLESS it's absurdly
  skewed and the other candidate isn't" (not a strict two-condition AND
  that could leave no winner) — reflects that a usable risk-band spread
  matters more than a marginal Brier improvement for this project's
  purpose, while still defaulting to the better Brier score when both
  are reasonable.
- Kept Raw in the printed comparison/warning check (even though it was
  never a save candidate) purely for context, since seeing how far raw
  probabilities drift makes the calibrated numbers easier to sanity-check.

### Next step
- **User re-runs `python model/calibrate.py`** with the new 3-way
  comparison, reviews which calibrator won (Isotonic or Platt) and the
  printed reasoning, confirms the resulting risk-band distribution looks
  reasonable, then proceeds to Step 13: tests.

---

## 2026-10-09 — Step 12c: Probability calibration (isotonic regression)

### Completed
- Created `model/calibrate.py` (one-time fitting + evaluation script,
  written and reviewed — including a bootstrapping-order bug found and
  fixed before handing it over — not executed by the assistant; the user
  will run it manually):
  - Backs up the pre-calibration `model.joblib` + `best_params.json` to
    `model/artifacts/pre_calibration/` (idempotent, same pattern as Step
    7's `baseline_step6/` backup).
  - Rebuilds an unfitted model of the **exact same type + hyperparameters**
    as the real tuned model by replaying `best_params.json` through
    `model.tune.build_trial_model()` directly (reused, not retyped).
  - Gets out-of-fold probabilities via `sklearn.model_selection.
    cross_val_predict` (5-fold stratified, training set only — no
    leakage), fits `sklearn.isotonic.IsotonicRegression(out_of_bounds=
    "clip")` on (OOF probability, true label), and saves it to
    `model/artifacts/calibrator.joblib`. **`model.joblib` itself is never
    modified.**
  - Evaluates on the test set (touched once): Brier score before/after,
    a 10-bucket reliability table (mean predicted vs. actual rate, raw
    and calibrated side by side), and the Low/Medium/High risk-band
    distribution shift between raw and calibrated probabilities.
- Created `model/calibration.py`: the lightweight, reusable
  `apply_calibration()` — loads `calibrator.joblib` **lazily** (on first
  call, then cached) rather than at import time, specifically so
  `model/calibrate.py` can import `model/scoring.py`'s pure helper
  functions on its very first run, before `calibrator.joblib` exists yet
  (an eager load would have made that first run impossible — caught and
  fixed via an isolated import check before this was handed over).
- Updated `model/scoring.py`'s `score_company()` — the **only** change
  made there, per the brief — to call `apply_calibration()` on the raw
  model probability before `probability_to_score()`. Docstring updated to
  explain why, and to note that `model/explainer.py`'s SHAP explanations
  deliberately keep explaining the base model's raw, uncalibrated
  decision function.
- **Verified via isolated import checks** (not running `calibrate.py`
  itself): `model.scoring`, `model.explainer`, and `model.calibrate` all
  import cleanly with `calibrator.joblib` absent (confirming the lazy-load
  fix); `apply_calibration()` raises a clear, actionable
  `FileNotFoundError` naming the exact command to run first, rather than
  a confusing failure somewhere downstream.

### Files created/changed
- `model/calibrate.py`: created.
- `model/calibration.py`: created.
- `model/scoring.py`: `score_company()` updated (import + 2-line change +
  docstring); no other function touched.
- `CLAUDE.md`: current step updated, with an explicit note about the new
  `calibrator.joblib` dependency.

### Decisions made
- Did NOT use `sklearn.calibration.CalibratedClassifierCV` (per the
  brief): it would wrap the base model in an internal CV-fold ensemble,
  no longer a single plain `LogisticRegression` with stable coefficients
  — breaking `model/explainer.py`'s `shap.LinearExplainer`, which needs
  exactly that. Built the same idea by hand instead, as two fully
  separate artifacts (`model.joblib` unchanged; `calibrator.joblib` new).
- SHAP continues explaining the **base, uncalibrated** model — this is
  correct, not an oversight: SHAP explains *why the base model ranked a
  company the way it did*; calibration is a separate, monotonic rescaling
  applied afterward that doesn't change that ranking or reasoning.
- `model/calibration.py` loads `calibrator.joblib` lazily rather than
  eagerly (unlike `model/scoring.py`'s/`model/explainer.py`'s eager
  `_MODEL`/`_EXPLAINER` loads) — a deliberate, documented exception to
  that pattern, needed to break the chicken-and-egg import order on
  `calibrate.py`'s first-ever run.

### Next step
- **User runs `python model/calibrate.py` once** (this is now required
  before `score_company()` works again anywhere — API, dashboard,
  `scripts/init_db.py` — since it now calls `apply_calibration()`, which
  needs `calibrator.joblib` to exist). Review the printed Brier
  score/reliability table/risk-band shift, then proceed to Step 13: tests.

---

## 2026-10-09 — Step 12: Streamlit dashboard

### Completed
- Created `dashboard/components/charts.py`: 3 pure Plotly chart builders
  (no Streamlit/API/model code) — `build_score_gauge()` (300-900
  gauge colored by the 3 risk-band zones, black threshold line as the
  "needle"), `build_shap_driver_chart()` (tornado-style horizontal bars,
  positive SHAP values red/right, negative green/left), and
  `build_portfolio_pie_chart()` (risk-band donut chart). Also defines
  `FEATURE_LABELS`/`feature_label()`, a single shared lookup so the chart
  axis labels and the dashboard's plain-English sentences always show the
  same human-readable names.
- Created `dashboard/app.py`: calls the Step 11 API **only over HTTP**
  (via `requests`) — no `model`/`backend` imports, exactly like a real
  separate frontend. Wide layout, sidebar input form covering every
  `MSMEInput` field (dropdowns for category/state, checkboxes for the two
  booleans, sliders/number inputs with ranges from
  `docs/data_dictionary.md` elsewhere), and 3 main tabs:
  - **Credit Scorecard**: gauge + colored risk-band badge + probability,
    populated from the last `POST /evaluate` result.
  - **Why this score? (Explainability)**: the tornado chart plus each
    driver restated as a plain-English sentence (e.g. "Bounced Payments
    (last 6 months) = 7.00 increased risk").
  - **Portfolio Overview**: `GET /analytics/portfolio` fetched
    automatically on first render (not button-triggered), cached in
    `st.session_state`, with a manual Refresh button for later updates.
  - Unreachable API / non-200 responses are caught and shown via
    `st.error()` with the exact command to start the backend, instead of
    crashing the app.
- `st.session_state` holds `last_evaluation` and `portfolio_data` so both
  survive Streamlit's full-script rerun on every interaction (otherwise
  switching tabs would make the scorecard disappear).
- Verified the 3 chart-building functions directly with realistic sample
  data (figures built without error, correct bar/pie values, label
  lookup working with a sensible fallback for unknown features) — the
  full Streamlit app itself was not run by the assistant, per
  instructions; the user will run it manually in a second terminal.
- Added the missing `dashboard/__init__.py` and a `sys.path` fix at the
  top of `app.py` (matching the pattern already used in
  `model/train.py`/`scripts/init_db.py`), since `streamlit run
  dashboard/app.py` puts `dashboard/` itself on `sys.path`, not the
  project root, which would otherwise break the
  `dashboard.components.charts` import.

### Files created/changed
- `dashboard/components/charts.py`: created.
- `dashboard/app.py`: created.
- `dashboard/__init__.py`: created.
- `CLAUDE.md`: current step updated.

### Decisions made
- `business_category`/`state` dropdown options and per-field
  slider/number-input ranges are hardcoded in `app.py` (matching
  `docs/data_dictionary.md`), rather than imported from
  `model/artifacts/category_encodings.json` — Step 12's design explicitly
  keeps the dashboard decoupled from backend/model code, so this list
  must be kept in sync by hand if those files ever change; flagged in
  comments at both definitions.
- Portfolio data fetches automatically once per session (page load) and
  then only on manual Refresh, rather than on every script rerun —
  avoids an API call on every unrelated sidebar interaction while still
  satisfying "on page load, not button-triggered."

### Next step
- User starts both servers manually in two terminals
  (`uvicorn backend.main:app --reload`, then
  `streamlit run dashboard/app.py`), exercises the dashboard end-to-end,
  then Step 13: tests (`tests/test_api.py`, `tests/test_predictor.py`,
  `tests/test_scoring.py`).

---

## 2026-10-09 — Step 11: FastAPI backend

### Completed
- Created `backend/schemas.py`: Pydantic v2 models.
  - `MSMEInput` mirrors the RAW synthetic data's shape (not the fully
    -preprocessed `FEATURE_COLUMNS` shape): callers submit human-readable
    `business_category`/`state` strings and raw bank/GST/digital numbers,
    never the internal encoded columns or the 3 derived ratios (those are
    computed server-side — see Decisions below). Field bounds are strict
    where mathematically true (ratios 0-1, scores 0-100, counts ≥ 0) and
    loose (non-negative only) where they're just "what our synthetic
    sample happened to cover" (rupee amounts). Added 2 cross-field
    validators beyond the user's literal examples: GST fields must be
    all-present/all-null in lockstep with `has_gst_registration`, and
    `account_vintage_months <= age_of_business_years * 12` (same rule
    Step 4's EDA checked).
  - `EvaluateResponse`, `AssessmentRecord`/`CompanyHistoryResponse`,
    `PortfolioAnalyticsResponse`.
- Created `backend/crud.py`: plain functions (no FastAPI code) —
  `create_company_and_assessment()` (insert-or-reuse Company + always-new
  Assessment), `get_company_with_history()` (404-ready `None` return,
  history sorted newest-first in Python without touching
  `backend/db_models.py`'s relationship config), `get_portfolio_stats()`
  (counts/percentages/average score across every assessment).
- Created `backend/main.py`: `POST /api/v1/evaluate`, `GET
  /api/v1/company/{company_id}` (proper 404), `GET
  /api/v1/analytics/portfolio`, `GET /health`, CORS for any
  localhost/127.0.0.1 origin+port, and a `lifespan` startup hook that
  creates DB tables if missing (model + SHAP explainer loading already
  happens once at import time, inside `model/scoring.py`/
  `model/explainer.py` — the lifespan hook's docstring explains this
  explicitly rather than pretending otherwise).
  - `score_company()`/`explain_company()` reused unmodified; a new
    `_build_feature_row()` helper encodes category/state via the saved
    `category_encodings.json` and computes the 3 derived ratios by
    calling `model.preprocessing.add_derived_ratios()` directly (no
    formula retyped a third time).
- **Verified end-to-end with FastAPI's `TestClient` against a throwaway
  in-memory SQLite database** (dependency-overridden; the real
  `data/processed/msme_credit.db` was never touched — confirmed unchanged
  file size/timestamp afterward): `/health` 200; `POST /evaluate` 200 with
  real probability/score/SHAP output; `GET /company/{id}` 200 with correct
  history; `GET /company/<missing>` 404; `GET /analytics/portfolio` 200
  with correct aggregates; re-assessing the same `company_id` grew its
  history to 2 assessments (not 2 companies); invalid `business_category`,
  mismatched GST fields, and `account_vintage_months > age*12` each
  correctly returned 422. The server itself was not started by the
  assistant — the user will start it manually.

### Files created/changed
- `backend/schemas.py`: created.
- `backend/crud.py`: created.
- `backend/main.py`: created.
- `CLAUDE.md`: current step updated.

### Decisions made
- **Deliberate deviation from a literal reading of the request:**
  `MSMEInput` excludes not just the encoded category columns (as
  explicitly asked) but also the 3 derived ratio columns
  (`net_cash_margin`, `cash_buffer_ratio`, `gst_to_bank_turnover_ratio`),
  even though they're technically part of `FEATURE_COLUMNS` too. Asking
  callers to submit both raw inflow/outflow AND a separately-computed
  ratio would let a request contradict itself (ratio not matching the raw
  numbers); computing it server-side with the exact same
  `model.preprocessing.add_derived_ratios()` function removes that
  entirely. Flagged here per the "explain changes in plain language"
  rule in case this wasn't the intent.
- `PortfolioAnalyticsResponse` counts every assessment, not just distinct
  companies (`total_companies` is reported separately) — a company
  re-assessed twice can land in a different risk band each time, so
  collapsing to one row per company would hide real history.
- Used `fastapi.testclient.TestClient` + a dependency-overridden in-memory
  DB (not the real one) to verify all 3 endpoints and all 3 custom
  validators actually work, without starting a real server or writing
  test data into the real seeded database.

### Next step
- User starts the server manually
  (`venv\Scripts\python.exe -m uvicorn backend.main:app --reload`) and
  exercises it via `http://127.0.0.1:8000/docs`, then Step 12: the
  Streamlit dashboard (`dashboard/app.py`) calling this API.

---

## 2026-10-09 — Step 10: Database layer (SQLAlchemy + SQLite)

### Completed
- Created `backend/database.py`: SQLite engine pointed at
  `data/processed/msme_credit.db` (confirmed `*.db` is already in
  `.gitignore` from Step 1 — nothing new needed there), a shared
  `Base` declarative class, and `get_db()`, the FastAPI yield-pattern
  dependency Step 11's endpoints will use.
- Created `backend/db_models.py` with two ORM models:
  - `Company`: static profile (`company_id` PK, `company_name`,
    firmographics — age/business_category/state/employee_count —
    `created_at`).
  - `Assessment`: one scoring event (`assessment_id` PK autoincrement, FK
    to `company_id`, `assessed_at`, the full banking/GST/digital feature
    snapshot, `default_probability`/`credit_score`/`risk_band`, and
    `shap_top_drivers` as JSON). One Company → many Assessments.
- Created `scripts/init_db.py` (new top-level folder): creates both tables
  via `Base.metadata.create_all()`, samples 20 rows from
  `data/processed/test.csv`, runs each through Step 8's `score_company()`
  and Step 9's `explain_company()` unmodified, and inserts a Company +
  Assessment row per row. Re-running it adds new Assessment rows to the
  same 20 Companies rather than erroring or duplicating companies —
  demonstrating the one-to-many "re-assessment history" design.
- Verified the ORM wiring end-to-end (table creation, insert, foreign key,
  relationship traversal both directions) on a **throwaway in-memory
  SQLite database** — the real `data/processed/msme_credit.db` was never
  touched by the assistant; `scripts/init_db.py` itself was not run.
- Updated `CLAUDE.md`'s folder layout to mention the new `scripts/` folder,
  and its current step.

### Files created/changed
- `backend/database.py`: created.
- `backend/db_models.py`: created.
- `scripts/init_db.py`: created.
- `CLAUDE.md`: folder layout + current step updated.

### Decisions made
- **Important caveat documented in `scripts/init_db.py`:** `test.csv` has
  no `company_id`/`company_name` (dropped before training on purpose) and
  was saved without the original row index, so the 20 seeded companies'
  IDs/names are clearly-labelled placeholders (`MSME-SEED-0001`, "Seed
  Company 0001"), not real dataset IDs. `business_category`/`state`
  **are** recovered exactly, though, by inverting
  `model/artifacts/category_encodings.json`'s saved mapping — every
  banking/GST/digital number and the model's actual probability/score/
  SHAP explanation are real, only the name tag is a placeholder.
  Firmographics (`age_of_business_years`, `business_category`, `state`,
  `employee_count`) were kept on `Company` even though `age_of_business_
  years` technically also drifts over time, per the explicit Company/
  Assessment split requested.
- Used SQLite's native `JSON` column type for `shap_top_drivers` rather
  than a separate contributors table, since it's always read/written as
  one self-contained blob per assessment, not queried column-by-column.
- `check_same_thread=False` on the SQLite engine, since FastAPI can serve
  a request's `get_db()` dependency on a different thread than the one
  that created the engine; each request still gets its own `Session`.

### Next step
- Run `scripts/init_db.py` to actually seed the database, confirm the 20
  companies/assessments look right, then Step 11: the FastAPI backend
  (`backend/main.py`, `backend/schemas.py`, `backend/crud.py`) exposing
  `score_company()`/`explain_company()` and the company assessment-history
  endpoint over this database.

---

## 2026-10-09 — Step 9: SHAP explanations (global + local)

### Completed
- Created `model/explainer.py` (written and reviewed — including isolated,
  deleted scratch checks confirming the SHAP API calls and the
  reconstruction math against the real model/data — not executed by the
  assistant; the user ran it manually to see the example explanations).
- Used `shap.LinearExplainer` (not `TreeExplainer`) since the winning Step
  7 model is Logistic Regression — a linear model, so SHAP values are
  exact/closed-form rather than approximated. `build_shap_explainer()` is
  structured with a type-based branch so a future tree-model winner would
  activate a `TreeExplainer` branch automatically, with no other code
  changes needed.
- **Global SHAP importance (top 7 by mean |SHAP value|):**
  `bounce_count_last_6m` (0.2794), `age_of_business_years` (0.1733),
  `account_vintage_months` (0.1712), `net_cash_margin` (0.1639),
  `gst_filing_regularity_score` (0.1425), `has_gst_registration` (0.1417),
  `cash_flow_volatility` (0.1189).
- Saved `docs/images/shap_global_importance.png` (bar),
  `docs/images/shap_summary_beeswarm.png` (importance + direction), and
  `docs/images/shap_waterfall_example.png` (one example company).
- `explain_company()`: the function Step 11 (API) and Step 12 (dashboard)
  will call directly, returning top-5 positive/negative SHAP contributors
  per company in a JSON-serializable dict.
- **Local explanations confirmed intuitive:** riskiest companies driven up
  mainly by `bounce_count_last_6m` (SHAP +1.73, +1.48) and negative
  `net_cash_margin`; safest companies driven down by long
  `account_vintage_months` and high `gst_filing_regularity_score`.
- **Sanity check:** all 4 local explanations' (sum of SHAP values + base
  value) exactly reconstructed the model's raw output, diff ~1e-16
  (floating-point noise) — confirms the explainer is wired correctly.
- **Validation of Step 5's engineered features:** the derived ratio
  `net_cash_margin` (#4) far outranks the raw `avg_monthly_inflow` /
  `avg_monthly_outflow` it's built from (both bottom-3) — confirms the
  engineered ratio adds real value over the raw columns it was derived
  from, not just redundant information.

### Files created/changed
- `model/explainer.py`: created.
- `docs/images/shap_global_importance.png`,
  `docs/images/shap_summary_beeswarm.png`,
  `docs/images/shap_waterfall_example.png`: created.

### Decisions made
- SHAP values are computed in log-odds space (the linear model's raw
  output), matching what `LinearExplainer` naturally explains; probability
  and score are derived separately via `model/scoring.py` for display.
- **Limitation noted for the final report:** `state_encoded` ranks #8
  (0.0748) and `business_category_encoded` ranks #11 — both higher than
  `docs/data_dictionary.md`'s design intent of a "very small effect" for
  `state`. Likely cause: Step 5's label/ordinal encoding was chosen
  reasoning about tree models (which split on thresholds regardless of
  code value), but Logistic Regression — a linear model — won instead;
  linear models treat an encoded integer as a real magnitude, so an
  arbitrary alphabetical category ordering can manufacture spurious
  importance that wouldn't exist with one-hot encoding. Documented as a
  fairness/methodology discussion point; not fixed in-pipeline at this
  stage (would require revisiting Step 5's encoding choice specifically
  for linear models, e.g. one-hot or target encoding, if addressed later).

### Next step
- Step 10: write `model/evaluate.py` (or equivalent) consolidating final
  model evaluation/reporting, then Step 11: backend API
  (`backend/main.py`) exposing `score_company()` and `explain_company()`.

---

## 2026-10-09 — Step 8: Credit score (300-900) + risk band conversion

### Completed
- Created `model/scoring.py` (written and reviewed, not executed by the
  assistant — the user ran it manually).
- `probability_to_score()`: a 3-segment piecewise-linear mapping from
  default probability to a 300-900 score, calibrated to hit the exact
  CLAUDE.md boundaries: 900 → 750 over p = 0.00-0.20, 750 → 600 over
  p = 0.20-0.50, 600 → 300 over p = 0.50-1.00. All breakpoints are read
  from `model/config.py`'s `RISK_BANDS`, not re-typed as separate numbers.
- `assign_risk_band()`: Low Risk (750+) / Medium Risk (600-749) / High Risk
  (<600), matching CLAUDE.md exactly.
- `score_company()`: the single function that will back the Step 11 API —
  takes one company (dict/Series/single-row DataFrame), runs the tuned
  model, and returns `{default_probability, credit_score, risk_band}`.
- **Risk band distribution on the test set:** Low Risk 8.2% (82), Medium
  Risk 58.9% (589), High Risk 32.9% (329).
- **Sanity check vs. Step 7's 0.5 threshold:** risk-band-derived metrics
  (Precision 0.2948, Recall 0.6554, F1 0.4067) closely match Step 7's
  (Precision 0.2982, Recall 0.6689, F1 0.4125) — confusion matrices
  `[[620,232],[51,97]]` vs. `[[619,233],[49,99]]` differ by only 2
  companies right at the p=0.50/score=600 boundary. Confirms the
  probability-to-score formula is mathematically consistent with the
  tuned model's actual behavior, not a disconnected piece of logic.
- **Example companies spot-checked:** two 22-26yr old, zero-bounce,
  high-GST-compliance companies scored 862-870 (Low Risk); a thinner-margin
  3.7yr company scored 643 (Medium Risk); two ~3yr companies with 7-8
  bounces and negative cash margin scored 342-343 (High Risk) and both had
  actually defaulted — scoring behaves sensibly on real examples.

### Files created/changed
- `model/scoring.py`: created.

### Decisions made
- Used piecewise-linear (3 segments) rather than a single linear or
  logit-based formula, since no single straight line can pass through all
  4 required points (0→900, 0.20→750, 0.50→600, 1→300) — verified
  algebraically in the module docstring, not just eyeballed.
- "High Risk" is defined as `score < 600` (strict), which is mathematically
  equivalent to `probability > 0.50` (strict) under this formula — matches
  Step 7's `probability >= 0.50` cutoff everywhere except the
  essentially-never-hit exact boundary p == 0.50.
- `score_company()`'s input/output shapes were deliberately kept simple
  (plain dict/Series/DataFrame in, plain dict out) now, specifically so
  Step 11's backend API can call it with minimal glue code.

### Next step
- Step 9: SHAP explanations for individual predictions (which features
  pushed a company's score up or down), using the tuned model from
  `model/artifacts/model.joblib`.

---

## 2026-10-09 — Step 7: Class-imbalance fix + Optuna hyperparameter tuning

### Completed
- Created `model/tune.py` (written and reviewed, not executed by the
  assistant — the user ran it manually to watch Optuna's trials live).
- Backed up Step 6's original `model.joblib` and `model_metrics.json` to
  `model/artifacts/baseline_step6/` before anything was overwritten.
- **Stage 1 — balanced, untuned models**, scored with 5-fold stratified CV
  on the training set only (`class_weight="balanced"` for Logistic
  Regression/Random Forest, `scale_pos_weight` for XGBoost/LightGBM):

  | Model | CV ROC-AUC | CV PR-AUC | CV Recall (default) |
  |---|---|---|---|
  | **Logistic Regression (winner)** | **0.7382** | 0.3781 | 0.6300 |
  | Random Forest | 0.7136 | — | 0.2922 |
  | LightGBM | 0.6941 | — | 0.3311 |
  | XGBoost | 0.6692 | — | 0.2601 |

  Logistic Regression won by CV ROC-AUC alone, per the model selection rule
  — the held-out test set was not used for this decision.
- **Stage 2 — Optuna tuning** of Logistic Regression: 50 trials, 5-fold CV
  on the training set only, optimizing CV ROC-AUC. Best: `C = 0.00603`,
  best CV ROC-AUC = 0.7410.
- **Final tuned model, evaluated ONCE on the held-out test set**
  (threshold = 0.5, provisional — Step 8 sets this properly):
  - ROC-AUC 0.7437, PR-AUC 0.3501, Recall (default) 0.6689, F1 0.4125,
    KS 0.4004
  - Confusion matrix `[[TN, FP], [FN, TP]]`: `[[619, 233], [49, 99]]`
- **3-way comparison vs. Step 6 baseline** (ROC-AUC 0.7443, Recall 0.1014,
  unbalanced/untuned Logistic Regression): adding `class_weight="balanced"`
  improved recall roughly **6.6x (10% → 67%)**, with ROC-AUC essentially
  unchanged (0.7443 → 0.7437) and precision trading down, as expected when
  deliberately shifting the decision boundary to catch more defaulters.
- Saved the tuned model to `model/artifacts/model.joblib`, best
  hyperparameters to `model/artifacts/best_params.json`, and full
  before/after metrics to `model/artifacts/model_metrics.json`.

### Files created/changed
- `model/tune.py`: created.
- `model/artifacts/baseline_step6/model.joblib`,
  `model/artifacts/baseline_step6/model_metrics.json`: Step 6 backup.
- `model/artifacts/model.joblib`: overwritten with the Step 7 tuned model.
- `model/artifacts/best_params.json`: created.
- `model/artifacts/model_metrics.json`: overwritten with Step 6 + Step 7
  metrics combined.

### Decisions made
- Model type and all hyperparameters were selected using only
  cross-validation ROC-AUC on the training set; the test set was touched
  exactly once, at the end, purely for final reporting.
- **Discussion point for the final report:** Logistic Regression won model
  selection in both Step 6 and Step 7, ahead of all 3 tree ensembles. This
  likely isn't a tree-model weakness — `docs/data_dictionary.md` section 5
  states the synthetic default labels were generated by passing a hidden
  risk score through a **logistic (sigmoid) function**. A linear model
  recovering a logistic-shaped relationship well is expected, and is a sign
  Logistic Regression matches the data's true generating structure here,
  not that it's intrinsically a better credit model. A real-world dataset
  with messier, more nonlinear risk patterns might favor the tree models
  instead.
- Threshold of 0.5 used only for reporting the final tuned model's
  Recall/F1/confusion matrix — explicitly provisional, pending Step 8's
  score/risk-band design.

### Next step
- Step 8: convert predicted default probabilities into the 300-900 credit
  score and Low/Medium/High risk bands (per `CLAUDE.md`'s fixed bands),
  choosing the real classification threshold(s) deliberately as part of
  that design — then SHAP explanations.

---

## 2026-10-09 — Step 6: Baseline model training (script written, not yet run)

### Completed
- Created `model/train.py`: loads `data/processed/train.csv`/`test.csv`
  using `FEATURE_COLUMNS`/`TARGET_COLUMN` from `model/config.py` (no
  hardcoded column names), trains 4 baseline classifiers (Logistic
  Regression, Random Forest, XGBoost, LightGBM), evaluates each on the test
  set, prints a comparison table sorted by ROC-AUC, and saves the best
  model + all models' metrics.
- Logistic Regression and Random Forest are wrapped in a scikit-learn
  `Pipeline` with a median `SimpleImputer` (fit on train only, applied to
  test -- no leakage) since neither handles NaN natively; XGBoost and
  LightGBM train directly on the raw data with the GST NaNs intact.
- Evaluation uses ROC-AUC, precision/recall/F1 for the default class, a
  confusion matrix, and the KS (Kolmogorov-Smirnov) statistic -- explained
  in a module docstring why these fit an ~15%-default imbalanced target
  better than plain accuracy.
- LightGBM import is wrapped in a try/except: if not installed, the script
  warns and skips it instead of crashing, so the other 3 models still run.
  (LightGBM was not installed in this environment as of writing.)
- Per the user's request, the script was only written and reviewed line by
  line -- **not executed**. The user will run it manually.

### Files created/changed
- `model/train.py`: created.

### Decisions made
- Imputation lives inside a `Pipeline` (not a standalone preprocessing
  step) specifically so `.fit`/`.predict` can't leak test-set information
  into the training-set medians.
- Kept all 4 models at standard default parameters (e.g. `n_estimators=100`)
  intentionally -- hyperparameter tuning is Step 7, not this step.
- Best model is selected by test-set ROC-AUC and saved to
  `model/artifacts/model.joblib`; all 4 models' metrics are saved to
  `model/artifacts/model_metrics.json` for later reference/comparison.

### Next step
- Run `python model/train.py` (optionally `pip install lightgbm` first so
  all 4 models are compared), confirm ROC-AUC lands in the expected
  ~0.75-0.85 range, then move to Step 7: hyperparameter tuning with Optuna.

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
