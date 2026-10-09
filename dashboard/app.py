"""
Step 12 — Streamlit dashboard.

This app talks to the FastAPI backend (Step 11) ONLY over HTTP, using the
`requests` library -- it does NOT import model/ or backend/ code directly.
That's deliberate: it's exactly how a real separate frontend would work,
and it means this dashboard and the API can be deployed/run completely
independently (which is also why you run them in two separate terminals).

How to run (in a SECOND terminal -- the API must already be running in a
FIRST terminal, see the bottom of this docstring):
    venv\\Scripts\\python.exe -m streamlit run dashboard/app.py

The API itself is started with:
    venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests
import streamlit as st

# `streamlit run dashboard/app.py` executes this file with its OWN
# directory (dashboard/) on sys.path, not the project root -- so
# `import dashboard.components...` would otherwise fail. This makes the
# project root importable regardless of how/where this script is launched
# from, the same defensive pattern used in model/train.py, scripts/
# init_db.py, etc.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.charts import (  # noqa: E402
    RISK_BAND_COLORS,
    build_portfolio_pie_chart,
    build_score_gauge,
    build_shap_driver_chart,
    feature_label,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL = "http://localhost:8000"
EVALUATE_URL = f"{API_BASE_URL}/api/v1/evaluate"
PORTFOLIO_URL = f"{API_BASE_URL}/api/v1/analytics/portfolio"

# Mirrors docs/data_dictionary.md section 1's category list. The dashboard
# doesn't import backend/schemas.py directly (see module docstring), so
# this list is maintained by hand -- keep it in sync with
# model/artifacts/category_encodings.json's "business_category" keys if
# that ever changes.
BUSINESS_CATEGORIES = ["retail", "trading", "services", "manufacturing", "food"]

# Mirrors docs/data_dictionary.md section 1's state list (and
# model/artifacts/category_encodings.json's "state" keys) -- same
# maintained-by-hand caveat as above.
STATES = [
    "Andhra Pradesh", "Bihar", "Delhi", "Gujarat", "Haryana", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Punjab", "Rajasthan",
    "Tamil Nadu", "Telangana", "Uttar Pradesh", "West Bengal",
]

st.set_page_config(
    page_title="MSME Alternative Credit Assessment",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# st.session_state setup
# ---------------------------------------------------------------------------
# Streamlit re-runs this ENTIRE script top-to-bottom on every interaction
# (every slider drag, every button click, every tab switch). Without
# st.session_state, anything we computed on a PREVIOUS run -- like the
# scorecard from the last company we evaluated -- would simply vanish the
# moment we clicked over to a different tab, because the script would
# start over with no memory of it. st.session_state is a plain dict that
# survives across those re-runs (for as long as the browser tab stays
# open), so we stash the last API result there instead of a local
# variable, and every tab can read it back on every re-run.
if "last_evaluation" not in st.session_state:
    st.session_state.last_evaluation = None
if "portfolio_data" not in st.session_state:
    st.session_state.portfolio_data = None


# ---------------------------------------------------------------------------
# API helper functions
# ---------------------------------------------------------------------------

def call_evaluate_api(payload: dict) -> dict | None:
    """POSTs one company to the backend. Returns the parsed JSON response,
    or None (after showing a st.error) if the API is unreachable or
    rejected the request."""
    try:
        response = requests.post(EVALUATE_URL, json=payload, timeout=15)
    except requests.exceptions.ConnectionError:
        st.error(
            f"⚠️ Could not reach the API at {API_BASE_URL}. "
            f"Is the backend server running? Start it in another terminal with:\n\n"
            f"`venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload`"
        )
        return None
    except requests.exceptions.Timeout:
        st.error("⚠️ The API took too long to respond. Is it still starting up?")
        return None

    if response.status_code == 200:
        return response.json()

    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    st.error(f"API returned {response.status_code}: {detail}")
    return None


def call_portfolio_api() -> dict | None:
    """GETs the portfolio analytics. Returns the parsed JSON response, or
    None (after showing a st.error) if the API is unreachable."""
    try:
        response = requests.get(PORTFOLIO_URL, timeout=15)
    except requests.exceptions.ConnectionError:
        st.error(
            f"⚠️ Could not reach the API at {API_BASE_URL}. "
            f"Is the backend server running? Start it in another terminal with:\n\n"
            f"`venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload`"
        )
        return None

    if response.status_code == 200:
        return response.json()

    st.error(f"API returned {response.status_code} fetching portfolio analytics.")
    return None


# ---------------------------------------------------------------------------
# Sidebar: the input form
# ---------------------------------------------------------------------------

st.sidebar.title("\U0001F4CB Evaluate a Company")
st.sidebar.caption("Enter a company's details, then click Evaluate at the bottom.")

company_id_input = st.sidebar.text_input(
    "Existing Company ID (optional)",
    value="",
    help="Leave blank to create a new company. Provide an existing ID (e.g. "
    "one from the Portfolio tab) to add a new assessment to its history instead.",
)
company_name_input = st.sidebar.text_input("Company Name", value="My Company")

st.sidebar.subheader("Firmographics")
age_of_business_years = st.sidebar.slider(
    "Business Age (years)", min_value=0.5, max_value=40.0, value=5.0, step=0.5
)
business_category = st.sidebar.selectbox("Business Category", BUSINESS_CATEGORIES, index=0)
state = st.sidebar.selectbox("State", STATES, index=STATES.index("Maharashtra"))
employee_count = st.sidebar.slider("Employee Count", min_value=1, max_value=250, value=10)

st.sidebar.subheader("Banking")
avg_monthly_inflow = st.sidebar.number_input(
    "Avg. Monthly Inflow (₹)", min_value=50_000, max_value=15_000_000, value=600_000, step=10_000
)
avg_monthly_outflow = st.sidebar.number_input(
    "Avg. Monthly Outflow (₹)", min_value=0, max_value=15_000_000, value=540_000, step=10_000
)
min_ending_balance_avg = st.sidebar.number_input(
    "Avg. Minimum Bank Balance (₹)", min_value=0, max_value=3_000_000, value=60_000, step=5_000
)
bounce_count_last_6m = st.sidebar.slider("Bounced Payments (last 6 months)", min_value=0, max_value=15, value=0)
account_vintage_months = st.sidebar.slider(
    "Bank Account Age (months)", min_value=0, max_value=240, value=48,
    help="Cannot exceed Business Age × 12.",
)
cash_flow_volatility = st.sidebar.slider(
    "Cash Flow Volatility", min_value=0.05, max_value=1.5, value=0.25, step=0.01
)

st.sidebar.subheader("Tax & Compliance")
has_gst_registration = st.sidebar.checkbox("GST Registered", value=True)
if has_gst_registration:
    gst_filing_regularity_score = st.sidebar.slider(
        "GST Filing Regularity Score", min_value=0.0, max_value=100.0, value=85.0
    )
    annual_turnover_gst = st.sidebar.number_input(
        "Annual GST Turnover (₹)", min_value=0, max_value=150_000_000, value=6_500_000, step=50_000
    )
    gst_filing_delay_days_avg = st.sidebar.slider(
        "Avg. GST Filing Delay (days)", min_value=0, max_value=90, value=4
    )
else:
    gst_filing_regularity_score = None
    annual_turnover_gst = None
    gst_filing_delay_days_avg = None
    st.sidebar.caption("GST fields hidden -- this company has no GST registration.")

st.sidebar.subheader("Digital Footprint")
upi_transaction_volume_ratio = st.sidebar.slider(
    "UPI Transaction Share", min_value=0.0, max_value=1.0, value=0.5, step=0.01
)
pos_terminal_active_status = st.sidebar.checkbox("POS Terminal Active", value=False)
digital_payment_adoption_score = st.sidebar.slider(
    "Digital Payment Adoption Score", min_value=0.0, max_value=100.0, value=50.0
)

st.sidebar.markdown("---")
evaluate_clicked = st.sidebar.button("\U0001F50D Evaluate Company", type="primary", use_container_width=True)

if evaluate_clicked:
    payload = {
        "company_id": company_id_input or None,
        "company_name": company_name_input,
        "age_of_business_years": age_of_business_years,
        "business_category": business_category,
        "state": state,
        "employee_count": employee_count,
        "avg_monthly_inflow": avg_monthly_inflow,
        "avg_monthly_outflow": avg_monthly_outflow,
        "min_ending_balance_avg": min_ending_balance_avg,
        "bounce_count_last_6m": bounce_count_last_6m,
        "account_vintage_months": account_vintage_months,
        "cash_flow_volatility": cash_flow_volatility,
        "has_gst_registration": has_gst_registration,
        "gst_filing_regularity_score": gst_filing_regularity_score,
        "annual_turnover_gst": annual_turnover_gst,
        "gst_filing_delay_days_avg": gst_filing_delay_days_avg,
        "upi_transaction_volume_ratio": upi_transaction_volume_ratio,
        "pos_terminal_active_status": pos_terminal_active_status,
        "digital_payment_adoption_score": digital_payment_adoption_score,
    }
    result = call_evaluate_api(payload)
    if result is not None:
        st.session_state.last_evaluation = result
        st.sidebar.success(
            f"Evaluated '{company_name_input}' → "
            f"Score {result['credit_score']} ({result['risk_band']})"
        )


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("\U0001F3E6 MSME Alternative Credit Assessment")
st.caption(
    "Explainable AI credit scoring for small businesses with thin credit files, "
    "using alternative data (bank transactions, GST filings, UPI/digital payments)."
)

tab1, tab2, tab3 = st.tabs(
    ["\U0001F4CA Credit Scorecard", "\U0001F50E Why this score? (Explainability)", "\U0001F4C8 Portfolio Overview"]
)

# --- TAB 1: Credit Scorecard ------------------------------------------------
with tab1:
    result = st.session_state.last_evaluation
    if result is None:
        st.info("\U0001F448 Fill in the company details in the sidebar and click **Evaluate Company** to see its scorecard here.")
    else:
        st.subheader(f"Company: {result['company_id']}")
        col_gauge, col_info = st.columns([2, 1])

        with col_gauge:
            st.plotly_chart(build_score_gauge(result["credit_score"]), use_container_width=True)

        with col_info:
            band = result["risk_band"]
            band_color = RISK_BAND_COLORS[band]
            st.markdown(
                f"<div style='background-color:{band_color}; padding:24px; "
                f"border-radius:10px; text-align:center; margin-bottom:16px;'>"
                f"<span style='color:white; font-size:28px; font-weight:bold;'>{band}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.metric("Credit Score", result["credit_score"])
            st.metric("Default Probability", f"{result['default_probability'] * 100:.1f}%")

# --- TAB 2: Explainability ---------------------------------------------------
with tab2:
    result = st.session_state.last_evaluation
    if result is None:
        st.info("\U0001F448 Run an evaluation from the sidebar first to see its explanation here.")
    else:
        st.plotly_chart(
            build_shap_driver_chart(result["top_positive_drivers"], result["top_negative_drivers"]),
            use_container_width=True,
        )

        st.subheader("In plain English")
        st.markdown("**Factors increasing risk:**")
        if result["top_positive_drivers"]:
            for driver in result["top_positive_drivers"]:
                st.write(
                    f"\U0001F53A **{feature_label(driver['feature'])}** = "
                    f"{driver['value']:.2f} increased risk (SHAP {driver['shap_value']:+.3f})"
                )
        else:
            st.caption("No risk-increasing factors in the top drivers.")

        st.markdown("**Factors decreasing risk:**")
        if result["top_negative_drivers"]:
            for driver in result["top_negative_drivers"]:
                st.write(
                    f"\U0001F53B **{feature_label(driver['feature'])}** = "
                    f"{driver['value']:.2f} decreased risk (SHAP {driver['shap_value']:+.3f})"
                )
        else:
            st.caption("No risk-decreasing factors in the top drivers.")

# --- TAB 3: Portfolio Overview -----------------------------------------------
with tab3:
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.subheader("Portfolio-wide statistics")
    with col_refresh:
        refresh_clicked = st.button("\U0001F504 Refresh")

    # Fetches automatically the first time this tab renders (no button
    # needed), then only re-fetches when Refresh is clicked -- see the
    # st.session_state setup above for why this persists instead of
    # re-fetching on every single re-run.
    if refresh_clicked or st.session_state.portfolio_data is None:
        st.session_state.portfolio_data = call_portfolio_api()

    data = st.session_state.portfolio_data
    if data is None:
        st.warning("No portfolio data available yet.")
    elif data["total_assessments"] == 0:
        st.info("No companies have been evaluated yet. Use the sidebar to evaluate one.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Companies", data["total_companies"])
        col2.metric("Average Credit Score", f"{data['average_credit_score']:.0f}")
        col3.metric("% High Risk", f"{data['high_risk_pct']:.1f}%")

        st.plotly_chart(
            build_portfolio_pie_chart(
                data["low_risk_count"], data["medium_risk_count"], data["high_risk_count"]
            ),
            use_container_width=True,
        )
