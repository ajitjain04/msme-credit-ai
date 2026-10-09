/**
 * Step 12b-2 -- typed axios client for the FastAPI backend.
 *
 * Mirrors dashboard/app.py's call_evaluate_api()/fetch_pdf_report()/
 * call_portfolio_api() helpers, but as reusable typed functions instead of
 * inline Streamlit code -- every component imports these instead of
 * calling axios directly, so there is exactly one place that knows the
 * API's base URL and response shapes.
 */

import axios from "axios";

import type {
  CompanyHistoryResponse,
  EvaluateResponse,
  FairnessAuditResponse,
  MSMEInput,
  PortfolioAnalyticsResponse,
} from "./types";

// NEXT_PUBLIC_ prefix required -- see frontend/.env.local's comment. This
// is inlined into the browser bundle at build time.
const API_URL = process.env.NEXT_PUBLIC_API_URL;

const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

/** POST /api/v1/evaluate -- scores one company and returns its scorecard. */
export async function evaluateCompany(payload: MSMEInput): Promise<EvaluateResponse> {
  const response = await apiClient.post<EvaluateResponse>("/api/v1/evaluate", payload);
  return response.data;
}

/** GET /api/v1/company/{company_id} -- a company's profile + full assessment history. */
export async function getCompanyHistory(companyId: string): Promise<CompanyHistoryResponse> {
  const response = await apiClient.get<CompanyHistoryResponse>(
    `/api/v1/company/${encodeURIComponent(companyId)}`
  );
  return response.data;
}

/** GET /api/v1/analytics/portfolio -- portfolio-wide risk-band stats. */
export async function getPortfolioAnalytics(): Promise<PortfolioAnalyticsResponse> {
  const response = await apiClient.get<PortfolioAnalyticsResponse>("/api/v1/analytics/portfolio");
  return response.data;
}

/** GET /api/v1/analytics/fairness -- a fresh Disparate Impact Ratio audit. */
export async function getFairnessAudit(): Promise<FairnessAuditResponse> {
  const response = await apiClient.get<FairnessAuditResponse>("/api/v1/analytics/fairness");
  return response.data;
}

/**
 * GET /api/v1/company/{company_id}/report/pdf -- downloads the one-page
 * PDF credit report and triggers a real browser file download.
 *
 * Standard browser pattern for a blob response: fetch the PDF bytes as a
 * Blob, wrap them in a temporary object URL, click a throwaway <a> tag
 * pointed at that URL (this is what actually triggers the browser's
 * "Save As" / downloads behaviour -- there's no other way to do this from
 * JavaScript), then clean up both the link element and the object URL.
 * Same end result as dashboard/app.py's st.download_button, just written
 * out by hand since the browser has no built-in equivalent.
 */
export async function downloadCompanyPdfReport(companyId: string): Promise<void> {
  const response = await apiClient.get(
    `/api/v1/company/${encodeURIComponent(companyId)}/report/pdf`,
    { responseType: "blob" }
  );

  const blob = new Blob([response.data], { type: "application/pdf" });
  const objectUrl = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `credit_report_${companyId}.pdf`; // matches backend/main.py's filename exactly
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(objectUrl);
}

/**
 * Turns an unknown error from any of the calls above into one readable
 * message -- same pattern as dashboard/app.py's repeated
 * "API unreachable vs. API rejected the request" st.error handling, just
 * written once instead of three times.
 */
export function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) {
      return (
        `Could not reach the API at ${API_URL}. Is the backend server running? ` +
        `Start it in another terminal with: venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload`
      );
    }

    const detail = err.response.data?.detail;
    if (typeof detail === "string") {
      return `API returned ${err.response.status}: ${detail}`;
    }
    if (Array.isArray(detail)) {
      // FastAPI/Pydantic validation errors come back as a list of
      // {loc, msg, type} objects -- flatten them into one readable line.
      const messages = detail.map((d: { loc?: unknown[]; msg?: string }) =>
        d.msg ? `${(d.loc ?? []).join(".")}: ${d.msg}` : JSON.stringify(d)
      );
      return `API returned ${err.response.status}: ${messages.join("; ")}`;
    }
    return `API returned ${err.response.status}: ${err.message}`;
  }
  return "Unknown error.";
}
