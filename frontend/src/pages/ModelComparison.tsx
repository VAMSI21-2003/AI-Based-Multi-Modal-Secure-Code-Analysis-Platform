import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Scale, CheckCircle2, XCircle } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Legend } from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import ProgressBar from "../components/ProgressBar";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import { VerdictPill } from "../components/RiskBadge";
import { getModelComparison, type ModelComparison as ModelComparisonT } from "../api/client";

export default function ModelComparison() {
  const [params] = useSearchParams();
  const scanId = params.get("scan");
  const [data, setData] = useState<ModelComparisonT | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getModelComparison(scanId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to compare models"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="Model Comparison" subtitle="Random Forest vs. XGBoost, side by side">
        <ScanPickerEmpty icon={Scale} title="No scan selected" description="Run a scan to compare how both trained models score the same function." />
      </PageShell>
    );
  }

  if (loading || !data) {
    return (
      <PageShell title="Model Comparison" subtitle="Random Forest vs. XGBoost">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Running both models..." />}
      </PageShell>
    );
  }

  if (!data.available) {
    return (
      <PageShell title="Model Comparison" subtitle="Random Forest vs. XGBoost">
        <div className="card p-4 text-sm text-(--status-warning)">{data.error || "Comparison unavailable for this scan."}</div>
      </PageShell>
    );
  }

  const chartData = [
    {
      name: "Vulnerability Probability",
      XGBoost: data.xgboost?.vuln_probability ?? 0,
      "Random Forest": data.random_forest?.vuln_probability ?? 0,
    },
    {
      name: "Confidence",
      XGBoost: data.xgboost?.confidence ?? 0,
      "Random Forest": data.random_forest?.confidence ?? 0,
    },
  ];

  return (
    <PageShell title="Model Comparison" subtitle="Both trained models scored against the same function">
      <div className="mb-5">
        <div className={`card p-4 flex items-center gap-3 ${data.agreement ? "border-(--status-good)" : "border-(--status-warning)"}`}>
          {data.agreement ? <CheckCircle2 className="text-(--status-good)" size={22} /> : <XCircle className="text-(--status-warning)" size={22} />}
          <div>
            <div className="text-sm font-semibold">{data.agreement ? "Models Agree" : "Models Disagree"}</div>
            <div className="text-xs text-(--text-muted)">
              {data.agreement
                ? "Both classifiers reached the same verdict for this function."
                : "The two classifiers reached different verdicts — treat this function with extra caution and review manually."}
              {data.probability_diff !== null && ` Probability difference: ${data.probability_diff} percentage points.`}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        <ModelCard name="XGBoost" accent="var(--series-1)" result={data.xgboost} />
        <ModelCard name="Random Forest" accent="var(--series-5)" result={data.random_forest} />
      </div>

      <ChartCard title="Side-by-Side Comparison" subtitle="Probability and confidence, both models">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ left: -10, right: 10, top: 10 }}>
            <CartesianGrid stroke="var(--gridline)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
            <RTooltip {...chartTooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
            <Bar dataKey="XGBoost" fill="#3987e5" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Random Forest" fill="#199e70" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </PageShell>
  );
}

function ModelCard({ name, accent, result }: { name: string; accent: string; result: any }) {
  if (!result?.available) {
    return (
      <div className="card p-5">
        <div className="text-sm font-semibold mb-2">{name}</div>
        <div className="text-xs text-(--text-muted)">Model not available.</div>
      </div>
    );
  }
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold" style={{ color: accent }}>{name}</div>
        <VerdictPill verdict={result.verdict} />
      </div>
      <div className="space-y-3">
        <ProgressBar value={result.vuln_probability} color={accent} label="Vulnerability Probability" />
        <ProgressBar value={result.confidence} color="var(--series-7)" label="Confidence" />
      </div>
    </div>
  );
}
