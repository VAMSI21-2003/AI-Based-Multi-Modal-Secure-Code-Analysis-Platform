import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Pause, SkipBack, SkipForward, Layers, Box } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { SCENARIOS, type BlockStatus } from "../data/simulatorScenarios";

const STATUS_STYLE: Record<BlockStatus, { bg: string; border: string; label: string }> = {
  valid: { bg: "rgba(57,135,229,0.16)", border: "#3987e5", label: "Valid" },
  freed: { bg: "rgba(137,135,129,0.16)", border: "#898781", label: "Freed" },
  overflowed: { bg: "rgba(236,131,90,0.2)", border: "#ec835a", label: "Overflowed" },
  leaked: { bg: "rgba(144,133,233,0.2)", border: "#9085e9", label: "Leaked" },
  dangling: { bg: "rgba(250,178,25,0.2)", border: "#fab219", label: "Dangling" },
  corrupted: { bg: "rgba(208,59,59,0.24)", border: "#d03b3b", label: "Corrupted" },
  written: { bg: "rgba(25,158,112,0.2)", border: "#199e70", label: "Written" },
  null: { bg: "rgba(137,135,129,0.1)", border: "#52514e", label: "NULL" },
};

const AUTOPLAY_MS = 2200;

export default function Simulator() {
  const [params] = useSearchParams();
  const deepLinkedScenario = params.get("scenario");
  const initialScenario = (deepLinkedScenario && SCENARIOS.some((s) => s.id === deepLinkedScenario))
    ? deepLinkedScenario
    : SCENARIOS[0].id;

  const [scenarioId, setScenarioId] = useState(initialScenario);
  const [frameIdx, setFrameIdx] = useState(0);
  const [playing, setPlaying] = useState(params.get("autoplay") === "1" && !!deepLinkedScenario);

  const scenario = SCENARIOS.find((s) => s.id === scenarioId)!;
  const frame = scenario.frames[frameIdx];

  // Manual scenario picks (sidebar buttons) always reset playback state.
  const selectScenario = (id: string) => {
    setScenarioId(id);
    setFrameIdx(0);
    setPlaying(false);
  };

  // Deep link from Findings ("Replay this exploit") arriving while this page
  // is already mounted -- same route, only the query string changed -- jumps
  // straight to the matching scenario and autoplays it.
  useEffect(() => {
    if (deepLinkedScenario && SCENARIOS.some((s) => s.id === deepLinkedScenario)) {
      setScenarioId(deepLinkedScenario);
      setFrameIdx(0);
      setPlaying(params.get("autoplay") === "1");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkedScenario]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setFrameIdx((i) => {
        if (i + 1 >= scenario.frames.length) { setPlaying(false); return i; }
        return i + 1;
      });
    }, AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [playing, scenario]);

  const stackBlocks = frame.blocks.filter((b) => b.region === "stack");
  const heapBlocks = frame.blocks.filter((b) => b.region === "heap");

  return (
    <PageShell title="Vulnerability Simulator" subtitle="Animated memory-safety walkthroughs — stack, heap, and pointers">
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <ChartCard title="Scenarios" className="xl:col-span-1">
          <div className="space-y-1.5">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                onClick={() => selectScenario(s.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-colors ${
                  s.id === scenarioId ? "bg-(--surface-3) border border-(--border-hairline-strong)" : "hover:bg-(--surface-2) border border-transparent"
                }`}
              >
                <div className="font-semibold">{s.title}</div>
                <div className="text-(--text-muted) mt-0.5">{s.cwe}</div>
              </button>
            ))}
          </div>
        </ChartCard>

        <div className="xl:col-span-3 space-y-5">
          <ChartCard title={scenario.title} subtitle={scenario.summary}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 min-h-[220px]">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-(--text-muted) font-semibold mb-2 flex items-center gap-1.5"><Layers size={11} /> Stack</div>
                <div className="space-y-2">
                  <AnimatePresence mode="popLayout">
                    {stackBlocks.length === 0 && <div className="text-xs text-(--text-muted)">(empty)</div>}
                    {stackBlocks.map((b) => (
                      <motion.div
                        key={b.id} layout
                        initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }}
                        transition={{ duration: 0.35 }}
                        className="rounded-lg px-3 py-2.5 text-xs font-medium mono"
                        style={{ background: STATUS_STYLE[b.status].bg, border: `1.5px solid ${STATUS_STYLE[b.status].border}` }}
                      >
                        {b.label}
                        <span className="float-right text-[10px] opacity-80">{STATUS_STYLE[b.status].label}</span>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-(--text-muted) font-semibold mb-2 flex items-center gap-1.5"><Box size={11} /> Heap</div>
                <div className="space-y-2">
                  <AnimatePresence mode="popLayout">
                    {heapBlocks.length === 0 && <div className="text-xs text-(--text-muted)">(empty)</div>}
                    {heapBlocks.map((b) => (
                      <motion.div
                        key={b.id} layout
                        initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
                        transition={{ duration: 0.35 }}
                        className="rounded-lg px-3 py-2.5 text-xs font-medium mono"
                        style={{ background: STATUS_STYLE[b.status].bg, border: `1.5px solid ${STATUS_STYLE[b.status].border}` }}
                      >
                        {b.label}
                        <span className="float-right text-[10px] opacity-80">{STATUS_STYLE[b.status].label}</span>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={frameIdx}
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                className="mt-5 p-4 rounded-lg bg-(--surface-3)"
              >
                <p className="text-sm text-(--text-secondary)">{frame.caption}</p>
                {frame.code && <pre className="mono text-xs text-(--accent) mt-2 whitespace-pre-wrap">{frame.code}</pre>}
              </motion.div>
            </AnimatePresence>

            <div className="flex items-center justify-center gap-3 mt-5">
              <button onClick={() => setFrameIdx((i) => Math.max(0, i - 1))} disabled={frameIdx === 0} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30">
                <SkipBack size={16} />
              </button>
              <button onClick={() => setPlaying((p) => !p)} className="px-5 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold flex items-center gap-2 hover:brightness-110">
                {playing ? <Pause size={15} /> : <Play size={15} />} {playing ? "Pause" : "Play"}
              </button>
              <button onClick={() => setFrameIdx((i) => Math.min(scenario.frames.length - 1, i + 1))} disabled={frameIdx === scenario.frames.length - 1} className="p-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30">
                <SkipForward size={16} />
              </button>
              <span className="text-xs text-(--text-muted) tabular ml-2">Step {frameIdx + 1} / {scenario.frames.length}</span>
            </div>
          </ChartCard>
        </div>
      </div>
    </PageShell>
  );
}
