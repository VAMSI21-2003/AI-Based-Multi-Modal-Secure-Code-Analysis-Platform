import { useEffect, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import EmbeddingScatter from "../components/EmbeddingScatter";
import { getAnalyticsOverview, getModelPerformance, getDatasetStats, getPcaBackground } from "../api/client";
import { RISK_HEX, RISK_ORDER } from "../utils/risk";

const SERIES = ["#3987e5", "#008300", "#d55181", "#c98500", "#199e70", "#d95926", "#9085e9", "#e66767"];

export default function Analytics() {
  const [overview, setOverview] = useState<any>(null);
  const [modelPerf, setModelPerf] = useState<any>(null);
  const [datasetStats, setDatasetStats] = useState<any>(null);
  const [pca, setPca] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    getAnalyticsOverview().then((o) => { if (!cancelled) setOverview(o); });
    getModelPerformance().then((p) => { if (!cancelled) setModelPerf(p); });
    getDatasetStats().then((d) => { if (!cancelled) setDatasetStats(d); });
    getPcaBackground().then((p) => { if (!cancelled) setPca(p); });
    return () => { cancelled = true; };
  }, []);

  if (!overview || !modelPerf || !datasetStats) {
    return <PageShell title="Project Analytics" subtitle="Trends, distributions & model performance"><Spinner label="Crunching analytics..." /></PageShell>;
  }

  const modelBarData = ["accuracy", "precision", "recall", "f1"].map((metric) => ({
    metric: metric[0].toUpperCase() + metric.slice(1),
    "Random Forest": modelPerf.available ? Math.round((modelPerf.random_forest?.[metric] ?? 0) * 1000) / 10 : 0,
    XGBoost: modelPerf.available ? Math.round((modelPerf.xgboost?.[metric] ?? 0) * 1000) / 10 : 0,
  }));

  const riskPie = RISK_ORDER.filter((k) => overview.risk_distribution[k]).map((k) => ({ name: k, value: overview.risk_distribution[k] }));
  const sourcePie = Object.entries(overview.source_distribution || {}).map(([k, v]) => ({ name: k, value: v as number }));

  return (
    <PageShell title="Project Analytics" subtitle="Trends, distributions, dataset stats & model performance">
      {modelPerf.available && (
        <ChartCard title="Model Performance" subtitle="Trained classifier benchmarks (Devign test set) — read-only, from the existing trained models" className="mb-5">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={modelBarData} margin={{ left: -20, right: 10 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis dataKey="metric" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <RTooltip {...chartTooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
              <Bar dataKey="Random Forest" fill={SERIES[4]} radius={[4, 4, 0, 0]} />
              <Bar dataKey="XGBoost" fill={SERIES[0]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-center">
            <Stat label="Training Samples" value={modelPerf.n_samples?.toLocaleString("en-US")} />
            <Stat label="Total Features" value={modelPerf.n_features} />
            <Stat label="AST + Metrics + Embeddings" value="11 + 13 + 768" />
            <Stat label="Test Split" value={`${modelPerf.n_test} samples`} />
          </div>
        </ChartCard>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Live Scan Risk Distribution">
          {riskPie.length === 0 ? <EmptyChart /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={riskPie} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2} strokeWidth={2} stroke="var(--surface-2)">
                  {riskPie.map((d) => <Cell key={d.name} fill={RISK_HEX[d.name]} />)}
                </Pie>
                <RTooltip {...chartTooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Scan Source Breakdown">
          {sourcePie.length === 0 ? <EmptyChart /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={sourcePie} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2} strokeWidth={2} stroke="var(--surface-2)">
                  {sourcePie.map((d, i) => <Cell key={d.name} fill={SERIES[i % SERIES.length]} />)}
                </Pie>
                <RTooltip {...chartTooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Top CWE Frequency" subtitle="Across all vulnerable scans">
          {overview.cwe_frequency.length === 0 ? <EmptyChart /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={overview.cwe_frequency} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid stroke="var(--gridline)" horizontal={false} />
                <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="cwe" width={70} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <RTooltip {...chartTooltipStyle} />
                <Bar dataKey="count" fill="#d95926" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ChartCard title="Training Dataset Composition" subtitle="Devign benchmark (existing, unmodified)">
          {datasetStats.available ? (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={[{ name: "Vulnerable", value: datasetStats.vulnerable }, { name: "Safe", value: datasetStats.safe }]}
                    dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2} strokeWidth={2} stroke="var(--surface-2)"
                  >
                    <Cell fill="#d03b3b" />
                    <Cell fill="#0ca30c" />
                  </Pie>
                  <RTooltip {...chartTooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="text-center text-xs text-(--text-muted)">{datasetStats.total_functions.toLocaleString("en-US")} total functions (FFmpeg + QEMU)</div>
            </>
          ) : <EmptyChart />}
        </ChartCard>

        <ChartCard title="CodeBERT Embedding Space" subtitle="2D PCA projection of the full training set">
          {pca?.available ? <EmbeddingScatter background={pca.points} current={null} explainedVariance={pca.explained_variance_ratio} /> : <EmptyChart />}
        </ChartCard>
      </div>
    </PageShell>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
      <div className="text-sm font-bold mt-0.5">{value}</div>
    </div>
  );
}

function EmptyChart() {
  return <div className="h-[220px] flex items-center justify-center text-sm text-(--text-muted)">Not enough data yet</div>;
}
