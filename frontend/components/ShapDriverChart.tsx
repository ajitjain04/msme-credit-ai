"use client";

import dynamic from "next/dynamic";
import type { Data, Layout, Shape } from "plotly.js";

import { RISK_BAND_COLORS, featureLabel } from "@/lib/featureLabels";
import type { ShapDriver } from "@/lib/types";

// See ScoreGauge.tsx for why this needs ssr:false.
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ShapDriverChartProps {
  topPositiveDrivers: ShapDriver[];
  topNegativeDrivers: ShapDriver[];
}

/**
 * Step 12b-2 -- the tornado-style SHAP driver chart, ported 1:1 from
 * dashboard/components/charts.py's build_shap_driver_chart(): positive
 * SHAP values (risk UP) extend right in red, negative SHAP values (risk
 * DOWN) extend left in green, sorted safest-at-top to riskiest-at-bottom.
 */
export default function ShapDriverChart({
  topPositiveDrivers,
  topNegativeDrivers,
}: ShapDriverChartProps) {
  const rows = [...topPositiveDrivers, ...topNegativeDrivers]
    .map((d) => ({
      label: featureLabel(d.feature),
      shapValue: d.shap_value,
      displayValue: d.display_value,
    }))
    .sort((a, b) => a.shapValue - b.shapValue);

  const labels = rows.map((r) => r.label);
  const values = rows.map((r) => r.shapValue);
  const colors = values.map((v) =>
    v > 0 ? RISK_BAND_COLORS["High Risk"] : RISK_BAND_COLORS["Low Risk"]
  );

  const data: Data[] = [
    {
      type: "bar",
      orientation: "h",
      x: values,
      y: labels,
      marker: { color: colors },
      text: values.map((v) => `${v >= 0 ? "+" : ""}${v.toFixed(3)}`),
      textposition: "outside",
      // Shows the already-decoded value (e.g. "Business Category: retail")
      // on hover, instead of the raw encoded number -- same display_value
      // the sentences below the chart use.
      hovertext: rows.map(
        (r) => `${r.label}: ${r.displayValue} (SHAP ${r.shapValue >= 0 ? "+" : ""}${r.shapValue.toFixed(3)})`
      ),
      hoverinfo: "text",
    },
  ];

  // go.Figure.add_vline(x=0, ...)'s equivalent in plotly.js: a shape line
  // spanning the full plot height at x=0 (yref "paper" means 0-1 of the
  // plot area, not the data's own y-scale).
  const zeroLine: Partial<Shape> = {
    type: "line",
    x0: 0,
    x1: 0,
    y0: 0,
    y1: 1,
    xref: "x",
    yref: "paper",
    line: { color: "gray", width: 1 },
  };

  const layout: Partial<Layout> = {
    title: { text: "What's driving this score? (SHAP values, log-odds)" },
    xaxis: { title: { text: "← Lowers risk (safer)          Raises risk (riskier) →" } },
    height: Math.max(320, 42 * labels.length + 80),
    margin: { l: 10, r: 10, t: 60, b: 50 },
    shapes: [zeroLine],
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
