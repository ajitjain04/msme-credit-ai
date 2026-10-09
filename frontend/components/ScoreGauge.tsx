"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";

import { RISK_BAND_COLORS } from "@/lib/featureLabels";

// plotly.js touches `window`/`document` as soon as it's imported, which
// breaks on the server. next/dynamic with ssr:false stops Next.js from
// ever trying to render this on the server -- it only mounts in the
// browser, same reasoning react-plotly.js's own docs give for Next.js.
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ScoreGaugeProps {
  score: number;
}

/**
 * Step 12b-2 -- the 300-900 credit-score gauge, ported 1:1 from
 * dashboard/components/charts.py's build_score_gauge() (same risk-band
 * colors, same threshold needle) so both frontends render an identical
 * chart from the same spec.
 */
export default function ScoreGauge({ score }: ScoreGaugeProps) {
  const data: Data[] = [
    {
      type: "indicator",
      mode: "gauge+number",
      value: score,
      number: { font: { size: 48 } },
      domain: { x: [0, 1], y: [0, 1] },
      gauge: {
        axis: { range: [300, 900], tickwidth: 1, dtick: 100 },
        bar: { color: "rgba(31, 41, 55, 0.85)", thickness: 0.25 },
        bgcolor: "white",
        borderwidth: 1,
        bordercolor: "lightgray",
        steps: [
          { range: [300, 600], color: RISK_BAND_COLORS["High Risk"] },
          { range: [600, 750], color: RISK_BAND_COLORS["Medium Risk"] },
          { range: [750, 900], color: RISK_BAND_COLORS["Low Risk"] },
        ],
        threshold: {
          line: { color: "black", width: 4 },
          thickness: 0.9,
          value: score,
        },
      },
    } as unknown as Data,
  ];

  const layout: Partial<Layout> = {
    height: 320,
    margin: { t: 30, b: 10, l: 30, r: 30 },
  };

  return (
    <Plot
      data={data}
      layout={layout}
      useResizeHandler
      style={{ width: "100%" }}
      config={{ displayModeBar: false }}
    />
  );
}
