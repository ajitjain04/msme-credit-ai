/**
 * Step 12b-2 -- TypeScript interfaces mirroring backend/schemas.py exactly.
 *
 * Keep these in sync BY HAND whenever backend/schemas.py changes -- the
 * frontend talks to the API only over HTTP (same design rule
 * dashboard/app.py followed for Streamlit), so there is no shared code
 * between the Python and TypeScript sides, only a shared JSON shape.
 */

// backend/schemas.py: ShapDriver
export interface ShapDriver {
  feature: string;
  value: number;
  shap_value: number;
  // Human-readable version of `value` -- already decoded server-side
  // (business_category_encoded/state_encoded show a real name like
  // "retail", not a raw code like "2.00"). Always prefer this over
  // formatting `value` yourself; see backend/schemas.py's ShapDriver
  // docstring for why.
  display_value: string;
}

// backend/schemas.py: MSMEInput (the request body for POST /api/v1/evaluate)
export interface MSMEInput {
  // Omit (null) to create a new company; provide an existing company_id to
  // add a new assessment to its history instead.
  company_id: string | null;
  company_name: string;

  // Firmographics
  age_of_business_years: number;
  business_category: string;
  state: string;
  employee_count: number;

  // Banking
  avg_monthly_inflow: number;
  avg_monthly_outflow: number;
  min_ending_balance_avg: number;
  bounce_count_last_6m: number;
  account_vintage_months: number;
  cash_flow_volatility: number;

  // Tax & compliance -- the 3 GST fields must be null together when
  // has_gst_registration is false, matching backend/schemas.py's
  // validate_gst_fields_match_registration() validator.
  has_gst_registration: boolean;
  gst_filing_regularity_score: number | null;
  annual_turnover_gst: number | null;
  gst_filing_delay_days_avg: number | null;

  // Digital footprint
  upi_transaction_volume_ratio: number;
  pos_terminal_active_status: boolean;
  digital_payment_adoption_score: number;
}

// backend/schemas.py: EvaluateResponse (the response for POST /api/v1/evaluate)
export interface EvaluateResponse {
  company_id: string;
  default_probability: number;
  credit_score: number;
  risk_band: string;
  top_positive_drivers: ShapDriver[];
  top_negative_drivers: ShapDriver[];
  assessed_at: string;
}

// backend/schemas.py: AssessmentRecord
export interface AssessmentRecord {
  assessment_id: number;
  assessed_at: string;
  default_probability: number;
  credit_score: number;
  risk_band: string;
  top_positive_drivers: ShapDriver[];
  top_negative_drivers: ShapDriver[];
}

// backend/schemas.py: CompanyHistoryResponse (GET /api/v1/company/{company_id})
export interface CompanyHistoryResponse {
  company_id: string;
  company_name: string;
  age_of_business_years: number;
  business_category: string;
  state: string;
  employee_count: number;
  created_at: string;
  assessments: AssessmentRecord[];
}

// backend/schemas.py: FairnessCohortAudit
export interface FairnessCohortAudit {
  cohort_dimension: string;
  cohort_value: string;
  reference_dimension_value: string;
  dir_value: number | null;
  group_actual_default_rate: number | null;
  cohort_size: number;
  cohort_size_with_known_outcome: number;
  flagged_low_dir: boolean;
}

// backend/schemas.py: ExcludedCohort
export interface ExcludedCohort {
  cohort_dimension: string;
  cohort_value: string;
  cohort_size: number;
}

// backend/schemas.py: FairnessAuditResponse (GET /api/v1/analytics/fairness)
export interface FairnessAuditResponse {
  computed_at: string;
  min_cohort_size: number;
  audits: FairnessCohortAudit[];
  excluded_small_cohorts: ExcludedCohort[];
}

// backend/schemas.py: PortfolioAnalyticsResponse (GET /api/v1/analytics/portfolio)
export interface PortfolioAnalyticsResponse {
  total_companies: number;
  total_assessments: number;
  low_risk_count: number;
  medium_risk_count: number;
  high_risk_count: number;
  low_risk_pct: number;
  medium_risk_pct: number;
  high_risk_pct: number;
  average_credit_score: number;
}
