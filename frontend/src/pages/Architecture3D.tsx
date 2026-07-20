import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  FileCode2, TreePine, BarChart3, Cpu, Combine, Brain, Lightbulb, FileText,
} from "lucide-react";
import { Radio } from "lucide-react";
import PageShell from "../components/PageShell";
import { Spinner } from "../components/Loading";
import { getModelArchitecture, getModelPerformance, getDashboardStats, type ModelArchitecture } from "../api/client";

interface Stage {
  id: string; label: string; sub: string; icon: any; color: string;
}

const LIVE_POLL_MS = 10000;

// The core inference path a real prediction actually travels through --
// Explainability/Reports are downstream consumers of a finished prediction,
// not part of the fusion pipeline itself, so the live pulse stops at "ml".
const PULSE_ORDER: Record<string, number> = { source: 0, ast: 1, metrics: 1, codebert: 2, fusion: 3, ml: 4 };
const PULSE_STEP_MS = 260;

export default function Architecture3D() {
  const [arch, setArch] = useState<ModelArchitecture | null>(null);
  const [perf, setPerf] = useState<any>(null);
  const [rotation, setRotation] = useState(0);
  const [autoRotate, setAutoRotate] = useState(true);
  const dragRef = useRef<{ startX: number; startRotation: number } | null>(null);
  const [lastScan, setLastScan] = useState<{ id: string; filename: string; verdict: string } | null>(null);
  const [pulseSeq, setPulseSeq] = useState(0);
  const [pulsing, setPulsing] = useState(false);
  const seenScanId = useRef<string | null>(null);
  const pulseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    getModelArchitecture().then(setArch).catch(() => {});
    getModelPerformance().then(setPerf).catch(() => {});
  }, []);

  // Digital Twin (Phase 7): the ML node pulses with the verdict of whatever
  // was ACTUALLY scanned most recently, polled live -- this isn't just a
  // static diagram of the architecture, it reflects real, current pipeline
  // activity. Whenever a genuinely NEW scan lands (not just the first poll
  // on page load), the current prediction visibly travels through every
  // stage of the real pipeline, one at a time, in order.
  useEffect(() => {
    const poll = () => {
      getDashboardStats().then((d) => {
        const top = d.recent_scans[0];
        if (!top) return;
        setLastScan({ id: top.id, filename: top.filename, verdict: top.verdict });
        if (seenScanId.current !== null && seenScanId.current !== top.id) {
          setPulseSeq((n) => n + 1);
          setPulsing(true);
          if (pulseTimeoutRef.current) clearTimeout(pulseTimeoutRef.current);
          pulseTimeoutRef.current = setTimeout(() => setPulsing(false), PULSE_ORDER.ml * PULSE_STEP_MS + 900);
        }
        seenScanId.current = top.id;
      }).catch(() => {});
    };
    poll();
    const id = setInterval(poll, LIVE_POLL_MS);
    return () => { clearInterval(id); if (pulseTimeoutRef.current) clearTimeout(pulseTimeoutRef.current); };
  }, []);

  useEffect(() => {
    if (!autoRotate) return;
    const id = setInterval(() => setRotation((r) => r + 0.15), 50);
    return () => clearInterval(id);
  }, [autoRotate]);

  if (!arch) {
    return <PageShell title="Architecture 3D" subtitle="The full pipeline, in space"><Spinner label="Loading architecture..." /></PageShell>;
  }

  const stages: Stage[] = [
    { id: "source", label: "Source Code", sub: "C / C++ input", icon: FileCode2, color: "#3987e5" },
    { id: "ast", label: "AST Branch", sub: `${arch.feature_pipeline.ast_dimensions} structural features`, icon: TreePine, color: "#d55181" },
    { id: "metrics", label: "Metrics Branch", sub: `${arch.feature_pipeline.metrics_dimensions} quality metrics`, icon: BarChart3, color: "#c98500" },
    { id: "codebert", label: "CodeBERT", sub: `${arch.feature_pipeline.embedding_dimensions}-dim · ${arch.codebert.layers} layers`, icon: Cpu, color: "#9085e9" },
    { id: "fusion", label: "Feature Fusion", sub: `${arch.feature_pipeline.total_dimensions}-dim fused vector`, icon: Combine, color: "#199e70" },
    {
      id: "ml", label: "XGBoost Classifier",
      sub: lastScan ? `Last: ${lastScan.filename} — ${lastScan.verdict}` : (perf?.available ? `${(perf.xgboost.f1 * 100).toFixed(1)}% F1` : `${arch.xgboost?.total_trees ?? "-"} trees`),
      icon: Brain, color: lastScan ? (lastScan.verdict === "VULNERABLE" ? "#d03b3b" : "#0ca30c") : "#e66767",
    },
    { id: "explain", label: "Explainability", sub: "Feature contributions, CFG, call graph", icon: Lightbulb, color: "#fab219" },
    { id: "reports", label: "Reports", sub: "PDF / DOCX / PPTX", icon: FileText, color: "#3987e5" },
  ];

  const n = stages.length;
  const radius = 340;

  const onPointerDown = (e: React.PointerEvent) => {
    setAutoRotate(false);
    dragRef.current = { startX: e.clientX, startRotation: rotation };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    setRotation(dragRef.current.startRotation + dx * 0.35);
  };
  const onPointerUp = () => { dragRef.current = null; };

  return (
    <PageShell title="Architecture 3D" subtitle="Source → AST → Metrics → CodeBERT → Fusion → ML → Explainability → Reports, in 3D space — drag to rotate">
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setAutoRotate((a) => !a)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${autoRotate ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary)"}`}
        >
          {autoRotate ? "Auto-rotating" : "Paused (drag to spin)"}
        </button>
        <span className="text-xs text-(--text-muted)">Real dimension counts pulled live from the trained model's architecture endpoint.</span>
        {lastScan && (
          <span className={`ml-auto flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${pulsing ? "bg-(--accent)/15 border-(--accent)/50 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline)"}`}>
            <Radio size={11} className="text-(--status-good) animate-pulse-soft" />
            {pulsing ? "Prediction travelling through pipeline..." : `Digital Twin live — ${lastScan.filename} (${lastScan.verdict})`}
          </span>
        )}
      </div>

      <div
        className="relative rounded-2xl border border-(--border-hairline) overflow-hidden select-none"
        style={{ height: 560, background: "radial-gradient(ellipse at 50% 30%, rgba(57,135,229,0.08), transparent 60%), var(--surface-1)", perspective: 1400, cursor: dragRef.current ? "grabbing" : "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <div className="cyber-grid" style={{ opacity: 0.4 }} />
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ transformStyle: "preserve-3d", transform: `rotateY(${rotation}deg) rotateX(-8deg)` }}
        >
          {stages.map((s, i) => {
            const angle = (360 / n) * i;
            return (
              <div
                key={s.id}
                className="absolute"
                style={{
                  transformStyle: "preserve-3d",
                  transform: `rotateY(${angle}deg) translateZ(${radius}px)`,
                }}
              >
                <StageCard
                  stage={s} counterRotation={-rotation - angle}
                  pulseSeq={PULSE_ORDER[s.id] !== undefined ? pulseSeq : null}
                  pulseDelayMs={PULSE_ORDER[s.id] !== undefined ? PULSE_ORDER[s.id] * PULSE_STEP_MS : 0}
                  verdictColor={s.id === "ml" && lastScan ? (lastScan.verdict === "VULNERABLE" ? "#d03b3b" : "#0ca30c") : null}
                />
              </div>
            );
          })}

          {/* Connector ring + flowing particles, one per adjacent stage pair */}
          {stages.map((_, i) => {
            const angleA = (360 / n) * i;
            return <ConnectorParticle key={i} angleA={angleA} angleB={(360 / n) * ((i + 1) % n)} radius={radius} n={n} />;
          })}

          {/* Center hub */}
          <div style={{ transformStyle: "preserve-3d", transform: "translateZ(0px)" }} className="w-3 h-3 rounded-full bg-(--accent)" >
            <div className="absolute inset-0 rounded-full bg-(--accent) animate-ping opacity-60" />
          </div>
        </div>

        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[11px] text-(--text-muted) bg-(--surface-0)/70 backdrop-blur px-3 py-1.5 rounded-full border border-(--border-hairline)">
          Drag horizontally to rotate the pipeline · click a node to jump to its page
        </div>
      </div>
    </PageShell>
  );
}

const STAGE_LINKS: Record<string, string> = {
  source: "/scanner", ast: "/explanation", metrics: "/advanced-analysis", codebert: "/explainability",
  fusion: "/research", ml: "/comparison", explain: "/explainability", reports: "/export-center",
};

function StageCard({ stage, counterRotation, pulseSeq, pulseDelayMs, verdictColor }: {
  stage: Stage; counterRotation: number; pulseSeq: number | null; pulseDelayMs: number; verdictColor: string | null;
}) {
  const Icon = stage.icon;
  const glowColor = verdictColor ?? stage.color;
  return (
    <a
      href={STAGE_LINKS[stage.id] ?? "#"}
      style={{ transformStyle: "preserve-3d", transform: `rotateY(${counterRotation}deg)`, display: "block" }}
      className="w-48 -ml-24 -mt-16"
    >
      <div
        className="relative rounded-xl p-4 border backdrop-blur-md transition-transform hover:scale-105"
        style={{ background: `${stage.color}14`, borderColor: `${stage.color}55`, boxShadow: `0 0 30px -10px ${stage.color}88` }}
      >
        {pulseSeq !== null && pulseSeq > 0 && (
          <motion.div
            key={pulseSeq}
            className="absolute inset-0 rounded-xl pointer-events-none"
            style={{ border: `2px solid ${glowColor}`, boxShadow: `0 0 26px 4px ${glowColor}` }}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: [0, 1, 0], scale: [0.94, 1.05, 1.08] }}
            transition={{ duration: 0.7, delay: pulseDelayMs / 1000, ease: "easeOut" }}
          />
        )}
        <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2" style={{ background: `${stage.color}26`, border: `1px solid ${stage.color}55` }}>
          <Icon size={16} style={{ color: stage.color }} />
        </div>
        <div className="text-xs font-bold text-(--text-primary)">{stage.label}</div>
        <div className="text-[10px] text-(--text-muted) mt-0.5 leading-snug">{stage.sub}</div>
      </div>
    </a>
  );
}

function ConnectorParticle({ angleA, angleB, radius, n }: { angleA: number; angleB: number; radius: number; n: number }) {
  // A particle travels along the circular ring between two adjacent stage angles.
  return (
    <motion.div
      style={{ transformStyle: "preserve-3d" }}
      animate={{ rotateY: [angleA, angleB] }}
      transition={{ duration: 2.4, repeat: Infinity, ease: "linear", repeatDelay: (n - 1) * 0.15 }}
    >
      <div style={{ transformStyle: "preserve-3d", transform: `translateZ(${radius}px)` }}>
        <div className="w-2 h-2 rounded-full bg-(--accent) -ml-1 -mt-1" style={{ boxShadow: "0 0 10px 3px var(--accent-glow)" }} />
      </div>
    </motion.div>
  );
}
