"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";

import { RISK_BAND_COLORS } from "@/lib/featureLabels";

// See ScoreGauge.tsx for why this needs ssr:false.
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PortfolioPieChartProps {
  lowCount: number;
  mediumCount: number;
  highCount: number;
}

/**
 * Step 12b-3 -- the portfolio risk-band donut chart, ported 1:1 from
 * dashboard/components/charts.py's build_portfolio_pie_chart() (same
 * colors, same hole size, same label+percent text).
 */
export default function PortfolioPieChart({
  lowCount,
  mediumCount,
  highCount,
}: PortfolioPieChartProps) {
  const labels = ["Low Risk", "Medium Risk", "High Risk"];
  const values = [lowCount, mediumCount, highCount];
  const colors = labels.map((label) => RISK_BAND_COLORS[label]);

  const data: Data[] = [
    {
      type: "pie",
      labels,
      values,
      hole: 0.45,
      marker: { colors },
      textinfo: "label+percent",
    },
  ];

  const layout: Partial<Layout> = {
    title: { text: "Portfolio Risk Band Distribution" },
    height: 400,
    margin: { t: 60, b: 10, l: 10, r: 10 },
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
