"use client";
// ^ Required: this page fetches data on load (useEffect) and holds it in
// state (useState) -- both browser-only concerns.

import { useCallback, useEffect, useState } from "react";

import PortfolioPieChart from "@/components/PortfolioPieChart";
import { formatApiError, getPortfolioAnalytics } from "@/lib/api";
import type { PortfolioAnalyticsResponse } from "@/lib/types";

/**
 * Step 12b-3 -- Portfolio Overview page (frontend/app/portfolio/page.tsx
 * -> served at /portfolio, see Next.js's file-based routing). Ports
 * dashboard/app.py's Tab 3 exactly: 3 stat cards + the risk-band donut
 * chart, with the same manual Refresh button.
 */
export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getPortfolioAnalytics();
      setData(result);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetches automatically the first time this page loads -- same as
  // dashboard/app.py's "fetch on first render, then only on Refresh" rule.
  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <main className="min-h-screen bg-gray-50 p-6 md:p-10">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            {"📈"} Portfolio Overview
          </h1>
          <button
            onClick={refresh}
            disabled={loading}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : `${"🔄"} Refresh`}
          </button>
        </div>

        {error && (
          <pre className="whitespace-pre-wrap rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </pre>
        )}

        {!error && !data && <p className="text-gray-500">Loading portfolio data...</p>}

        {data && data.total_assessments === 0 && (
          <p className="rounded-lg border border-gray-200 bg-white p-6 text-center text-gray-500 shadow-sm">
            No companies have been evaluated yet. Use the Evaluate page to evaluate one.
          </p>
        )}

        {data && data.total_assessments > 0 && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard label="Total Companies" value={data.total_companies} />
              <StatCard label="Average Credit Score" value={data.average_credit_score.toFixed(0)} />
              <StatCard label="% High Risk" value={`${data.high_risk_pct.toFixed(1)}%`} />
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <PortfolioPieChart
                lowCount={data.low_risk_count}
                mediumCount={data.medium_risk_count}
                highCount={data.high_risk_count}
              />
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-center shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
