/**
 * Step 12b-2 -- human-readable feature labels + risk-band colors, ported
 * 1:1 from dashboard/components/charts.py's FEATURE_LABELS/feature_label()
 * and RISK_BAND_COLORS, so both frontends show identical wording and
 * colors. Keep these in sync BY HAND if the Python versions ever change
 * (same maintained-by-hand caveat charts.py itself documents).
 */

export const RISK_BAND_COLORS: Record<string, string> = {
  "Low Risk": "#2ecc71", // green
  "Medium Risk": "#f1c40f", // yellow
  "High Risk": "#e74c3c", // red
};

const FEATURE_LABELS: Record<string, string> = {
  age_of_business_years: "Business Age (years)",
  business_category_encoded: "Business Category",
  state_encoded: "State",
  employee_count: "Employee Count",
  avg_monthly_inflow: "Avg. Monthly Inflow (₹)",
  avg_monthly_outflow: "Avg. Monthly Outflow (₹)",
  min_ending_balance_avg: "Avg. Minimum Bank Balance (₹)",
  bounce_count_last_6m: "Bounced Payments (last 6 months)",
  account_vintage_months: "Bank Account Age (months)",
  cash_flow_volatility: "Cash Flow Volatility",
  has_gst_registration: "GST Registered",
  gst_filing_regularity_score: "GST Filing Regularity Score",
  annual_turnover_gst: "Annual GST Turnover (₹)",
  gst_filing_delay_days_avg: "Avg. GST Filing Delay (days)",
  upi_transaction_volume_ratio: "UPI Transaction Share",
  pos_terminal_active_status: "POS Terminal Active",
  digital_payment_adoption_score: "Digital Payment Adoption Score",
  net_cash_margin: "Net Cash Margin",
  cash_buffer_ratio: "Cash Buffer Ratio",
  gst_to_bank_turnover_ratio: "GST-to-Bank Turnover Ratio",
};

/**
 * Human-readable label for a raw feature column name, falling back to a
 * title-cased version of the name itself if it's not in the lookup --
 * same fallback behaviour as charts.py's feature_label().
 */
export function featureLabel(featureName: string): string {
  if (featureName in FEATURE_LABELS) {
    return FEATURE_LABELS[featureName];
  }
  return featureName
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
