import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ShieldCheck, ScanLine, ArrowRight, FileCode2, Network, BarChart3, Combine, TreePine,
  Flame, Lightbulb, Scale, Clock, FileText, BookOpen, Wand2, FlaskConical, Cpu, LayoutDashboard,
  FolderGit2, Brain, BrainCircuit, CheckCircle2, MonitorPlay,
} from "lucide-react";
import PipelineDiagram from "../components/PipelineDiagram";
import CyberBackground from "../components/CyberBackground";
import { useCountUp } from "../hooks/useCountUp";
import { getDashboardStats, getModelPerformance, type DashboardStats } from "../api/client";

const FEATURES = [
  { icon: LayoutDashboard, label: "Live Dashboard", desc: "Real-time posture across every scan" },
  { icon: ScanLine, label: "Code Scanner", desc: "Paste, upload, or drag in files" },
  { icon: FolderGit2, label: "Project Scanner", desc: "Whole folders & zip archives" },
  { icon: Brain, label: "AI Analysis", desc: "Verdict, confidence, risk breakdown" },
  { icon: BrainCircuit, label: "AI Code Explanation", desc: "Complexity, call graph, CFG, scores" },
  { icon: Flame, label: "Vulnerability Heatmap", desc: "VS Code-style line diagnostics" },
  { icon: Lightbulb, label: "Explainability", desc: "Feature importance & contribution" },
  { icon: Scale, label: "Model Comparison", desc: "XGBoost vs. Random Forest" },
  { icon: Clock, label: "Vulnerability Timeline", desc: "Every scan, chronologically" },
  { icon: FileText, label: "Security Reports", desc: "Professional PDF export" },
  { icon: BookOpen, label: "Knowledge Base", desc: "CWE reference with mitigations" },
  { icon: Wand2, label: "AI Recommendations", desc: "Auto-fix suggestions" },
  { icon: FlaskConical, label: "Research", desc: "Real ROC/PR curves, architecture" },
  { icon: Cpu, label: "System Monitor", desc: "Live CPU, RAM, latency telemetry" },
];

const FORMATS = [".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".zip", "folders"];

export default function Landing() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [perf, setPerf] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    getDashboardStats().then((d) => { if (!cancelled) setStats(d); }).catch(() => {});
    getModelPerformance().then((p) => { if (!cancelled) setPerf(p); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen relative">
      <div className="absolute top-0 left-0 right-0 h-[560px] overflow-hidden pointer-events-none">
        <CyberBackground />
      </div>
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div className="relative flex items-center justify-between px-8 h-16 border-b border-(--border-hairline)">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-(--accent) to-(--series-7) flex items-center justify-center shadow-[0_0_18px_var(--accent-glow)]">
            <ShieldCheck size={18} color="white" strokeWidth={2.4} />
          </div>
          <span className="text-sm font-bold">SecureCode AI</span>
        </div>
        <Link to="/" className="text-xs font-medium text-(--text-secondary) hover:text-(--text-primary) transition-colors">
          Open Dashboard →
        </Link>
      </div>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <div className="relative px-8 pt-20 pb-16 text-center max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-(--surface-2) border border-(--border-hairline) text-xs text-(--text-secondary) mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-(--status-good) animate-pulse-soft" /> Multi-modal AI vulnerability detection
          </div>
          <h1 className="text-5xl font-bold tracking-tight leading-tight">
            AI-Powered Secure Code<br />Analysis Platform
          </h1>
          <p className="text-(--text-secondary) text-base mt-5 max-w-2xl mx-auto leading-relaxed">
            CodeBERT semantic embeddings, AST structural analysis, and software metrics fused into a single
            792-dimensional vector and classified by a trained XGBoost model — with full explainability,
            call graphs, control flow analysis, and CWE-mapped remediation guidance.
          </p>
          <div className="flex items-center justify-center gap-3 mt-8">
            <Link to="/scanner" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-(--accent) text-white text-base font-semibold hover:brightness-110 transition shadow-[0_0_30px_var(--accent-glow)]">
              <ScanLine size={18} /> Start Scan <ArrowRight size={16} />
            </Link>
            <Link to="/" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-(--surface-2) border border-(--border-hairline) text-base font-semibold hover:bg-(--surface-3) transition">
              View Dashboard
            </Link>
            <Link to="/presentation" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-(--surface-2) border border-(--border-hairline) text-base font-semibold hover:bg-(--surface-3) transition">
              <MonitorPlay size={18} /> Presentation Mode
            </Link>
          </div>
        </motion.div>
      </div>

      {/* ── Animated counters ───────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="px-8 pb-16 max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        <Counter value={27225} label="Training Samples" />
        <Counter value={792} label="Feature Dimensions" />
        <Counter value={125} suffix="M" label="CodeBERT Parameters" />
        <Counter value={stats?.total_files_scanned ?? 0} label="Files Scanned (Live)" />
      </motion.div>

      {/* ── Architecture diagram ────────────────────────────────────────── */}
      <Section title="Architecture" subtitle="Three independent branches, fused into one decision">
        <div className="flex flex-col md:flex-row items-center justify-center gap-4 flex-wrap">
          {[
            { icon: Network, label: "AST Branch", desc: "11 structural features", color: "#d55181" },
            { icon: BarChart3, label: "Metrics Branch", desc: "13 quality metrics", color: "#c98500" },
            { icon: Cpu, label: "CodeBERT Branch", desc: "768-dim embedding", color: "#9085e9" },
          ].map((b) => (
            <div key={b.label} className="card p-5 w-52 text-center">
              <div className="w-11 h-11 mx-auto rounded-xl flex items-center justify-center mb-3" style={{ background: `${b.color}1f`, border: `1.5px solid ${b.color}55` }}>
                <b.icon size={20} style={{ color: b.color }} />
              </div>
              <div className="text-sm font-semibold">{b.label}</div>
              <div className="text-xs text-(--text-muted) mt-1">{b.desc}</div>
            </div>
          ))}
          <ArrowRight className="text-(--text-muted) hidden md:block" size={20} />
          <div className="card p-5 w-52 text-center border-(--accent)">
            <div className="w-11 h-11 mx-auto rounded-xl flex items-center justify-center mb-3 bg-(--accent)/15 border border-(--accent)/40">
              <Combine size={20} className="text-(--accent)" />
            </div>
            <div className="text-sm font-semibold">Feature Fusion</div>
            <div className="text-xs text-(--text-muted) mt-1">792-dim concatenated vector</div>
          </div>
          <ArrowRight className="text-(--text-muted) hidden md:block" size={20} />
          <div className="card p-5 w-52 text-center">
            <div className="w-11 h-11 mx-auto rounded-xl flex items-center justify-center mb-3 bg-(--status-good)/15 border border-(--status-good)/40">
              <TreePine size={20} className="text-(--status-good)" />
            </div>
            <div className="text-sm font-semibold">XGBoost Classifier</div>
            <div className="text-xs text-(--text-muted) mt-1">
              {perf?.available ? `${(perf.xgboost.f1 * 100).toFixed(1)}% F1 on held-out test set` : "100 trees, depth 6"}
            </div>
          </div>
        </div>
      </Section>

      {/* ── Pipeline visualization ──────────────────────────────────────── */}
      <Section title="Detection Pipeline" subtitle="What happens to your code, step by step">
        <div className="card p-8 overflow-x-auto">
          <PipelineDiagram />
        </div>
      </Section>

      {/* ── Features grid ───────────────────────────────────────────────── */}
      <Section title="Everything In One Platform" subtitle="Every module, ready to use">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.label}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.35, delay: (i % 4) * 0.05, ease: "easeOut" }}
              className="card card-hover p-4"
            >
              <f.icon size={18} className="text-(--accent) mb-2" />
              <div className="text-sm font-semibold">{f.label}</div>
              <div className="text-xs text-(--text-muted) mt-0.5">{f.desc}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* ── Formats + workflow ───────────────────────────────────────────── */}
      <Section title="Supported Formats & Workflow" subtitle="">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card p-6">
            <div className="text-sm font-semibold mb-3 flex items-center gap-2"><FileCode2 size={15} /> Supported File Formats</div>
            <div className="flex flex-wrap gap-2">
              {FORMATS.map((f) => (
                <span key={f} className="text-xs font-mono px-2.5 py-1 rounded-full bg-(--surface-3) text-(--text-secondary)">{f}</span>
              ))}
            </div>
          </div>
          <div className="card p-6">
            <div className="text-sm font-semibold mb-3">Security Workflow</div>
            <ol className="space-y-2">
              {["Upload code, a folder, or a zip archive", "Automatic AST + metrics + CodeBERT extraction", "XGBoost classification with confidence scoring", "Line-level heatmap & CWE-mapped explanation", "Auto-suggested secure rewrite & PDF report"].map((step, i) => (
                <li key={i} className="flex items-start gap-2.5 text-xs text-(--text-secondary)">
                  <CheckCircle2 size={14} className="text-(--status-good) shrink-0 mt-0.5" /> {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </Section>

      {/* ── Final CTA ────────────────────────────────────────────────────── */}
      <div className="px-8 py-20 text-center">
        <Link to="/scanner" className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-(--accent) text-white text-lg font-semibold hover:brightness-110 transition shadow-[0_0_30px_var(--accent-glow)]">
          <ScanLine size={20} /> Start Scan <ArrowRight size={18} />
        </Link>
        <div className="text-xs text-(--text-muted) mt-4">No signup. Runs entirely on the existing trained models.</div>
      </div>
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="px-8 py-12 max-w-6xl mx-auto border-t border-(--border-hairline)">
      <motion.div
        className="text-center mb-8"
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        <h2 className="text-2xl font-bold">{title}</h2>
        {subtitle && <p className="text-sm text-(--text-muted) mt-1.5">{subtitle}</p>}
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.45, delay: 0.08, ease: "easeOut" }}
      >
        {children}
      </motion.div>
    </div>
  );
}

function Counter({ value, suffix = "", label }: { value: number; suffix?: string; label: string }) {
  const animated = useCountUp(value);
  return (
    <div className="card card-hover p-5 text-center">
      <div className="text-3xl font-bold tabular text-(--text-primary)">{Math.round(animated).toLocaleString("en-US")}{suffix}</div>
      <div className="text-xs text-(--text-muted) mt-1 uppercase tracking-wider">{label}</div>
    </div>
  );
}
