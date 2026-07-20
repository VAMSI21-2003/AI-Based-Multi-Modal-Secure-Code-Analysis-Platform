import { useEffect, useState } from "react";
import { Cpu, Layers, Database } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  BarChart, Bar, ReferenceLine,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import { getEvalCurves, getModelArchitecture, type EvalCurves, type ModelArchitecture } from "../api/client";

type ModelKey = "xgboost" | "random_forest";

export default function Research() {
  const [curves, setCurves] = useState<EvalCurves | null>(null);
  const [arch, setArch] = useState<ModelArchitecture | null>(null);
  const [model, setModel] = useState<ModelKey>("xgboost");

  useEffect(() => {
    getEvalCurves().then(setCurves);
    getModelArchitecture().then(setArch);
  }, []);

  if (!curves || !arch) {
    return <PageShell title="Research" subtitle="Model architecture, dataset & evaluation"><Spinner label="Loading research data..." /></PageShell>;
  }

  const evalData = curves.available ? curves[model] : undefined;
  const cm = evalData?.confusion_matrix;
  const rocData = evalData?.roc_curve.fpr.map((f, i) => ({ fpr: f, tpr: evalData.roc_curve.tpr[i] })) ?? [];
  const prData = evalData?.pr_curve.recall.map((r, i) => ({ recall: r, precision: evalData.pr_curve.precision[i] })) ?? [];
  const training = arch.training;

  return (
    <PageShell title="Research" subtitle="Model architecture, dataset statistics, and evaluation — reproduced from the existing trained models (no retraining)">
      {/* ── Architecture cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        <ChartCard title="CodeBERT" subtitle={<span className="flex items-center gap-1.5"><Cpu size={12} /> microsoft/codebert-base</span>}>
          <FactRow label="Parameters" value={arch.codebert.parameters ? `${(arch.codebert.parameters / 1e6).toFixed(1)}M` : "—"} />
          <FactRow label="Transformer Layers" value={arch.codebert.layers} />
          <FactRow label="Hidden Size" value={arch.codebert.hidden_size} />
          <FactRow label="Attention Heads" value={arch.codebert.attention_heads} />
          <FactRow label="Max Sequence Length" value={arch.codebert.max_sequence_length} />
        </ChartCard>

        <ChartCard title="XGBoost" subtitle={<span className="flex items-center gap-1.5"><Layers size={12} /> Gradient-boosted trees</span>}>
          {arch.xgboost ? <>
            <FactRow label="Estimators (Trees)" value={arch.xgboost.n_estimators} />
            <FactRow label="Max Depth" value={arch.xgboost.max_depth ?? "—"} />
            <FactRow label="Learning Rate (eta)" value={arch.xgboost.learning_rate ?? "—"} />
            <FactRow label="Total Trees (saved)" value={arch.xgboost.total_trees} />
          </> : <div className="text-xs text-(--text-muted)">Model not available.</div>}
        </ChartCard>

        <ChartCard title="Random Forest" subtitle={<span className="flex items-center gap-1.5"><Layers size={12} /> Bagged decision trees</span>}>
          {arch.random_forest ? <>
            <FactRow label="Estimators (Trees)" value={arch.random_forest.n_estimators} />
            <FactRow label="Max Depth" value={arch.random_forest.max_depth ?? "Unbounded"} />
            <FactRow label="Total Nodes" value={arch.random_forest.total_nodes.toLocaleString("en-US")} />
          </> : <div className="text-xs text-(--text-muted)">Model not available.</div>}
        </ChartCard>
      </div>

      {/* ── Feature pipeline + dataset ───────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Feature Pipeline Dimensions" subtitle={<span className="flex items-center gap-1.5"><Layers size={12} /> Early fusion, concatenated vector</span>}>
          <FactRow label="AST Structural Features" value={arch.feature_pipeline.ast_dimensions} />
          <FactRow label="Software Metrics" value={arch.feature_pipeline.metrics_dimensions} />
          <FactRow label="CodeBERT Embedding" value={arch.feature_pipeline.embedding_dimensions} />
          <FactRow label="Total Fused Vector" value={arch.feature_pipeline.total_dimensions} bold />
        </ChartCard>

        <ChartCard title="Dataset & Training Statistics" subtitle={<span className="flex items-center gap-1.5"><Database size={12} /> Devign benchmark (FFmpeg + QEMU)</span>}>
          {training ? <>
            <FactRow label="Total Samples" value={training.n_samples.toLocaleString("en-US")} />
            <FactRow label="Training Set" value={training.n_train.toLocaleString("en-US")} />
            <FactRow label="Test Set" value={training.n_test.toLocaleString("en-US")} />
            <FactRow label="Test Split" value={`${(training.test_size * 100).toFixed(0)}%`} />
            <FactRow label="Random Seed" value={training.random_state} />
          </> : <div className="text-xs text-(--text-muted)">Training metadata not available.</div>}
        </ChartCard>

        <ChartCard title="Training Configuration" subtitle={<span className="flex items-center gap-1.5"><Cpu size={12} /> Split methodology & wall-clock time</span>}>
          {training ? <>
            <FactRow label="Split Method" value="Stratified (class ratio preserved)" />
            <FactRow label="Trees per Model" value={training.n_estimators} />
            <FactRow label="XGBoost Train Time" value={`${training.xgboost.train_time}s`} />
            <FactRow label="Random Forest Train Time" value={`${training.random_forest.train_time}s`} />
          </> : <div className="text-xs text-(--text-muted)">Training metadata not available.</div>}
        </ChartCard>
      </div>

      {/* ── Model toggle ─────────────────────────────────────────────────── */}
      <div className="flex gap-2 mb-5">
        {(["xgboost", "random_forest"] as ModelKey[]).map((m) => (
          <button
            key={m}
            onClick={() => setModel(m)}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              model === m ? "bg-(--surface-3) border-(--border-hairline-strong)" : "border-(--border-hairline) text-(--text-muted) hover:bg-(--surface-2)"
            }`}
          >
            {m === "xgboost" ? "XGBoost" : "Random Forest"}
          </button>
        ))}
        {curves.test_set_size && (
          <span className="ml-auto self-center text-xs text-(--text-muted)">
            Evaluated on {curves.test_set_size.toLocaleString("en-US")} held-out test samples ({curves.test_set_vulnerable} vulnerable / {curves.test_set_safe} safe)
          </span>
        )}
      </div>

      {!curves.available || !evalData ? (
        <div className="card p-4 text-sm text-(--status-warning) mb-5">Evaluation curves not available.</div>
      ) : (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
            <ChartCard title="Confusion Matrix" subtitle="Held-out test set">
              {cm && <ConfusionMatrix cm={cm} />}
            </ChartCard>

            <ChartCard title="ROC Curve" subtitle={`AUC = ${evalData.roc_curve.auc}`}>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={rocData} margin={{ left: -15, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--gridline)" />
                  <XAxis dataKey="fpr" type="number" domain={[0, 1]} tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} label={{ value: "False Positive Rate", position: "insideBottom", offset: -5, fill: "var(--text-muted)", fontSize: 10 }} />
                  <YAxis dataKey="tpr" type="number" domain={[0, 1]} tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RTooltip {...chartTooltipStyle} formatter={(v: any) => Number(v).toFixed(3)} />
                  <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--baseline)" strokeDasharray="4 3" />
                  <Line type="monotone" dataKey="tpr" stroke="#3987e5" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Precision-Recall Curve" subtitle="Held-out test set">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={prData} margin={{ left: -15, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--gridline)" />
                  <XAxis dataKey="recall" type="number" domain={[0, 1]} tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} label={{ value: "Recall", position: "insideBottom", offset: -5, fill: "var(--text-muted)", fontSize: 10 }} />
                  <YAxis dataKey="precision" type="number" domain={[0, 1]} tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RTooltip {...chartTooltipStyle} formatter={(v: any) => Number(v).toFixed(3)} />
                  <Line type="monotone" dataKey="precision" stroke="#9085e9" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <ChartCard title="Global Feature Importance" subtitle="Top 20 features, model-wide (not per-scan)">
            <ResponsiveContainer width="100%" height={420}>
              <BarChart data={evalData.feature_importances_top20.slice().reverse()} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid stroke="var(--gridline)" horizontal={false} />
                <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
                <YAxis type="category" dataKey="feature" width={110} tick={{ fill: "var(--text-secondary)", fontSize: 10 }} axisLine={false} tickLine={false} />
                <RTooltip {...chartTooltipStyle} />
                <Bar dataKey="importance" fill="#3987e5" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {evalData.ablation && (
            <ChartCard
              title="Ablation Study"
              subtitle="Feature-block masking on the held-out test set, using the SAME trained model (no retraining)"
              className="mt-5"
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={evalData.ablation} margin={{ left: -10, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--gridline)" vertical={false} />
                  <XAxis dataKey="config" tick={{ fill: "var(--text-muted)", fontSize: 9.5 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} interval={0} angle={-12} textAnchor="end" height={70} />
                  <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                  <RTooltip {...chartTooltipStyle} formatter={(v: any) => Number(v).toFixed(3)} />
                  <Bar dataKey="f1" name="F1 Score" fill="#9085e9" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="text-[11px] text-(--text-muted) mt-2 leading-relaxed">
                Each bar zeroes out all feature dimensions <em>outside</em> the named block and re-runs the existing model on the test set --
                it measures how much each modality's information contributes to the model's actual decisions, not the performance of an
                independently-trained single-modality model (this pipeline only ever trains one fused-feature model). A masked configuration
                scoring above or below the full model is a genuine property of how the tree splits combine features, not measurement noise.
              </div>
            </ChartCard>
          )}
        </>
      )}
    </PageShell>
  );
}

function FactRow({ label, value, bold = false }: { label: string; value: any; bold?: boolean }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-(--border-hairline) last:border-0 text-xs">
      <span className="text-(--text-muted)">{label}</span>
      <span className={`tabular ${bold ? "font-bold text-sm" : "font-semibold"}`}>{value}</span>
    </div>
  );
}

function ConfusionMatrix({ cm }: { cm: { tn: number; fp: number; fn: number; tp: number } }) {
  const total = cm.tn + cm.fp + cm.fn + cm.tp;
  const cell = (label: string, value: number, color: string) => (
    <div className="rounded-lg p-4 text-center" style={{ background: `${color}1f`, border: `1px solid ${color}55` }}>
      <div className="text-2xl font-bold tabular" style={{ color }}>{value}</div>
      <div className="text-[10px] text-(--text-muted) mt-1">{label}</div>
      <div className="text-[10px] text-(--text-muted)">{((value / total) * 100).toFixed(1)}%</div>
    </div>
  );
  return (
    <div>
      <div className="grid grid-cols-2 gap-2">
        {cell("True Negative", cm.tn, "#0ca30c")}
        {cell("False Positive", cm.fp, "#ec835a")}
        {cell("False Negative", cm.fn, "#d03b3b")}
        {cell("True Positive", cm.tp, "#3987e5")}
      </div>
      <div className="grid grid-cols-2 text-center text-[10px] text-(--text-muted) mt-1.5">
        <span>Predicted Safe</span><span>Predicted Vulnerable</span>
      </div>
    </div>
  );
}
