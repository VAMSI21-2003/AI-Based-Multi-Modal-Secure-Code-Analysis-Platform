import { useEffect, useState } from "react";
import { Lightbulb } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip } from "recharts";
import PageShell from "../components/PageShell";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import ProgressBar from "../components/ProgressBar";
import Gauge from "../components/Gauge";
import ContributionBars from "../components/ContributionBars";
import AstTreeViewer from "../components/AstTreeViewer";
import FeatureTable from "../components/FeatureTable";
import { useActiveScan } from "../hooks/useActiveScan";
import { getEvalCurves, type EvalCurves } from "../api/client";

export default function Explainability() {
  const { scanId, scan, detail, loading, error } = useActiveScan();
  const [curves, setCurves] = useState<EvalCurves | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEvalCurves().then((c) => { if (!cancelled) setCurves(c); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!scanId) {
    return (
      <PageShell title="Explainability" subtitle="Why the model made this decision">
        <ScanPickerEmpty icon={Lightbulb} title="No scan selected" description="Run a scan to see the full explainability breakdown: AST tree, feature values, and contribution analysis." />
      </PageShell>
    );
  }

  if (loading || !scan || !detail) {
    return (
      <PageShell title="Explainability" subtitle="Why the model made this decision">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Building explanation..." />}
      </PageShell>
    );
  }

  const topWarnings = detail.insights.filter(([, sev]) => sev === "warning").map(([t]) => t);
  const narrative = scan.verdict === "VULNERABLE"
    ? `The ${scan.model_used} classifier flagged this function as VULNERABLE with ${scan.confidence.toFixed(1)}% confidence. ` +
      (topWarnings.length
        ? `This is primarily driven by: ${topWarnings.length} structural warning${topWarnings.length > 1 ? "s" : ""} -- ${topWarnings.join(" ")}`
        : "The semantic embedding from CodeBERT placed this function close to known-vulnerable patterns in the training distribution.") +
      (detail.line_risks.length ? ` ${detail.line_risks.length} line(s) also matched known-dangerous API patterns (see Heatmap).` : "")
    : `The ${scan.model_used} classifier did not find sufficient evidence of vulnerability, with ${scan.confidence.toFixed(1)}% confidence in the "safe" verdict. ` +
      `Structural complexity and CodeBERT's semantic embedding both placed this function closer to the safe cluster of the training distribution.`;

  return (
    <PageShell title="Explainability" subtitle={`Full decision breakdown for ${scan.filename}`}>
      <ChartCard title="Decision Explanation" className="mb-5">
        <p className="text-sm text-(--text-secondary) leading-relaxed">{narrative}</p>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <ProgressBar value={scan.vuln_probability} color={scan.risk_color} label="Vulnerability Probability" />
          <ProgressBar value={scan.confidence} color="var(--series-7)" label="Model Confidence" />
        </div>
      </ChartCard>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Confidence" className="flex items-center justify-center"><Gauge value={scan.confidence} color="var(--series-7)" label="Confidence" /></ChartCard>
        <ChartCard title="Vulnerability Risk" className="flex items-center justify-center"><Gauge value={scan.vuln_probability} color={scan.risk_color} label="Risk" /></ChartCard>
        <ChartCard title="Safety Score" className="flex items-center justify-center"><Gauge value={scan.safe_probability} color="var(--status-good)" label="Safe" /></ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="Top Feature Contributions" subtitle="What pushed the prediction, and in which direction">
          {detail.contributions ? <ContributionBars contributions={detail.contributions} /> : (
            <div className="text-xs text-(--text-muted) py-10 text-center">Not available in demo mode.</div>
          )}
        </ChartCard>
        <ChartCard title="AST Tree Viewer" subtitle="Interactive parse tree (click to expand)">
          <AstTreeViewer tree={detail.ast_tree.tree} available={detail.ast_tree.available} error={detail.ast_tree.error} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="AST Feature Values" subtitle="11 structural features vs. typical range">
          <FeatureTable features={scan.ast_features} />
        </ChartCard>
        <ChartCard title="Software Metric Values" subtitle="13 quality metrics vs. typical range">
          <FeatureTable features={scan.metric_features} />
        </ChartCard>
      </div>

      {curves?.available && curves.xgboost && (
        <ChartCard title="Global Feature Importance" subtitle="Model-wide importance from the trained XGBoost classifier (not specific to this scan) — top 15">
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={curves.xgboost.feature_importances_top20.slice(0, 15).slice().reverse()} layout="vertical" margin={{ left: 20, right: 20 }}>
              <CartesianGrid stroke="var(--gridline)" horizontal={false} />
              <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
              <YAxis type="category" dataKey="feature" width={110} tick={{ fill: "var(--text-secondary)", fontSize: 10 }} axisLine={false} tickLine={false} />
              <RTooltip {...chartTooltipStyle} />
              <Bar dataKey="importance" fill="#9085e9" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </PageShell>
  );
}
