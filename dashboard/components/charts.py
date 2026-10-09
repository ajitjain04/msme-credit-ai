"""
Step 12 — Reusable Plotly chart builders for the Streamlit dashboard.

Pure functions only: each one takes plain Python values (numbers, lists of
dicts) and returns a Plotly Figure. No Streamlit calls, no API calls, no
model/backend imports live here -- dashboard/app.py wires these together
with data it already fetched from the FastAPI backend over HTTP.
"""

from __future__ import annotations

import plotly.graph_objects as go

# Standard risk-band colors, shared by the gauge, the pie chart and
# dashboard/app.py's colored risk-band badge, so all three always agree.
RISK_BAND_COLORS = {
    "Low Risk": "#2ecc71",  # green
    "Medium Risk": "#f1c40f",  # yellow
    "High Risk": "#e74c3c",  # red
}

# Human-readable labels for model.config.FEATURE_COLUMNS, used both on the
# SHAP driver chart's axis labels and in dashboard/app.py's plain-English
# driver sentences -- defined once here so both always show the same text.
# NOTE: the dashboard talks to the API only (no backend/model imports per
# Step 12's design), so this list is maintained by hand and should be kept
# in sync with model/config.py's FEATURE_COLUMNS if that list ever changes.
FEATURE_LABELS: dict[str, str] = {
    "age_of_business_years": "Business Age (years)",
    "business_category_encoded": "Business Category",
    "state_encoded": "State",
    "employee_count": "Employee Count",
    "avg_monthly_inflow": "Avg. Monthly Inflow (₹)",
    "avg_monthly_outflow": "Avg. Monthly Outflow (₹)",
    "min_ending_balance_avg": "Avg. Minimum Bank Balance (₹)",
    "bounce_count_last_6m": "Bounced Payments (last 6 months)",
    "account_vintage_months": "Bank Account Age (months)",
    "cash_flow_volatility": "Cash Flow Volatility",
    "has_gst_registration": "GST Registered",
    "gst_filing_regularity_score": "GST Filing Regularity Score",
    "annual_turnover_gst": "Annual GST Turnover (₹)",
    "gst_filing_delay_days_avg": "Avg. GST Filing Delay (days)",
    "upi_transaction_volume_ratio": "UPI Transaction Share",
    "pos_terminal_active_status": "POS Terminal Active",
    "digital_payment_adoption_score": "Digital Payment Adoption Score",
    "net_cash_margin": "Net Cash Margin",
    "cash_buffer_ratio": "Cash Buffer Ratio",
    "gst_to_bank_turnover_ratio": "GST-to-Bank Turnover Ratio",
}


def feature_label(feature_name: str) -> str:
    """Human-readable label for a raw feature column name, falling back to
    a title-cased version of the name itself if it's not in the lookup
    (e.g. a feature added later that this dict hasn't caught up with)."""
    return FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ").title())


def build_score_gauge(score: int) -> go.Figure:
    """A 300-900 gauge/speedometer chart, colored by the 3 risk-band zones
    (CLAUDE.md's fixed boundaries: red below 600, yellow 600-749, green
    750+), with a black threshold line marking the current score -- the
    "needle" pointing at where this company landed."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"font": {"size": 48}},
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [300, 900], "tickwidth": 1, "dtick": 100},
                "bar": {"color": "rgba(31, 41, 55, 0.85)", "thickness": 0.25},
                "bgcolor": "white",
                "borderwidth": 1,
                "bordercolor": "lightgray",
                "steps": [
                    {"range": [300, 600], "color": RISK_BAND_COLORS["High Risk"]},
                    {"range": [600, 750], "color": RISK_BAND_COLORS["Medium Risk"]},
                    {"range": [750, 900], "color": RISK_BAND_COLORS["Low Risk"]},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 4},
                    "thickness": 0.9,
                    "value": score,
                },
            },
        )
    )
    fig.update_layout(height=320, margin=dict(t=30, b=10, l=30, r=30))
    return fig


def build_shap_driver_chart(
    top_positive_drivers: list[dict], top_negative_drivers: list[dict]
) -> go.Figure:
    """A horizontal tornado-style bar chart combining both driver lists
    (each a list of {"feature", "value", "shap_value"} dicts, matching
    backend/schemas.py's ShapDriver shape): positive SHAP values (risk UP)
    extend right in red, negative SHAP values (risk DOWN) extend left in
    green, sorted so the chart reads safest-at-top to riskiest-at-bottom.
    """
    rows = [
        {"label": feature_label(d["feature"]), "shap_value": d["shap_value"]}
        for d in list(top_positive_drivers) + list(top_negative_drivers)
    ]
    rows.sort(key=lambda r: r["shap_value"])

    labels = [r["label"] for r in rows]
    values = [r["shap_value"] for r in rows]
    colors = [
        RISK_BAND_COLORS["High Risk"] if v > 0 else RISK_BAND_COLORS["Low Risk"]
        for v in values
    ]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.3f}" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="What's driving this score? (SHAP values, log-odds)",
        xaxis_title="← Lowers risk (safer)          Raises risk (riskier) →",
        height=max(320, 42 * len(labels) + 80),
        margin=dict(l=10, r=10, t=60, b=50),
    )
    fig.add_vline(x=0, line_width=1, line_color="gray")
    return fig


def build_portfolio_pie_chart(low_count: int, medium_count: int, high_count: int) -> go.Figure:
    """A donut chart of the 3 risk bands, using the same colors everywhere
    else in the dashboard uses them."""
    labels = ["Low Risk", "Medium Risk", "High Risk"]
    values = [low_count, medium_count, high_count]
    colors = [RISK_BAND_COLORS[label] for label in labels]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker=dict(colors=colors),
            textinfo="label+percent",
        )
    )
    fig.update_layout(
        title="Portfolio Risk Band Distribution",
        height=400,
        margin=dict(t=60, b=10, l=10, r=10),
    )
    return fig
