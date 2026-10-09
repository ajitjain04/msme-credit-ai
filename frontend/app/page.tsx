"use client";
// ^ REQUIRED here: this component uses useState + an onClick handler + a
// live axios call, all of which only make sense running in the BROWSER.
// Without this directive, Next.js's App Router treats every component as
// a Server Component by default (see this step's explanation of what that
// means). See the module docstring further down for the full picture.

import { useState } from "react";
import axios from "axios";

// NEXT_PUBLIC_ prefix is required for any env var read in client-side code
// -- see frontend/.env.local's comment for why. process.env.NEXT_PUBLIC_*
// values are inlined into the JavaScript bundle at BUILD time, so this
// works the same whether the request is fired from the browser or (later)
// from a Server Component.
const API_URL = process.env.NEXT_PUBLIC_API_URL;

/**
 * Step 12b-1 — placeholder homepage.
 *
 * This page exists purely to prove the Next.js frontend can successfully
 * reach the FastAPI backend (GET /health) before any real UI (the company
 * -evaluation form, the scorecard, the SHAP charts) gets built on top of
 * it. Nothing here is the final design -- it will be replaced entirely in
 * the next sub-step.
 */
export default function Home() {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkHealth() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await axios.get(`${API_URL}/health`);
      setResult(JSON.stringify(response.data, null, 2));
    } catch (err) {
      const message = axios.isAxiosError(err) ? err.message : "Unknown error.";
      setError(
        `Could not reach the API at ${API_URL}. Is the backend running? (uvicorn backend.main:app --reload) -- ${message}`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-bold text-center">
        MSME Alternative Credit Assessment
      </h1>
      <p className="max-w-md text-center text-gray-600">
        Placeholder page (Step 12b-1) -- confirms this Next.js frontend can
        talk to the FastAPI backend before any real UI is built.
      </p>

      <button
        onClick={checkHealth}
        disabled={loading}
        className="rounded-md bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Checking..." : "Test API Connection (/health)"}
      </button>

      {result && (
        <pre className="w-full max-w-md overflow-auto rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-900">
          {result}
        </pre>
      )}

      {error && (
        <pre className="w-full max-w-md overflow-auto whitespace-pre-wrap rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </pre>
      )}
    </main>
  );
}
