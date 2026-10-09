"use client";
// ^ Required: this page holds the "last evaluation result" state (via
// useState) that EvaluationForm writes to and ScoreGauge/ShapDriverChart
// read from -- see the "lifting state up" explanation given alongside
// this change for what that means and why it lives here, one level above
// both.

import { useState } from "react";

import EvaluationForm from "@/components/EvaluationForm";
import ScoreGauge from "@/components/ScoreGauge";
import ShapDriverChart from "@/components/ShapDriverChart";
import { featureLabel, RISK_BAND_COLORS } from "@/lib/featureLabels";
import type { EvaluateResponse } from "@/lib/types";

/**
 * Step 12b-2 -- the real homepage: the company-evaluation form, and once
 * a result exists, the credit scorecard (gauge + risk badge + default
 * probability) and the SHAP explainability view below it. Replaces the
 * Step 12b-1 placeholder entirely.
 */
export default function Home() {
  const [result, setResult] = useState<EvaluateResponse | null>(null);

  return (
    <main className="min-h-screen bg-gray-50 p-6 md:p-10">
      <header className="mx-auto mb-8 max-w-5xl">
        <h1 className="text-3xl font-bold text-gray-900">
          {"🏦"} MSME Alternative Credit Assessment
        </h1>
        <p className="mt-2 text-gray-600">
          Explainable AI credit scoring for small businesses with thin credit files,
          using alternative data (bank transactions, GST filings, UPI/digital payments).
        </p>
      </header>

      <div className="mx-auto max-w-5xl space-y-8">
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">
            {"📋"} Evaluate a Company
          </h2>
          <EvaluationForm onEvaluated={setResult} />
        </section>

        {!result && (
          <p className="text-center text-gray-500">
            {"👈"} Fill in the company details above and click Evaluate Company to see its scorecard here.
          </p>
        )}

        {result && (
          <>
            <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-gray-900">
                {"📊"} Credit Scorecard -- {result.company_id}
              </h2>
              <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div className="md:col-span-2">
                  <ScoreGauge score={result.credit_score} />
                </div>
                <div className="flex flex-col gap-4">
                  <div
                    className="rounded-lg p-6 text-center"
                    style={{ backgroundColor: RISK_BAND_COLORS[result.risk_band] }}
                  >
                    <span className="text-2xl font-bold text-white">{result.risk_band}</span>
                  </div>
                  <div className="rounded-lg border border-gray-200 p-4 text-center">
                    <p className="text-sm text-gray-500">Credit Score</p>
                    <p className="text-2xl font-bold text-gray-900">{result.credit_score}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 p-4 text-center">
                    <p className="text-sm text-gray-500">Default Probability</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {(result.default_probability * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold text-gray-900">
                {"🔎"} Why this score? (Explainability)
              </h2>
              <ShapDriverChart
                topPositiveDrivers={result.top_positive_drivers}
                topNegativeDrivers={result.top_negative_drivers}
              />

              <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 font-semibold text-red-700">Factors increasing risk</h3>
                  {result.top_positive_drivers.length === 0 ? (
                    <p className="text-sm text-gray-500">No risk-increasing factors in the top drivers.</p>
                  ) : (
                    <ul className="space-y-1 text-sm text-gray-700">
                      {result.top_positive_drivers.map((d, i) => (
                        <li key={i}>
                          {"🔺"} <strong>{featureLabel(d.feature)}</strong> = {d.display_value}{" "}
                          increased risk (SHAP {d.shap_value >= 0 ? "+" : ""}
                          {d.shap_value.toFixed(3)})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3 className="mb-2 font-semibold text-green-700">Factors decreasing risk</h3>
                  {result.top_negative_drivers.length === 0 ? (
                    <p className="text-sm text-gray-500">No risk-decreasing factors in the top drivers.</p>
                  ) : (
                    <ul className="space-y-1 text-sm text-gray-700">
                      {result.top_negative_drivers.map((d, i) => (
                        <li key={i}>
                          {"🔻"} <strong>{featureLabel(d.feature)}</strong> = {d.display_value}{" "}
                          decreased risk (SHAP {d.shap_value >= 0 ? "+" : ""}
                          {d.shap_value.toFixed(3)})
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
