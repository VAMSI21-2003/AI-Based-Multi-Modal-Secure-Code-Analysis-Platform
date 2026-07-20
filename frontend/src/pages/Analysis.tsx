import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Brain, BrainCircuit, Flame, Wand2, Download, FileCode2, Clock, Scale, ShieldAlert } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import Gauge from "../components/Gauge";
import FeatureRadar from "../components/FeatureRadar";
import EmbeddingScatter from "../components/EmbeddingScatter";
import ContributionBars from "../components/ContributionBars";
import { useActiveScan } from "../hooks/useActiveScan";
import { getHistory, downloadScanPdf } from "../api/client";
import toast from "react-hot-toast";
import { timeAgo } from "../utils/risk";

export default function Analysis() {
  const { scanId, scan, detail, loading, error } = useActiveScan();
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => {
    if (!scan) return;
    getHistory({ project: scan.project_name, sort: "date", order: "asc", limit: 30 })
      .then((d) => setTimeline(d.results.map((r: any) => ({
        date: new Date(r.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
        probability: r.vuln_probability,
        filename: r.filename,
      }))))
      .catch(() => {});
  }, [scan]);

  if (!scanId) {
    return (
      <PageShell title="AI Vulnerability Analysis" subtitle="Deep dive into a single function's prediction">
        <ScanPickerEmpty icon={Brain} title="No scan selected" description="Run a scan or pick a recent one to see the full AI analysis: confidence, explanation, AST, metrics, and embedding placement." />
      </PageShell>
    );
  }

  if (loading || !scan || !detail) {
    return (
      <PageShell title="AI Vulnerability Analysis" subtitle="Deep dive into a single function's prediction">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Loading analysis..." />}
      </PageShell>
    );
  }

  const insights = detail.insights ?? [];

  return (
    <PageShell
      title="AI Vulnerability Analysis"
      subtitle={`${scan.filename} · ${scan.project_name}`}
      actions={
        <>
          <Link to={`/explanation?scan=${scanId}`} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <BrainCircuit size={14} /> Code Explanation
          </Link>
          <Link to={`/heatmap?scan=${scanId}`} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <Flame size={14} /> Heatmap
          </Link>
          <Link to={`/comparison?scan=${scanId}`} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <Scale size={14} /> Compare Models
          </Link>
          <Link to={`/recommendations?scan=${scanId}`} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <Wand2 size={14} /> Recommendations
          </Link>
          <a href={downloadScanPdf(scanId!)} onClick={() => toast.success("Generating PDF report...")} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110">
            <Download size={14} /> PDF Report
          </a>
        </>
      }
    >
      {scan.evidence_risk?.escalated && (
        <div className="mb-5 rounded-xl border p-4 flex items-start gap-3" style={{ background: "rgba(208,59,59,0.08)", borderColor: "rgba(208,59,59,0.35)" }}>
          <ShieldAlert size={18} className="text-(--status-critical) shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-semibold text-(--status-critical) flex items-center gap-2">
              Evidence-based risk: <RiskBadge level={scan.evidence_risk.level} size="sm" />
              <span className="text-(--text-muted) font-normal text-xs">(model alone reported {scan.evidence_risk.ml_level})</span>
            </div>
            <div className="text-xs text-(--text-secondary) mt-1.5">
              The line-level scanner found deterministic, severity-{scan.evidence_risk.max_finding_severity} findings that this display escalates above the model's own risk level. The model's probability and confidence below are unchanged — this is an additional cross-check, not a replacement.
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {scan.evidence_risk.reasons.map((r, i) => (
                <span key={i} className="text-[11px] px-2 py-1 rounded-full bg-(--surface-3) text-(--text-secondary)">
                  Line {r.line}: {r.reason}{r.cwe ? ` (${r.cwe})` : ""}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <ChartCard title="Verdict" className="flex flex-col items-center justify-center">
          <VerdictPill verdict={scan.verdict} />
          <div className="mt-3"><RiskBadge level={scan.risk_level} /></div>
          <div className="text-[11px] text-(--text-muted) mt-3 text-center">Model: {scan.model_used}</div>
        </ChartCard>
        <ChartCard title="Vulnerability Probability" className="flex items-center justify-center">
          <Gauge value={scan.vuln_probability} color={scan.risk_color} />
        </ChartCard>
        <ChartCard title="Model Confidence" className="flex items-center justify-center">
          <Gauge value={scan.confidence} color="var(--series-7)" />
        </ChartCard>
        <ChartCard title="Function Stats" className="flex flex-col justify-center gap-2.5">
          <div className="flex justify-between text-xs"><span className="text-(--text-muted)">Lines</span><span className="font-semibold tabular">{scan.lines}</span></div>
          <div className="flex justify-between text-xs"><span className="text-(--text-muted)">LOC</span><span className="font-semibold tabular">{scan.loc}</span></div>
          <div className="flex justify-between text-xs"><span className="text-(--text-muted)">Embedding Dims</span><span className="font-semibold tabular">{scan.embedding_dims}</span></div>
          <div className="flex justify-between text-xs"><span className="text-(--text-muted)">Scanned</span><span className="font-semibold">{timeAgo(scan.created_at)}</span></div>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mt-5">
        <ChartCard title="Why This Verdict" subtitle="Structural insights driving the decision">
          <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
            {insights.length === 0 && <div className="text-xs text-(--text-muted)">No specific insights available.</div>}
            {insights.map(([text, severity], i) => (
              <div key={i} className={`text-xs rounded-lg p-3 border-l-2 ${
                severity === "warning" ? "border-(--status-serious) bg-(--status-serious)/10" :
                severity === "info" ? "border-(--series-1) bg-(--series-1)/10" :
                "border-(--status-good) bg-(--status-good)/10"
              }`}>
                {text}
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Feature Contribution" subtitle="Approximate driver of the prediction (importance × deviation)">
          {detail.contributions ? (
            <ContributionBars contributions={detail.contributions.slice(0, 10)} />
          ) : (
            <div className="text-xs text-(--text-muted) py-10 text-center">Not available in demo mode.</div>
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mt-5">
        <ChartCard title="AST & Metric Signature" subtitle="Structural feature radar (normalised)">
          <FeatureRadar astFeatures={scan.ast_features} metricFeatures={scan.metric_features} />
        </ChartCard>

        <ChartCard title="CodeBERT Embedding Placement" subtitle="This function's semantic position vs. the training set (PCA)">
          {detail.pca_background && scan.embedding_2d ? (
            <EmbeddingScatter background={detail.pca_background.points} current={scan.embedding_2d} explainedVariance={detail.pca_background.explained_variance_ratio} />
          ) : (
            <div className="text-xs text-(--text-muted) py-10 text-center">Embedding projection not available (demo mode).</div>
          )}
        </ChartCard>
      </div>

      {timeline.length > 1 && (
        <div className="mt-5">
          <ChartCard title="Prediction Timeline" subtitle={`Vulnerability probability over time for "${scan.project_name}"`}>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={timeline} margin={{ left: -20, right: 20, top: 10 }}>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
                <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <RTooltip {...chartTooltipStyle} />
                <Line type="monotone" dataKey="probability" name="Vuln Probability %" stroke="#9085e9" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      <div className="mt-5">
        <ChartCard title="Analysed Source" subtitle={scan.filename}>
          <div className="mono text-xs bg-(--surface-3) rounded-lg p-4 overflow-x-auto whitespace-pre">
            {scan.code}
          </div>
          <div className="mt-2 text-xs text-(--text-muted) flex items-center gap-1.5">
            <FileCode2 size={12} /> {detail.line_risks.length} flagged line{detail.line_risks.length !== 1 && "s"} &middot;
            <Link to={`/heatmap?scan=${scanId}`} className="text-(--accent) hover:underline flex items-center gap-1">
              view heatmap <Clock size={11} />
            </Link>
          </div>
        </ChartCard>
      </div>
    </PageShell>
  );
}
