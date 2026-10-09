"use client";
// ^ Required: this component holds form state (useState) and submits it
// with a live axios call on click -- both only make sense in the browser.

import { useState, FormEvent, ReactNode } from "react";

import { evaluateCompany, formatApiError } from "@/lib/api";
import type { EvaluateResponse, MSMEInput } from "@/lib/types";

// Mirrors dashboard/app.py's BUSINESS_CATEGORIES/STATES lists exactly
// (docs/data_dictionary.md section 1). Maintained by hand in both
// frontends -- keep in sync with model/artifacts/category_encodings.json
// if this list ever changes.
const BUSINESS_CATEGORIES = ["retail", "trading", "services", "manufacturing", "food"];

const STATES = [
  "Andhra Pradesh", "Bihar", "Delhi", "Gujarat", "Haryana", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Punjab", "Rajasthan",
  "Tamil Nadu", "Telangana", "Uttar Pradesh", "West Bengal",
];

// Same defaults dashboard/app.py's sidebar widgets use.
interface FormState {
  companyId: string;
  companyName: string;
  ageOfBusinessYears: number;
  businessCategory: string;
  state: string;
  employeeCount: number;
  avgMonthlyInflow: number;
  avgMonthlyOutflow: number;
  minEndingBalanceAvg: number;
  bounceCountLast6m: number;
  accountVintageMonths: number;
  cashFlowVolatility: number;
  hasGstRegistration: boolean;
  gstFilingRegularityScore: number;
  annualTurnoverGst: number;
  gstFilingDelayDaysAvg: number;
  upiTransactionVolumeRatio: number;
  posTerminalActiveStatus: boolean;
  digitalPaymentAdoptionScore: number;
}

const INITIAL_STATE: FormState = {
  companyId: "",
  companyName: "My Company",
  ageOfBusinessYears: 5.0,
  businessCategory: BUSINESS_CATEGORIES[0],
  state: "Maharashtra",
  employeeCount: 10,
  avgMonthlyInflow: 600_000,
  avgMonthlyOutflow: 540_000,
  minEndingBalanceAvg: 60_000,
  bounceCountLast6m: 0,
  accountVintageMonths: 48,
  cashFlowVolatility: 0.25,
  hasGstRegistration: true,
  gstFilingRegularityScore: 85,
  annualTurnoverGst: 6_500_000,
  gstFilingDelayDaysAvg: 4,
  upiTransactionVolumeRatio: 0.5,
  posTerminalActiveStatus: false,
  digitalPaymentAdoptionScore: 50,
};

interface EvaluationFormProps {
  /** Called with the API result once a submission succeeds. */
  onEvaluated: (result: EvaluateResponse) => void;
}

/**
 * Step 12b-2 -- the real company-evaluation form, mirroring
 * dashboard/app.py's sidebar fields (same fields, same min/max/defaults
 * from docs/data_dictionary.md), laid out as a multi-column form grouped
 * into the same 4 sections.
 */
export default function EvaluationForm({ onEvaluated }: EvaluationFormProps) {
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: MSMEInput = {
      company_id: form.companyId.trim() === "" ? null : form.companyId.trim(),
      company_name: form.companyName,
      age_of_business_years: form.ageOfBusinessYears,
      business_category: form.businessCategory,
      state: form.state,
      employee_count: form.employeeCount,
      avg_monthly_inflow: form.avgMonthlyInflow,
      avg_monthly_outflow: form.avgMonthlyOutflow,
      min_ending_balance_avg: form.minEndingBalanceAvg,
      bounce_count_last_6m: form.bounceCountLast6m,
      account_vintage_months: form.accountVintageMonths,
      cash_flow_volatility: form.cashFlowVolatility,
      has_gst_registration: form.hasGstRegistration,
      // Null together when unregistered -- matches backend/schemas.py's
      // validate_gst_fields_match_registration() validator exactly.
      gst_filing_regularity_score: form.hasGstRegistration ? form.gstFilingRegularityScore : null,
      annual_turnover_gst: form.hasGstRegistration ? form.annualTurnoverGst : null,
      gst_filing_delay_days_avg: form.hasGstRegistration ? form.gstFilingDelayDaysAvg : null,
      upi_transaction_volume_ratio: form.upiTransactionVolumeRatio,
      pos_terminal_active_status: form.posTerminalActiveStatus,
      digital_payment_adoption_score: form.digitalPaymentAdoptionScore,
    };

    try {
      const result = await evaluateCompany(payload);
      onEvaluated(result);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Existing Company ID (optional)">
          <input
            type="text"
            value={form.companyId}
            onChange={(e) => update("companyId", e.target.value)}
            placeholder="Leave blank to create a new company"
            className={inputClass}
          />
        </Field>
        <Field label="Company Name">
          <input
            type="text"
            value={form.companyName}
            onChange={(e) => update("companyName", e.target.value)}
            className={inputClass}
          />
        </Field>
      </div>

      <Section title="Firmographics">
        <Field label="Business Age (years)">
          <input
            type="number"
            min={0.5}
            max={40}
            step={0.5}
            value={form.ageOfBusinessYears}
            onChange={(e) => update("ageOfBusinessYears", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Business Category">
          <select
            value={form.businessCategory}
            onChange={(e) => update("businessCategory", e.target.value)}
            className={inputClass}
          >
            {BUSINESS_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="State">
          <select
            value={form.state}
            onChange={(e) => update("state", e.target.value)}
            className={inputClass}
          >
            {STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Employee Count">
          <input
            type="number"
            min={1}
            max={250}
            value={form.employeeCount}
            onChange={(e) => update("employeeCount", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
      </Section>

      <Section title="Banking">
        <Field label="Avg. Monthly Inflow (₹)">
          <input
            type="number"
            min={50_000}
            max={15_000_000}
            step={10_000}
            value={form.avgMonthlyInflow}
            onChange={(e) => update("avgMonthlyInflow", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Avg. Monthly Outflow (₹)">
          <input
            type="number"
            min={0}
            max={15_000_000}
            step={10_000}
            value={form.avgMonthlyOutflow}
            onChange={(e) => update("avgMonthlyOutflow", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Avg. Minimum Bank Balance (₹)">
          <input
            type="number"
            min={0}
            max={3_000_000}
            step={5_000}
            value={form.minEndingBalanceAvg}
            onChange={(e) => update("minEndingBalanceAvg", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Bounced Payments (last 6 months)">
          <input
            type="number"
            min={0}
            max={15}
            value={form.bounceCountLast6m}
            onChange={(e) => update("bounceCountLast6m", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Bank Account Age (months)" hint="Cannot exceed Business Age × 12.">
          <input
            type="number"
            min={0}
            max={240}
            value={form.accountVintageMonths}
            onChange={(e) => update("accountVintageMonths", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <Field label="Cash Flow Volatility">
          <input
            type="number"
            min={0.05}
            max={1.5}
            step={0.01}
            value={form.cashFlowVolatility}
            onChange={(e) => update("cashFlowVolatility", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
      </Section>

      <Section title="Tax & Compliance">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700 md:col-span-2">
          <input
            type="checkbox"
            checked={form.hasGstRegistration}
            onChange={(e) => update("hasGstRegistration", e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          GST Registered
        </label>

        {form.hasGstRegistration ? (
          <>
            <Field label="GST Filing Regularity Score">
              <input
                type="number"
                min={0}
                max={100}
                value={form.gstFilingRegularityScore}
                onChange={(e) => update("gstFilingRegularityScore", Number(e.target.value))}
                className={inputClass}
              />
            </Field>
            <Field label="Annual GST Turnover (₹)">
              <input
                type="number"
                min={0}
                max={150_000_000}
                step={50_000}
                value={form.annualTurnoverGst}
                onChange={(e) => update("annualTurnoverGst", Number(e.target.value))}
                className={inputClass}
              />
            </Field>
            <Field label="Avg. GST Filing Delay (days)">
              <input
                type="number"
                min={0}
                max={90}
                value={form.gstFilingDelayDaysAvg}
                onChange={(e) => update("gstFilingDelayDaysAvg", Number(e.target.value))}
                className={inputClass}
              />
            </Field>
          </>
        ) : (
          <p className="text-sm text-gray-500 md:col-span-2">
            GST fields hidden -- this company has no GST registration.
          </p>
        )}
      </Section>

      <Section title="Digital Footprint">
        <Field label="UPI Transaction Share">
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={form.upiTransactionVolumeRatio}
            onChange={(e) => update("upiTransactionVolumeRatio", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={form.posTerminalActiveStatus}
            onChange={(e) => update("posTerminalActiveStatus", e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          POS Terminal Active
        </label>
        <Field label="Digital Payment Adoption Score">
          <input
            type="number"
            min={0}
            max={100}
            value={form.digitalPaymentAdoptionScore}
            onChange={(e) => update("digitalPaymentAdoptionScore", Number(e.target.value))}
            className={inputClass}
          />
        </Field>
      </Section>

      {error && (
        <pre className="whitespace-pre-wrap rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </pre>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-md bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50 md:w-auto"
      >
        {submitting ? "Evaluating..." : "🔍 Evaluate Company"}
      </button>
    </form>
  );
}

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-gray-200 pt-6">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">{children}</div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-gray-500">{hint}</span>}
    </label>
  );
}
