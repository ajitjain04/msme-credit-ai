"use client";
// ^ Required: fetches data on load (useEffect) and holds it in state.

import { useCallback, useEffect, useState } from "react";

import { formatApiError, getFairnessAudit } from "@/lib/api";
import type { FairnessAuditResponse } from "@/lib/types";

/**
 * Step 12b-3 -- Fairness Audit page (frontend/app/fairness/page.tsx ->
 * served at /fairness). No Streamlit equivalent existed for this one
 * (Step 12d only added the backend endpoint) -- built fresh here, reusing
 * the same explanation and "never read DIR alone" framing already used
 * for GET /api/v1/analytics/fairness's docstring in backend/main.py and
 * model/fairness.py.
 */
export default function FairnessPage() {
  const [data, setData] = useState<FairnessAuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getFairnessAudit();
      setData(result);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <main className="min-h-screen bg-gray-50 p-6 md:p-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            {"⚖️"} Fairness Audit
          </h1>
          <button
            onClick={refresh}
            disabled={loading}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : `${"🔄"} Refresh`}
          </button>
        </div>

        <section className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-700 shadow-sm">
          <h2 className="mb-2 text-base font-semibold text-gray-900">
            What is Disparate Impact Ratio (DIR)?
          </h2>
          <p className="mb-2">
            DIR compares how often one cohort (e.g. companies from a specific state or business
            category) gets a favourable outcome -- here, Low or Medium Risk instead of High Risk --
            against a reference cohort (the one with the highest favourable-outcome rate in that
            dimension). A DIR of 1.0 means the two cohorts are approved at the same rate; a DIR
            below 0.80 trips the commonly-used &quot;four-fifths rule&quot; threshold for a
            disparity worth a closer look.
          </p>
          <p>
            <strong>A low DIR is a prompt to investigate, not proof of unfair treatment on its
            own.</strong> State and business category are risk-relevant business circumstances,
            not protected characteristics -- a flagged cohort should always be read next to its
            ACTUAL observed default rate (shown right alongside DIR below), never DIR by itself.
            If the actual default rate for a flagged cohort is genuinely low, the model may simply
            not have enough data yet to be confident, rather than being unfair.
          </p>
        </section>

        {error && (
          <pre className="whitespace-pre-wrap rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </pre>
        )}

        {!error && !data && <p className="text-gray-500">Loading fairness audit...</p>}

        {data && (
          <>
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Dimension</th>
                    <th className="px-4 py-3">Cohort</th>
                    <th className="px-4 py-3">Reference Cohort</th>
                    <th className="px-4 py-3">DIR</th>
                    <th className="px-4 py-3">Actual Default Rate</th>
                    <th className="px-4 py-3">Cohort Size</th>
                    <th className="px-4 py-3">Flag</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.audits.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                        No cohorts large enough to audit yet.
                      </td>
                    </tr>
                  ) : (
                    data.audits.map((audit, i) => (
                      <tr key={i} className={audit.flagged_low_dir ? "bg-red-50" : undefined}>
                        <td className="px-4 py-3 font-medium text-gray-900">{audit.cohort_dimension}</td>
                        <td className="px-4 py-3 text-gray-900">{audit.cohort_value}</td>
                        <td className="px-4 py-3 text-gray-500">{audit.reference_dimension_value}</td>
                        <td className="px-4 py-3 text-gray-900">
                          {audit.dir_value !== null ? audit.dir_value.toFixed(3) : "N/A"}
                        </td>
                        <td className="px-4 py-3 text-gray-900">
                          {audit.group_actual_default_rate !== null
                            ? `${(audit.group_actual_default_rate * 100).toFixed(1)}% (n=${audit.cohort_size_with_known_outcome})`
                            : "No known outcomes yet"}
                        </td>
                        <td className="px-4 py-3 text-gray-900">{audit.cohort_size}</td>
                        <td className="px-4 py-3">
                          {audit.flagged_low_dir ? (
                            <span className="rounded-full bg-red-600 px-2 py-1 text-xs font-semibold text-white">
                              {"⚠"} DIR &lt; 0.80
                            </span>
                          ) : (
                            <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-semibold text-green-700">
                              OK
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-gray-500">
              Computed {new Date(data.computed_at).toLocaleString()}. Cohorts below{" "}
              {data.min_cohort_size} assessments are excluded as statistically unreliable (see
              below), not scored.
            </p>

            {data.excluded_small_cohorts.length > 0 && (
              <section className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow-sm">
                <h3 className="mb-2 font-semibold text-gray-900">
                  Excluded (too small to audit reliably)
                </h3>
                <ul className="list-inside list-disc space-y-1">
                  {data.excluded_small_cohorts.map((cohort, i) => (
                    <li key={i}>
                      {cohort.cohort_dimension}: {cohort.cohort_value} (n={cohort.cohort_size})
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
