import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play, Pause, ChevronLeft, ChevronRight, ShieldCheck, Cpu, Network, BarChart3, Combine, TreePine,
  Target, BookOpen, Wand2, ArrowRight, X,
} from "lucide-react";
import PipelineDiagram from "../components/PipelineDiagram";
import CyberBackground from "../components/CyberBackground";
import Gauge from "../components/Gauge";
import EmbeddingScatter from "../components/EmbeddingScatter";
import { VerdictPill } from "../components/RiskBadge";
import { useCountUp } from "../hooks/useCountUp";
import { getDashboardStats, getScan, getScanDetail, getModelPerformance, type ScanResult, type ScanDetail } from "../api/client";

const AUTOPLAY_MS = 7000;

export default function Presentation() {
  const [slide, setSlide] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [latestScan, setLatestScan] = useState<ScanResult | null>(null);
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [perf, setPerf] = useState<any>(null);

  useEffect(() => {
    getDashboardStats().then((d) => {
      if (d.recent_scans.length > 0) {
        const id = d.recent_scans[0].id;
        getScan(id).then(setLatestScan);
        getScanDetail(id).then(setDetail);
      }
    });
    getModelPerformance().then(setPerf);
  }, []);

  const slides = [
    "title", "architecture", "pipeline", "prediction", "explanation", "visualization", "modules", "close",
  ];

  const next = useCallback(() => setSlide((s) => Math.min(slides.length - 1, s + 1)), [slides.length]);
  const prev = useCallback(() => setSlide((s) => Math.max(0, s - 1)), []);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setSlide((s) => (s + 1 >= slides.length ? s : s + 1)), AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [playing, slides.length]);

  useEffect(() => {
    if (slide === slides.length - 1) setPlaying(false);
  }, [slide, slides.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  return (
    <div className="min-h-screen flex flex-col bg-(--surface-0) relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"><CyberBackground /></div>
      <div className="relative flex items-center justify-between px-6 h-14 border-b border-(--border-hairline)">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck size={16} className="text-(--accent)" /> SecureCode AI — Presentation Mode
        </div>
        <Link to="/welcome" className="text-(--text-muted) hover:text-(--text-primary)"><X size={18} /></Link>
      </div>

      <div className="flex-1 flex items-center justify-center px-8 py-10">
        <AnimatePresence mode="wait">
          <motion.div key={slide} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.4 }} className="w-full max-w-4xl">
            {slides[slide] === "title" && <TitleSlide />}
            {slides[slide] === "architecture" && <ArchitectureSlide perf={perf} />}
            {slides[slide] === "pipeline" && <PipelineSlide />}
            {slides[slide] === "prediction" && <PredictionSlide scan={latestScan} />}
            {slides[slide] === "explanation" && <ExplanationSlide scan={latestScan} detail={detail} />}
            {slides[slide] === "visualization" && <VisualizationSlide scan={latestScan} detail={detail} />}
            {slides[slide] === "modules" && <ModulesSlide />}
            {slides[slide] === "close" && <CloseSlide />}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="flex items-center justify-center gap-3 pb-8">
        <button onClick={prev} disabled={slide === 0} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30"><ChevronLeft size={18} /></button>
        <button onClick={() => setPlaying((p) => !p)} className="px-5 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold flex items-center gap-2 hover:brightness-110">
          {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? "Pause" : "Play"}
        </button>
        <button onClick={next} disabled={slide === slides.length - 1} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30"><ChevronRight size={18} /></button>
        <div className="flex gap-1.5 ml-3">
          {slides.map((_, i) => (
            <button key={i} onClick={() => setSlide(i)} className="w-2 h-2 rounded-full transition-all" style={{ background: i === slide ? "var(--accent)" : "var(--surface-3)", width: i === slide ? 20 : 8 }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SlideTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-2xl font-bold text-center mb-8">{children}</h2>;
}

function TitleSlide() {
  return (
    <div className="text-center">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-(--accent) to-(--series-7) flex items-center justify-center mb-6 shadow-[0_0_40px_var(--accent-glow)]">
        <ShieldCheck size={30} color="white" />
      </div>
      <h1 className="text-4xl font-bold">SecureCode AI</h1>
      <p className="text-(--text-secondary) mt-3 text-lg">AI-Powered Secure Code Analysis Platform</p>
      <div className="grid grid-cols-3 gap-4 mt-10 max-w-lg mx-auto">
        <Counter value={27225} label="Training Samples" />
        <Counter value={792} label="Feature Dims" />
        <Counter value={125} suffix="M" label="CodeBERT Params" />
      </div>
    </div>
  );
}

function Counter({ value, suffix = "", label }: { value: number; suffix?: string; label: string }) {
  const animated = useCountUp(value);
  return (
    <div className="card p-4">
      <div className="text-2xl font-bold tabular">{Math.round(animated).toLocaleString("en-US")}{suffix}</div>
      <div className="text-[10px] text-(--text-muted) uppercase tracking-wider mt-1">{label}</div>
    </div>
  );
}

function ArchitectureSlide({ perf }: { perf: any }) {
  const branches = [
    { icon: Network, label: "AST Branch", desc: "11 structural features", color: "#d55181" },
    { icon: BarChart3, label: "Metrics Branch", desc: "13 quality metrics", color: "#c98500" },
    { icon: Cpu, label: "CodeBERT Branch", desc: "768-dim embedding", color: "#9085e9" },
  ];
  return (
    <div>
      <SlideTitle>Multi-Modal Architecture</SlideTitle>
      <div className="flex flex-wrap items-center justify-center gap-4">
        {branches.map((b) => (
          <div key={b.label} className="card p-5 w-44 text-center">
            <div className="w-10 h-10 mx-auto rounded-xl flex items-center justify-center mb-2" style={{ background: `${b.color}1f`, border: `1.5px solid ${b.color}55` }}>
              <b.icon size={18} style={{ color: b.color }} />
            </div>
            <div className="text-sm font-semibold">{b.label}</div>
            <div className="text-[11px] text-(--text-muted)">{b.desc}</div>
          </div>
        ))}
        <ArrowRight className="text-(--text-muted)" />
        <div className="card p-5 w-44 text-center border-(--accent)">
          <Combine size={18} className="mx-auto text-(--accent) mb-2" />
          <div className="text-sm font-semibold">Feature Fusion</div>
          <div className="text-[11px] text-(--text-muted)">792-dim vector</div>
        </div>
        <ArrowRight className="text-(--text-muted)" />
        <div className="card p-5 w-44 text-center">
          <TreePine size={18} className="mx-auto text-(--status-good) mb-2" />
          <div className="text-sm font-semibold">XGBoost</div>
          <div className="text-[11px] text-(--text-muted)">{perf?.available ? `F1 = ${(perf.xgboost.f1 * 100).toFixed(1)}%` : "100 trees"}</div>
        </div>
      </div>
    </div>
  );
}

function PipelineSlide() {
  return (
    <div>
      <SlideTitle>Detection Pipeline</SlideTitle>
      <div className="card p-6 overflow-x-auto"><PipelineDiagram compact /></div>
    </div>
  );
}

function PredictionSlide({ scan }: { scan: ScanResult | null }) {
  if (!scan) return <div className="text-center text-(--text-muted)">Run a scan to see a live prediction here.</div>;
  return (
    <div>
      <SlideTitle>Live Prediction</SlideTitle>
      <div className="text-center mb-4">
        <div className="text-sm mono text-(--text-muted)">{scan.filename}</div>
        <div className="mt-2"><VerdictPill verdict={scan.verdict} /></div>
      </div>
      <div className="flex justify-center gap-8">
        <Gauge value={scan.vuln_probability} color={scan.risk_color} label="Risk" />
        <Gauge value={scan.confidence} color="var(--series-7)" label="Confidence" />
      </div>
    </div>
  );
}

function ExplanationSlide({ scan, detail }: { scan: ScanResult | null; detail: ScanDetail | null }) {
  if (!scan || !detail) return <div className="text-center text-(--text-muted)">No scan available yet.</div>;
  return (
    <div>
      <SlideTitle>Why This Verdict</SlideTitle>
      <div className="space-y-2 max-w-xl mx-auto">
        {detail.insights.slice(0, 4).map(([text, sev], i) => (
          <div key={i} className={`text-sm rounded-lg p-3 border-l-2 ${sev === "warning" ? "border-(--status-serious) bg-(--status-serious)/10" : "border-(--series-1) bg-(--series-1)/10"}`}>{text}</div>
        ))}
        {detail.insights.length === 0 && <div className="text-center text-(--text-muted) text-sm">No specific structural warnings for this function.</div>}
      </div>
    </div>
  );
}

function VisualizationSlide({ scan, detail }: { scan: ScanResult | null; detail: ScanDetail | null }) {
  if (!detail?.pca_background) return <div className="text-center text-(--text-muted)">Embedding visualization unavailable.</div>;
  return (
    <div>
      <SlideTitle>Semantic Embedding Space</SlideTitle>
      <EmbeddingScatter background={detail.pca_background.points} current={scan?.embedding_2d ?? null} explainedVariance={detail.pca_background.explained_variance_ratio} />
    </div>
  );
}

function ModulesSlide() {
  const items = [
    { icon: Target, label: "20+ Analysis Modules" }, { icon: BookOpen, label: "CWE Knowledge Base" }, { icon: Wand2, label: "Auto-Fix Suggestions" },
  ];
  return (
    <div>
      <SlideTitle>A Complete Platform</SlideTitle>
      <div className="grid grid-cols-3 gap-4 max-w-lg mx-auto">
        {items.map((it) => (
          <div key={it.label} className="card p-5 text-center">
            <it.icon size={22} className="mx-auto text-(--accent) mb-2" />
            <div className="text-xs font-medium">{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CloseSlide() {
  return (
    <div className="text-center">
      <h2 className="text-3xl font-bold mb-4">Ready to scan?</h2>
      <p className="text-(--text-secondary) mb-8">Every visualization here runs on the existing trained models — nothing was faked for this demo.</p>
      <Link to="/scanner" className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-(--accent) text-white text-base font-semibold hover:brightness-110 shadow-[0_0_30px_var(--accent-glow)]">
        Start Scan <ArrowRight size={16} />
      </Link>
    </div>
  );
}
