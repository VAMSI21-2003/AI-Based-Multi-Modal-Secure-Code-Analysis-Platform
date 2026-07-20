import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileCode2, Hash, Cpu, Network, BarChart3, Combine, TreePine, Target, FileText,
  Play, Pause, SkipBack, SkipForward, Download,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import { VerdictPill } from "../components/RiskBadge";
import { useActiveScan } from "../hooks/useActiveScan";
import { getCodeIntelligence, downloadScanPdf, type CodeIntelligence } from "../api/client";

const AUTOPLAY_MS = 2600;

export default function ExecutionFlow() {
  const { scanId, scan, detail, loading } = useActiveScan();
  const [intel, setIntel] = useState<CodeIntelligence | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => { if (scanId) getCodeIntelligence(scanId).then(setIntel); }, [scanId]);

  const stages = scan && detail && intel ? [
    {
      icon: FileCode2, color: "#3987e5", title: "Source Code",
      detail: `${scan.filename} — ${scan.lines} lines, ${scan.code?.length ?? 0} characters`,
    },
    {
      icon: Hash, color: "#199e70", title: "Tokenizer",
      detail: `Code split into BPE tokens (max 512, truncated/padded) for CodeBERT's vocabulary`,
    },
    {
      icon: Cpu, color: "#9085e9", title: "CodeBERT",
      detail: `125M-parameter transformer produces a ${scan.embedding_dims}-dim [CLS] embedding${scan.embedding_2d ? ` — placed at (${scan.embedding_2d.x.toFixed(2)}, ${scan.embedding_2d.y.toFixed(2)}) in PCA space` : ""}`,
    },
    {
      icon: Network, color: "#d55181", title: "AST",
      detail: `tree-sitter parse produces ${intel.functions.length} function(s), ${scan.ast_features.n_total_nodes} AST nodes, max depth ${scan.ast_features.max_depth}`,
    },
    {
      icon: BarChart3, color: "#c98500", title: "Software Metrics",
      detail: `${scan.metric_features.loc} LOC, nesting depth ${scan.metric_features.nesting_depth}, ${scan.metric_features.pointer_count} pointer tokens`,
    },
    {
      icon: Combine, color: "#d95926", title: "Feature Fusion",
      detail: `11 AST + 13 Metrics + 768 CodeBERT = 792-dim fused vector`,
    },
    {
      icon: TreePine, color: "#3987e5", title: scan.model_used,
      detail: `${scan.is_demo ? "Heuristic fallback (no trained model)" : "Trained classifier"} scores the fused vector`,
    },
    {
      icon: Target, color: scan.risk_color, title: "Prediction",
      detail: `${scan.verdict} — ${scan.vuln_probability.toFixed(1)}% probability, ${scan.confidence.toFixed(1)}% confidence (${scan.risk_level})`,
    },
    {
      icon: FileText, color: "#0ca30c", title: "Security Report",
      detail: `${detail.line_risks.length} line-level finding(s), ${detail.recommendations.length} recommendation panel(s) generated`,
    },
  ] : [];

  useEffect(() => {
    if (!playing || stages.length === 0) return;
    const id = setInterval(() => {
      setStep((s) => {
        if (s + 1 >= stages.length) return s;
        return s + 1;
      });
    }, AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [playing, stages.length]);

  useEffect(() => {
    if (stages.length > 0 && step === stages.length - 1) setPlaying(false);
  }, [step, stages.length]);

  if (!scanId) {
    return (
      <PageShell title="Execution Flow Visualizer" subtitle="Watch a real scan move through the pipeline, stage by stage">
        <ScanPickerEmpty icon={Cpu} title="No scan selected" description="Run a scan to replay its actual pipeline execution with real numbers at every stage." />
      </PageShell>
    );
  }

  if (loading || !scan || !detail || !intel || stages.length === 0) {
    return (
      <PageShell title="Execution Flow Visualizer" subtitle="Loading">
        <Spinner label="Assembling pipeline trace..." />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Execution Flow Visualizer"
      subtitle={`${scan.filename} — real pipeline trace for this scan`}
      actions={<a href={downloadScanPdf(scanId!)} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110"><Download size={13} /> Security Report</a>}
    >
      <ChartCard title="Pipeline Trace">
        <div className="flex flex-wrap items-center justify-center gap-1 mb-8">
          {stages.map((s, i) => (
            <div key={i} className="flex items-center">
              <button
                onClick={() => setStep(i)}
                className="w-11 h-11 rounded-xl flex items-center justify-center transition-all"
                style={{
                  background: i <= step ? `${s.color}2a` : "var(--surface-3)",
                  border: `1.5px solid ${i <= step ? s.color : "var(--border-hairline)"}`,
                  opacity: i <= step ? 1 : 0.4,
                  transform: i === step ? "scale(1.15)" : "scale(1)",
                }}
              >
                <s.icon size={18} style={{ color: i <= step ? s.color : "var(--text-muted)" }} />
              </button>
              {i < stages.length - 1 && <div className="w-5 h-[2px]" style={{ background: i < step ? stages[i].color : "var(--border-hairline)" }} />}
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
            className="text-center max-w-xl mx-auto"
          >
            <div className="text-lg font-bold" style={{ color: stages[step].color }}>{stages[step].title}</div>
            <p className="text-sm text-(--text-secondary) mt-2">{stages[step].detail}</p>
            {step === stages.length - 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <VerdictPill verdict={scan.verdict} />
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        <div className="flex items-center justify-center gap-3 mt-8">
          <button onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30"><SkipBack size={16} /></button>
          <button onClick={() => setPlaying((p) => !p)} className="px-5 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold flex items-center gap-2 hover:brightness-110">
            {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? "Pause" : "Play"}
          </button>
          <button onClick={() => setStep((s) => Math.min(stages.length - 1, s + 1))} disabled={step === stages.length - 1} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30"><SkipForward size={16} /></button>
          <span className="text-xs text-(--text-muted) tabular ml-2">Stage {step + 1} / {stages.length}</span>
        </div>
      </ChartCard>

      <div className="text-center mt-4">
        <Link to={`/analysis?scan=${scanId}`} className="text-xs text-(--accent) hover:underline">View full analysis →</Link>
      </div>
    </PageShell>
  );
}
