"""
Plain-English explanation text for SHAP drivers (rule-based, no LLM).

The API used to return only raw numbers per driver (e.g. "GST Filing
Regularity Score: +1.526"), which a non-technical loan officer or business
owner can't interpret. This module turns each driver, and the whole
assessment, into readable sentences.

WHY TEMPLATES AND NOT AN LLM
----------------------------------------------------------------------------
Every sentence below is built from fixed templates + a lookup table, so the
output is deterministic (same input -> same text), instant, free, and fully
traceable to the model: the direction and strength words come straight from
the SHAP value's sign and size, and nothing is "invented". That makes it
part of our own explainability pipeline rather than an external black box.

SIGN CONVENTION (matches the model and the frontend)
----------------------------------------------------------------------------
A POSITIVE SHAP value pushes default probability UP (risk increases, score
goes down); a NEGATIVE one pushes it DOWN (risk reduces, score goes up).
This is the same convention model/explainer.py uses for its
"top_positive_contributors" / "top_negative_contributors", and the one
frontend/src/App.tsx uses to colour a bar red ("increase") vs green
("reduce").

MAGNITUDE THRESHOLDS (calibrated on real data, not guessed)
----------------------------------------------------------------------------
SHAP values here are in log-odds units. Across the 617 stored top-driver
SHAP values in the seeded assessments, the median |SHAP| was ~0.11, the
90th percentile ~0.27, and only ~3% reached 0.5 (0.3% reached 1.0). So the
obvious "1.0 / 0.3" cut-offs would label almost every driver "slightly".
Using 0.5 / 0.2 instead gives roughly: strongly ~3%, moderately ~24%,
slightly ~73% of drivers -- a meaningful spread. Change them here only.

How to run the built-in examples:
    venv\\Scripts\\python.exe model/explanation_text.py
"""

from __future__ import annotations

from typing import Any, Optional

# |SHAP| at or above this -> "strongly"; at or above the next -> "moderately";
# anything smaller -> "slightly". See the module docstring for how these
# were chosen.
STRONG_THRESHOLD = 0.5
MODERATE_THRESHOLD = 0.2

# Plain-English noun phrase for every feature in model.config.FEATURE_COLUMNS.
# Written so it reads naturally after "The ..." in a sentence.
FEATURE_EXPLANATIONS: dict[str, str] = {
    "age_of_business_years": "number of years the business has been operating",
    "business_category_encoded": "type of business",
    "state_encoded": "state the business operates in",
    "employee_count": "number of employees",
    "avg_monthly_inflow": "average money received into the bank account each month",
    "avg_monthly_outflow": "average money paid out of the bank account each month",
    "min_ending_balance_avg": "average lowest month-end bank balance",
    "bounce_count_last_6m": "number of bounced payments in the last 6 months",
    "account_vintage_months": "number of months the bank account has been open",
    "cash_flow_volatility": "month-to-month swings in cash flow",
    "has_gst_registration": "GST registration status",
    "gst_filing_regularity_score": "regularity of GST return filing",
    "annual_turnover_gst": "yearly turnover declared in GST returns",
    "gst_filing_delay_days_avg": "average number of days GST returns are filed late",
    "upi_transaction_volume_ratio": "share of business payments made through UPI",
    "pos_terminal_active_status": "whether a card-payment (POS) terminal is active",
    "digital_payment_adoption_score": "level of digital payment adoption",
    "net_cash_margin": "share of incoming money left over after expenses",
    "cash_buffer_ratio": "cash cushion held relative to monthly outflow",
    "gst_to_bank_turnover_ratio": "match between GST-declared turnover and bank turnover",
}

# The only features that can be missing, and only because the business has
# no GST registration (same set as model/report_generator.py).
_GST_NULLABLE_FEATURES = {
    "gst_filing_regularity_score",
    "annual_turnover_gst",
    "gst_filing_delay_days_avg",
    "gst_to_bank_turnover_ratio",
}


def _describe(feature_name: str) -> str:
    """Plain description of a feature; falls back to the raw name (with
    underscores removed) so an unknown feature never crashes the API."""
    return FEATURE_EXPLANATIONS.get(feature_name, feature_name.replace("_", " "))


def _strength_word(shap_value: float) -> str:
    """Maps |SHAP value| to 'strongly' / 'moderately' / 'slightly'."""
    size = abs(shap_value)
    if size >= STRONG_THRESHOLD:
        return "strongly"
    if size >= MODERATE_THRESHOLD:
        return "moderately"
    return "slightly"


def generate_driver_explanation(
    feature_name: str, shap_value: float, display_value: Optional[str]
) -> str:
    """One plain-English sentence for one SHAP driver.

    `display_value` is the already-formatted value from
    model.report_generator.format_driver_value() (e.g. "retail",
    "4.00", or "Not available (GST not registered)"). None / a "Not
    available..." string means the value was missing, which only happens
    for a GST-unregistered company.

    Example: "The average number of days GST returns are filed late (12.00)
    strongly increased the assessed risk."
    """
    strength = _strength_word(shap_value)
    verb = "increased" if shap_value > 0 else "reduced"
    description = _describe(feature_name)

    is_missing = display_value is None or display_value.startswith("Not available")
    if is_missing:
        if feature_name in _GST_NULLABLE_FEATURES:
            reason = "could not be measured because the business is not GST-registered"
        else:
            reason = "was not available"
        return f"The {description} {reason}, and this {strength} {verb} the assessed risk."

    return f"The {description} ({display_value}) {strength} {verb} the assessed risk."


def _join_phrases(phrases: list[str]) -> str:
    """['a'] -> 'a'; ['a', 'b'] -> 'a and b'."""
    return " and ".join(phrases)


def generate_overall_summary(
    risk_band: str,
    credit_score: int,
    default_probability: float,
    top_drivers: list[dict[str, Any]],
) -> str:
    """One paragraph: the risk band + score, then the top 1-2 factors that
    raised risk and the top 1-2 that lowered it.

    `top_drivers` is a combined list of driver dicts (each with at least
    "feature" and "shap_value") -- i.e. top_positive + top_negative.
    """
    probability_pct = default_probability * 100
    sentences = [
        f"This business is assessed as {risk_band} with a credit score of "
        f"{credit_score} (estimated default probability {probability_pct:.1f}%)."
    ]

    increasing = sorted(
        (d for d in top_drivers if d["shap_value"] > 0), key=lambda d: d["shap_value"], reverse=True
    )[:2]
    reducing = sorted((d for d in top_drivers if d["shap_value"] < 0), key=lambda d: d["shap_value"])[:2]

    concerns = [_describe(d["feature"]) for d in increasing]
    strengths = [_describe(d["feature"]) for d in reducing]

    if concerns and strengths:
        sentences.append(
            f"The main concerns are the {_join_phrases(concerns)}, while the "
            f"{_join_phrases(strengths)} support the score."
        )
    elif concerns:
        sentences.append(f"The main concerns are the {_join_phrases(concerns)}.")
    elif strengths:
        sentences.append(f"The score is mainly supported by the {_join_phrases(strengths)}.")

    return " ".join(sentences)


# ---------------------------------------------------------------------------
# PLAIN-ENGLISH LAYER (for business owners; no feature names, no numbers)
# ---------------------------------------------------------------------------
# One everyday phrase per feature, written as a TOPIC ("how regularly GST
# returns are filed") rather than as a value ("consistent GST filing").
# That is deliberate: a SHAP value tells us the direction this feature moved
# the estimate for THIS business compared with a typical one, not what the
# raw value was, so we only say a topic "helped" or "held back" the score --
# never that the business is "good" or "bad" at it. Change wording here only.
PLAIN_TOPICS: dict[str, str] = {
    "age_of_business_years": "how long the business has been operating",
    "business_category_encoded": "the type of business",
    "state_encoded": "the state the business operates in",
    "employee_count": "the size of the team",
    "avg_monthly_inflow": "the amount of money coming in each month",
    "avg_monthly_outflow": "the amount of money going out each month",
    "min_ending_balance_avg": "how much money is left in the account at the end of the month",
    "bounce_count_last_6m": "bounced payments in the last 6 months",
    "account_vintage_months": "how long the bank account has been open",
    "cash_flow_volatility": "how much cash flow rises and falls from month to month",
    "has_gst_registration": "whether the business is registered for GST",
    "gst_filing_regularity_score": "how regularly GST returns are filed",
    "annual_turnover_gst": "the yearly sales declared in GST returns",
    "gst_filing_delay_days_avg": "how late GST returns tend to be filed",
    "upi_transaction_volume_ratio": "how much of the business is paid for through UPI",
    "pos_terminal_active_status": "whether a card-payment machine is in use",
    "digital_payment_adoption_score": "how widely digital payments are used",
    "net_cash_margin": "how much money is left over after expenses",
    "cash_buffer_ratio": "the cash cushion kept compared with monthly spending",
    "gst_to_bank_turnover_ratio": "how well GST-declared sales match the bank account",
}

_PLAIN_BAND_OPENERS = {
    "Low Risk": "Overall, this business falls in the lower-risk group.",
    "Medium Risk": "Overall, this business falls in the middle risk group.",
    "High Risk": "Overall, this business falls in the higher-risk group.",
}


def _plain_topic(feature_name: str) -> str:
    """Everyday phrase for a feature; unknown features fall back to the
    technical description (still no raw underscores)."""
    return PLAIN_TOPICS.get(feature_name, _describe(feature_name))


def generate_plain_summary(
    risk_band: str,
    top_drivers: list[dict[str, Any]],
) -> str:
    """2-4 plain sentences for a non-technical reader: the risk group, what
    helped most, what held back most, and a one-line caveat.

    No feature names, no SHAP numbers, no score figures. Only the SHAP SIGN
    and rank are used: negative SHAP lowers default risk ("helped"),
    positive SHAP raises it ("held back"). `top_drivers` has the same shape
    as for generate_overall_summary().
    """
    sentences = [_PLAIN_BAND_OPENERS.get(risk_band, "This business has been assessed by the model.")]

    helping = sorted((d for d in top_drivers if d["shap_value"] < 0), key=lambda d: d["shap_value"])[:2]
    hurting = sorted(
        (d for d in top_drivers if d["shap_value"] > 0), key=lambda d: d["shap_value"], reverse=True
    )[:2]

    if helping:
        sentences.append(
            f"The score is helped most by {_join_phrases([_plain_topic(d['feature']) for d in helping])}."
        )
    if hurting:
        sentences.append(
            f"It is held back most by {_join_phrases([_plain_topic(d['feature']) for d in hurting])}."
        )
    sentences.append("This is a statistical estimate from the information provided, not a lending decision.")
    return " ".join(sentences)


if __name__ == "__main__":
    print("--- Risk-increasing driver (strong) ---")
    print(generate_driver_explanation("gst_filing_delay_days_avg", 1.526, "12.00"))

    print("\n--- Risk-reducing driver (moderate) ---")
    print(generate_driver_explanation("account_vintage_months", -0.35, "48.00"))

    print("\n--- Slight, encoded category (decoded name) ---")
    print(generate_driver_explanation("business_category_encoded", 0.05, "retail"))

    print("\n--- GST-unregistered company (value is None) ---")
    print(generate_driver_explanation("gst_filing_regularity_score", 0.8, None))
    print(
        generate_driver_explanation(
            "gst_to_bank_turnover_ratio", -0.1, "Not available (GST not registered)"
        )
    )

    low_drivers = [
        {"feature": "bounce_count_last_6m", "shap_value": 0.12},
        {"feature": "cash_flow_volatility", "shap_value": -0.45},
        {"feature": "gst_filing_regularity_score", "shap_value": -0.30},
    ]
    medium_drivers = [
        {"feature": "gst_filing_delay_days_avg", "shap_value": 0.9},
        {"feature": "gst_to_bank_turnover_ratio", "shap_value": 0.4},
        {"feature": "cash_flow_volatility", "shap_value": -0.5},
        {"feature": "age_of_business_years", "shap_value": -0.25},
    ]
    high_drivers = [
        {"feature": "bounce_count_last_6m", "shap_value": 1.4},
        {"feature": "min_ending_balance_avg", "shap_value": 0.7},
        {"feature": "upi_transaction_volume_ratio", "shap_value": -0.05},
    ]

    print("\n--- Overall summary: Low Risk ---")
    print(generate_overall_summary("Low Risk", 812, 0.081, low_drivers))
    print("\n--- Overall summary: Medium Risk ---")
    print(generate_overall_summary("Medium Risk", 721, 0.31, medium_drivers))
    print("\n--- Overall summary: High Risk ---")
    print(generate_overall_summary("High Risk", 540, 0.67, high_drivers))
