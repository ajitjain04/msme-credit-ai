"""
Step 12e — Downloadable one-page PDF credit-assessment report, per the
literature review's Fig 10 / Sect 6.6 ("a downloadable PDF credit
-assessment report... reminiscent of the borrower-facing explanation in
[5]").

This module does NOT call the model, run SHAP, or touch the database --
it only takes numbers that score_company() (model/scoring.py) and
explain_company() (model/explainer.py) already produced, and draws them
onto a PDF page with the `reportlab` library. backend/main.py's new
endpoint is the only caller that actually runs those two functions; this
module just renders whatever it's handed.

WHY THIS REUSES dashboard/components/charts.py's FEATURE_LABELS/
feature_label() and RISK_BAND_COLORS
----------------------------------------------------------------------------
The Streamlit dashboard already has one canonical "raw feature name ->
human-readable label" lookup (used for its SHAP driver chart's axis labels
AND its plain-English sentences in Tab 2) and one canonical "risk band ->
color" mapping (used by its gauge, badge and pie chart). Both already live
in dashboard/components/charts.py as plain, Streamlit-free functions/dicts
-- importing them here means the PDF report always shows the exact same
feature names and colors as the dashboard, with zero risk of the two
drifting apart from two separately-maintained copies.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.charts import RISK_BAND_COLORS, feature_label  # noqa: E402

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 50
TOP_DRIVERS_SHOWN = 5

CATEGORY_ENCODINGS_PATH = PROJECT_ROOT / "model" / "artifacts" / "category_encodings.json"
with open(CATEGORY_ENCODINGS_PATH) as _f:
    # The EXACT {category_name: code} mapping model/preprocessing.py used
    # to encode business_category/state when building the training data
    # (the same file backend/schemas.py uses for request validation) --
    # loaded once here and inverted below, so this report decodes these
    # two features with the one canonical mapping, never a second,
    # separately-maintained copy.
    _CATEGORY_ENCODINGS: dict[str, dict[str, int]] = json.load(_f)

# {raw_feature_name: {code: category_name}}. SHAP explains the model's
# OWN inputs, which are these 2 encoded integer columns (see
# docs/data_dictionary.md / model/preprocessing.py) -- meaningful to the
# model, but meaningless to a report reader on their own ("2.00" says
# nothing). Only these 2 features need this treatment: every other
# feature in model.config.FEATURE_COLUMNS is already a real, directly
# -meaningful number (a rupee amount, a ratio, a count, a 0/1 flag) that
# doesn't need translating.
_ENCODED_FEATURE_DECODERS: dict[str, dict[int, str]] = {
    "business_category_encoded": {
        code: name for name, code in _CATEGORY_ENCODINGS["business_category"].items()
    },
    "state_encoded": {code: name for name, code in _CATEGORY_ENCODINGS["state"].items()},
}

# These 4 features are the ONLY ones that can ever be missing (None),
# and only for the SAME reason every time: the company has no GST
# registration (Step 5's design -- see docs/data_dictionary.md section
# 3: the 3 raw GST columns are intentionally left empty for an
# unregistered company, and gst_to_bank_turnover_ratio is derived FROM
# annual_turnover_gst, so it's missing for the identical reason). Reusing
# has_gst_registration's existing meaning here, rather than inventing a
# new "why is this missing" concept, is exactly why a bare "missing" check
# can safely map to this one specific message below.
_GST_NULLABLE_FEATURES = {
    "gst_filing_regularity_score",
    "annual_turnover_gst",
    "gst_filing_delay_days_avg",
    "gst_to_bank_turnover_ratio",
}


def format_driver_value(feature_name: str, value: Optional[float]) -> str:
    """Formats one driver's raw value for display.

    business_category_encoded/state_encoded are decoded back to their
    real category name (e.g. "retail", "Maharashtra") via
    model/artifacts/category_encodings.json -- see
    _ENCODED_FEATURE_DECODERS above. Every other feature is shown as a
    plain number, exactly as before.

    MISSING VALUES (value is None): model/explainer.py's
    _safe_feature_value() returns None instead of raising when a
    feature's raw value was genuinely missing -- in practice only the 4
    GST-related features in _GST_NULLABLE_FEATURES above, for a
    GST-unregistered company. Rather than show a crash or a literal
    "None"/"nan", this returns a message that tells a reader WHY the
    value is missing, reusing has_gst_registration's existing meaning
    instead of inventing new logic.

    Fallback: if an encoded value somehow isn't in the lookup (shouldn't
    happen in practice -- the model only ever produces codes it was
    trained on, and category_encodings.json is the exact mapping that
    produced them), this falls back to showing the raw number rather than
    crashing the report -- a wrong-looking number is a far smaller problem
    than a report that fails to generate at all.

    PUBLIC on purpose (no leading underscore): backend/main.py imports
    this directly to compute ShapDriver.display_value for the live API
    (consumed by the React dashboard and the old Streamlit dashboard),
    so there is exactly ONE place that knows how to turn an encoded
    business_category_encoded/state_encoded value back into a real name
    -- this module's PDF rendering and the API's JSON responses both call
    into this same function instead of maintaining two copies of the
    same decoding logic.
    """
    if value is None:
        if feature_name in _GST_NULLABLE_FEATURES:
            return "Not available (GST not registered)"
        return "Not available"

    decoder = _ENCODED_FEATURE_DECODERS.get(feature_name)
    if decoder is not None:
        code = int(round(value))
        if code in decoder:
            return decoder[code]
    return f"{value:.2f}"

DISCLAIMER_LINES = (
    "This report was generated by a machine learning model trained on SYNTHETIC data for a "
    "student project.",
    "It is NOT a real credit decision and must not be used for actual lending purposes.",
)


def _format_timestamp(value: Any) -> str:
    """Formats a datetime (or an already-string timestamp, or nothing) for
    display in the report header."""
    if value is None:
        value = datetime.utcnow()
    if isinstance(value, str):
        return value
    return value.strftime("%d %b %Y, %H:%M UTC")


def _driver_sentence(label: str, value_display: str, increases_risk: bool) -> str:
    """One plain-English sentence per driver, e.g. 'Bounced Payments (last
    6 months): 7.00 -- this increased the assessed risk', or (for an
    encoded category feature, already decoded by _format_driver_value())
    'Business Category: retail -- this increased the assessed risk'."""
    direction = "increased" if increases_risk else "decreased"
    return f"{label}: {value_display} -- this {direction} the assessed risk"


def _draw_driver_section(
    c: canvas.Canvas,
    title: str,
    drivers: list[dict[str, Any]],
    bar_color_hex: str,
    y: float,
    max_abs_shap: float,
) -> float:
    """Draws one section (either the 'increasing risk' or 'decreasing
    risk' group): a heading, then up to TOP_DRIVERS_SHOWN rows, each a
    label, a horizontal bar sized by |SHAP value| relative to the biggest
    SHAP value on the whole page (so the two sections are visually
    comparable), and a one-line plain-English sentence. Returns the y
    position to continue drawing from."""
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, title)
    y -= 18

    label_column_width = 190
    bar_x = MARGIN + label_column_width
    max_bar_width = PAGE_WIDTH - MARGIN - bar_x

    if not drivers:
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(MARGIN, y, "(none in the top drivers)")
        return y - 16

    for driver in drivers[:TOP_DRIVERS_SHOWN]:
        feature_name = driver["feature"]
        label = feature_label(feature_name)
        # Deliberately NOT float(driver["value"]) -- that crashes when a
        # GST-unregistered company's driver value is None (see
        # model/explainer.py's _safe_feature_value()). Pass it through
        # as-is; format_driver_value() is the one place that knows how
        # to handle None safely.
        value = driver["value"]
        shap_value = float(driver["shap_value"])
        value_display = format_driver_value(feature_name, value)

        c.setFillColor(black)
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN, y, label)

        bar_len = (abs(shap_value) / max_abs_shap * max_bar_width) if max_abs_shap > 0 else 0.0
        c.setFillColor(HexColor(bar_color_hex))
        c.rect(bar_x, y - 2, bar_len, 9, fill=1, stroke=0)
        y -= 13

        c.setFillColor(black)
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(MARGIN, y, _driver_sentence(label, value_display, increases_risk=shap_value > 0))
        y -= 16

    return y


def generate_pdf_report(
    company_data: dict[str, Any],
    score_result: dict[str, Any],
    explanation_result: dict[str, Any],
) -> BytesIO:
    """Builds a one-page PDF credit-assessment report and returns it as an
    in-memory BytesIO buffer (never written to a temp file -- see
    backend/main.py's new endpoint for why that matters: it can stream
    straight from memory to the HTTP response).

    Expected inputs (deliberately matching model.scoring.score_company()'s
    and model.explainer.explain_company()'s OWN return shapes, so callers
    don't need to reshape anything -- see those functions' docstrings):

        company_data = {
            "company_id": str,
            "company_name": str,
            "assessed_at": datetime | str | None,   # optional; defaults to "now"
        }
        score_result = {
            "default_probability": float,   # 0-1
            "credit_score": int,            # 300-900
            "risk_band": "Low Risk" | "Medium Risk" | "High Risk",
        }
        explanation_result = {
            "top_positive_contributors": [{"feature": str, "value": float, "shap_value": float}, ...],
            "top_negative_contributors": [...],
        }
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    y = PAGE_HEIGHT - MARGIN

    # --- Header --------------------------------------------------------
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, y, "MSME Alternative Credit Assessment Report")
    y -= 26

    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, y, str(company_data.get("company_name", "Unknown Company")))
    y -= 16

    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, y, f"Company ID: {company_data.get('company_id', 'N/A')}")
    y -= 13
    c.drawString(MARGIN, y, f"Assessment Date: {_format_timestamp(company_data.get('assessed_at'))}")
    y -= 20

    c.setStrokeColor(HexColor("#cccccc"))
    c.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    y -= 28

    # --- Risk band badge + credit score + default probability ---------
    risk_band = score_result["risk_band"]
    badge_color_hex = RISK_BAND_COLORS.get(risk_band, "#999999")
    badge_width, badge_height = 150, 32

    c.setFillColor(HexColor(badge_color_hex))
    c.roundRect(MARGIN, y - badge_height, badge_width, badge_height, 6, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(MARGIN + badge_width / 2, y - badge_height / 2 - 5, risk_band)

    score_x = MARGIN + badge_width + 30
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(score_x, y - 20, f"{score_result['credit_score']} / 900")

    c.setFont("Helvetica", 11)
    probability_pct = score_result["default_probability"] * 100
    c.drawString(score_x, y - badge_height - 8, f"Default Probability: {probability_pct:.1f}%")

    y -= badge_height + 32
    c.setStrokeColor(HexColor("#cccccc"))
    c.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    y -= 26

    # --- SHAP drivers ----------------------------------------------------
    positive_drivers = explanation_result.get("top_positive_contributors", [])
    negative_drivers = explanation_result.get("top_negative_contributors", [])
    all_shap_values = [abs(float(d["shap_value"])) for d in positive_drivers + negative_drivers]
    max_abs_shap = max(all_shap_values) if all_shap_values else 1.0

    y = _draw_driver_section(
        c, "Top Factors Increasing Risk", positive_drivers, RISK_BAND_COLORS["High Risk"], y, max_abs_shap
    )
    y -= 10
    y = _draw_driver_section(
        c, "Top Factors Decreasing Risk", negative_drivers, RISK_BAND_COLORS["Low Risk"], y, max_abs_shap
    )

    # --- Footer: disclaimer (wrapped across 2 lines so it never collides
    # with the page number) + page number, on its own line, right-aligned.
    #
    # Positioned with its LOWEST text baseline at y=44 -- comfortably
    # above the ~36pt hardware margin most printers refuse to print
    # inside, so the footer can't get silently clipped if this report is
    # ever printed on paper, not just viewed on screen. Also bumped from
    # 7pt light gray to 8pt darker gray: confirmed via pypdf that the
    # footer text was always technically present in the PDF (not actually
    # missing or off-page), but small + low-contrast + close to the edge
    # is an easy combination to overlook at a glance.
    c.setStrokeColor(HexColor("#cccccc"))
    c.line(MARGIN, 66, PAGE_WIDTH - MARGIN, 66)
    c.setFillColor(HexColor("#444444"))
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(MARGIN, 54, DISCLAIMER_LINES[0])
    c.drawString(MARGIN, 44, DISCLAIMER_LINES[1])
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_WIDTH - MARGIN, 44, "Page 1 of 1")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
