import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  Code2, Columns2, Map as MapIcon, Loader2, ShieldAlert, ShieldCheck, AlertTriangle,
  Network, MemoryStick, Wand2, Gauge as GaugeIcon, Workflow, Crosshair, Share2, GripVertical,
} from "lucide-react";
import { ReactFlow, Background, Controls, MiniMap as FlowMiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import Gauge from "../components/Gauge";
import { VerdictPill } from "../components/RiskBadge";
import FeatureTable from "../components/FeatureTable";
import ContributionBars from "../components/ContributionBars";
import CallGraphView from "../components/graphs/CallGraphView";
import CfgView from "../components/graphs/CfgView";
import AttackGraphView from "../components/graphs/AttackGraphView";
import { layoutGraph } from "../components/graphs/layout";
import { scanLive, getScan, type LiveScanResult, type ScanResult } from "../api/client";
import { getDefaultModel } from "../utils/settings";
import { replayUrl } from "../utils/replay";
import Editor from "@monaco-editor/react";

const DEBOUNCE_MS = 800;
const DEFAULT_CODE = `#include <string.h>
#include <stdlib.h>

void process(char *input, size_t len) {
    char buf[64];
    strcpy(buf, input);          // no bounds check
    int *p = malloc(sizeof(int));
    *p = len;                    // never freed
}

int main(void) {
    process("hello", 5);
    return 0;
}
`;

const TABS = ["Overview", "Structure", "Findings", "Memory & Pointers", "Call Graph", "CFG", "Attack Graph", "Knowledge Graph", "Suggestions"] as const;
type Tab = typeof TABS[number];

const MIN_PANEL_W = 360;
const MAX_PANEL_W = 720;

export default function LiveIDE() {
  const [params] = useSearchParams();
  const openScanId = params.get("scan");

  const [codeA, setCodeA] = useState(DEFAULT_CODE);
  const [codeB, setCodeB] = useState("");
  const [split, setSplit] = useState(false);
  const [language, setLanguage] = useState<"c" | "cpp">("c");
  const [minimap, setMinimap] = useState(true);
  const [theme, setTheme] = useState<"vs-dark" | "light">("vs-dark");
  const [tab, setTab] = useState<Tab>("Overview");
  const [panelWidth, setPanelWidth] = useState(440);
  const [loadingScan, setLoadingScan] = useState(!!openScanId);

  const [resultA, setResultA] = useState<LiveScanResult | null>(null);
  const [resultB, setResultB] = useState<LiveScanResult | null>(null);
  const [analyzingA, setAnalyzingA] = useState(false);
  const [analyzingB, setAnalyzingB] = useState(false);

  // Deep link from Repository Scanner / File Explorer ("Open in Live IDE"):
  // ?scan=<id> pulls that file's real stored source into Editor A so it
  // starts live-analyzing immediately, instead of the placeholder snippet.
  useEffect(() => {
    if (!openScanId) return;
    let cancelled = false;
    setLoadingScan(true);
    getScan(openScanId)
      .then((s) => {
        if (cancelled) return;
        if (s.code) setCodeA(s.code);
        setLanguage(/\.(cpp|cc|cxx|hpp|hh)$/i.test(s.filename) ? "cpp" : "c");
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingScan(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openScanId]);

  useLiveAnalysis(codeA, setResultA, setAnalyzingA);
  useLiveAnalysis(split ? codeB : "", setResultB, setAnalyzingB, !split);

  const dragRef = useRef<{ startX: number; startW: number } | null>(null);
  const onDividerDown = (e: React.PointerEvent) => {
    dragRef.current = { startX: e.clientX, startW: panelWidth };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onDividerMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const delta = dragRef.current.startX - e.clientX; // dragging left grows the panel
    const next = Math.min(MAX_PANEL_W, Math.max(MIN_PANEL_W, dragRef.current.startW + delta));
    setPanelWidth(next);
  };
  const onDividerUp = () => { dragRef.current = null; };

  return (
    <PageShell
      title="Live IDE"
      subtitle={loadingScan ? "Loading file from Repository Scanner..." : "Monaco editor with automatic, continuous analysis — no scan button, updates 800ms after you stop typing"}
      actions={
        <>
          <button onClick={() => setMinimap((m) => !m)} className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition-colors ${minimap ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary)"}`}>
            <MapIcon size={13} /> Minimap
          </button>
          <select value={language} onChange={(e) => setLanguage(e.target.value as "c" | "cpp")} className="bg-(--surface-2) border border-(--border-hairline) rounded-lg px-3 py-2 text-xs focus-ring outline-none">
            <option value="c">C</option>
            <option value="cpp">C++</option>
          </select>
          <button onClick={() => setSplit((s) => !s)} className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition-colors ${split ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary)"}`}>
            <Columns2 size={13} /> Split Editor
          </button>
        </>
      }
    >
      <div className="flex flex-col xl:flex-row gap-0" style={{ alignItems: "stretch" }}>
        <div className="flex-1 min-w-0 flex flex-col xl:flex-row gap-5 pr-0 xl:pr-5">
          <div className="flex-1 min-w-0">
            <EditorPane
              label="Editor A"
              code={codeA} onChange={setCodeA} language={language} minimap={minimap} theme={theme} setTheme={setTheme}
              analyzing={analyzingA} result={resultA}
            />
          </div>
          {split && (
            <div className="flex-1 min-w-0">
              <EditorPane
                label="Editor B"
                code={codeB} onChange={setCodeB} language={language} minimap={minimap} theme={theme} setTheme={setTheme}
                analyzing={analyzingB} result={resultB}
                placeholder="Paste a second snippet to compare live analysis side by side..."
              />
            </div>
          )}
        </div>

        <div
          onPointerDown={onDividerDown} onPointerMove={onDividerMove} onPointerUp={onDividerUp}
          className="hidden xl:flex items-center justify-center w-3 shrink-0 cursor-col-resize group"
          title="Drag to resize"
        >
          <div className="w-1 h-16 rounded-full bg-(--border-hairline) group-hover:bg-(--accent) transition-colors flex items-center justify-center">
            <GripVertical size={10} className="text-(--text-muted) group-hover:text-white -ml-1.5" />
          </div>
        </div>

        <div className="shrink-0 mt-5 xl:mt-0 w-full xl:w-auto" style={{ maxWidth: "100%" }}>
          <div className="xl:sticky xl:top-20 w-full xl:w-auto">
            <div className="hidden xl:block" style={{ width: panelWidth }}>
              <AnalysisPanel tab={tab} setTab={setTab} result={resultA} analyzing={analyzingA} />
            </div>
            <div className="xl:hidden">
              <AnalysisPanel tab={tab} setTab={setTab} result={resultA} analyzing={analyzingA} />
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}

function AnalysisPanel({ tab, setTab, result, analyzing }: { tab: Tab; setTab: (t: Tab) => void; result: LiveScanResult | null; analyzing: boolean }) {
  return (
    <ChartCard title="Live Analysis" subtitle={analyzing ? "Analyzing..." : "Editor A"}>
      <div className="flex flex-wrap gap-1 mb-4 border-b border-(--border-hairline) pb-3">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-2.5 py-1.5 rounded-md text-[11px] font-semibold transition-colors ${tab === t ? "bg-(--accent)/15 text-(--accent)" : "text-(--text-muted) hover:text-(--text-secondary) hover:bg-(--surface-3)"}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="max-h-[640px] overflow-y-auto scrollbar-thin pr-1">
        <LivePanel tab={tab} result={result} analyzing={analyzing} />
      </div>
    </ChartCard>
  );
}

function useLiveAnalysis(code: string, setResult: (r: LiveScanResult | null) => void, setAnalyzing: (b: boolean) => void, disabled = false) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqIdRef = useRef(0);

  useEffect(() => {
    if (disabled) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!code.trim()) { setResult(null); setAnalyzing(false); return; }
    setAnalyzing(true);
    timerRef.current = setTimeout(() => {
      const myReqId = ++reqIdRef.current;
      scanLive(code, getDefaultModel())
        .then((r) => { if (myReqId === reqIdRef.current) setResult(r); })
        .catch(() => { if (myReqId === reqIdRef.current) setResult(null); })
        .finally(() => { if (myReqId === reqIdRef.current) setAnalyzing(false); });
    }, DEBOUNCE_MS);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, disabled]);
}

function EditorPane({ label, code, onChange, language, minimap, theme, setTheme, analyzing, result, placeholder }: {
  label: string; code: string; onChange: (v: string) => void; language: "c" | "cpp"; minimap: boolean;
  theme: "vs-dark" | "light"; setTheme: (t: "vs-dark" | "light") => void; analyzing: boolean; result: LiveScanResult | null; placeholder?: string;
}) {
  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <div className="flex items-center justify-between px-3 py-1.5 bg-(--surface-3) border-b border-(--border-hairline)">
        <div className="flex items-center gap-1.5 text-xs text-(--text-muted)">
          <Code2 size={12} /> <span className="mono">{label}</span>
          {analyzing && <Loader2 size={11} className="animate-spin text-(--accent)" />}
        </div>
        <div className="flex items-center gap-2">
          {result?.valid && result.verdict && (
            <span className="flex items-center gap-1.5 text-[11px]">
              <VerdictPill verdict={result.verdict} />
              <span className="tabular text-(--text-muted)">{result.vuln_probability?.toFixed(1)}%</span>
            </span>
          )}
          <button onClick={() => setTheme(theme === "vs-dark" ? "light" : "vs-dark")} className="text-[10px] text-(--text-muted) hover:text-(--text-primary) px-1.5 py-0.5 rounded hover:bg-(--surface-2)">
            {theme === "vs-dark" ? "Light" : "Dark"}
          </button>
        </div>
      </div>
      <Editor
        height={560}
        language={language}
        theme={theme}
        value={code}
        onChange={(v) => onChange(v ?? "")}
        options={{
          minimap: { enabled: minimap },
          fontSize: 13,
          fontFamily: "ui-monospace, Consolas, monospace",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          autoIndent: "full",
          renderLineHighlight: "all",
          folding: true,
          padding: { top: 12 },
        }}
      />
      {placeholder && !code && (
        <div className="px-3 py-1.5 bg-(--surface-2) text-[11px] text-(--text-muted) border-t border-(--border-hairline)">{placeholder}</div>
      )}
    </div>
  );
}

function LivePanel({ tab, result, analyzing }: { tab: Tab; result: LiveScanResult | null; analyzing: boolean }) {
  if (!result) {
    return <div className="py-16 text-center text-sm text-(--text-muted)">{analyzing ? "Analyzing..." : "Start typing to see live analysis."}</div>;
  }
  if (!result.valid) {
    return <div className="py-10 text-center text-sm text-(--status-warning)">{result.validation_message || "Not enough code to analyze yet."}</div>;
  }

  const intel = result.intelligence;
  const scores = intel?.available ? intel.scores : undefined;

  if (tab === "Overview") {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-center gap-8 py-2">
          <Gauge value={result.vuln_probability ?? 0} color={result.risk_color || "var(--status-serious)"} label="Risk" />
          <Gauge value={result.confidence ?? 0} color="var(--series-7)" label="Confidence" />
        </div>
        <div className="grid grid-cols-2 gap-3 text-center">
          <MiniStat label="Verdict" value={result.verdict === "VULNERABLE" ? "Vulnerable" : "Safe"} icon={result.verdict === "VULNERABLE" ? ShieldAlert : ShieldCheck} color={result.verdict === "VULNERABLE" ? "var(--status-critical)" : "var(--status-good)"} />
          <MiniStat label="Risk Level" value={result.risk_level ?? "-"} icon={AlertTriangle} color={result.risk_color || "var(--status-warning)"} />
        </div>
        {result.is_demo && <div className="text-[11px] text-(--status-warning) text-center">Demo mode — trained model weights unavailable.</div>}
        {result.insights && result.insights.length > 0 && (
          <div className="space-y-1.5 pt-2 border-t border-(--border-hairline)">
            {result.insights.slice(0, 5).map(([text, sev], i) => (
              <div key={i} className={`text-xs rounded-lg p-2.5 border-l-2 ${sev === "warning" ? "border-(--status-serious) bg-(--status-serious)/10" : "border-(--series-1) bg-(--series-1)/10"}`}>{text}</div>
            ))}
          </div>
        )}
        {result.contributions && result.contributions.length > 0 && (
          <div className="pt-2 border-t border-(--border-hairline)">
            <div className="text-xs font-semibold mb-2">Top Contributing Features</div>
            <ContributionBars contributions={result.contributions} />
          </div>
        )}
      </div>
    );
  }

  if (tab === "Structure") {
    return (
      <div className="space-y-4">
        {scores && (
          <div className="grid grid-cols-2 gap-2">
            <MiniStat label="Quality" value={`${scores.quality}%`} icon={GaugeIcon} color="var(--series-1)" />
            <MiniStat label="Maintainability" value={String(scores.maintainability_index)} icon={GaugeIcon} color="var(--series-5)" />
            <MiniStat label="Security Score" value={`${scores.security_score}%`} icon={GaugeIcon} color="var(--status-good)" />
            <MiniStat label="Avg Complexity" value={String(scores.cyclomatic_complexity_avg ?? "-")} icon={GaugeIcon} color="var(--series-4)" />
          </div>
        )}
        <div className="text-xs font-semibold pt-2 border-t border-(--border-hairline)">AST Features</div>
        {result.ast_features && <FeatureTable features={result.ast_features} />}
        <div className="text-xs font-semibold pt-2 border-t border-(--border-hairline)">Software Metrics</div>
        {result.metric_features && <FeatureTable features={result.metric_features} />}
      </div>
    );
  }

  if (tab === "Findings") {
    return (
      <div className="space-y-3">
        <div className="text-xs font-semibold">Line-Level Heatmap ({result.line_risks?.length ?? 0})</div>
        {!result.line_risks || result.line_risks.length === 0 ? (
          <div className="text-xs text-(--text-muted) py-6 text-center">No line-level findings.</div>
        ) : (
          <div className="space-y-1.5">
            {result.line_risks.map((lr, i) => (
              <div key={i} className="text-xs rounded-lg p-2.5 bg-(--surface-3)">
                <div className="flex items-center justify-between mb-1">
                  <span className="mono font-semibold">Line {lr.line}</span>
                  <span className="text-(--text-muted)">{lr.cwe.join(", ")}</span>
                </div>
                <div className="text-(--text-secondary)">{lr.reasons.join("; ")}</div>
                {lr.cwe.length > 0 && (
                  <ReplayLink cwe={lr.cwe[0]} />
                )}
              </div>
            ))}
          </div>
        )}
        <div className="text-xs font-semibold pt-2 border-t border-(--border-hairline)">Dangerous APIs</div>
        {!intel?.dangerous_apis || intel.dangerous_apis.length === 0 ? (
          <div className="text-xs text-(--text-muted) py-4 text-center">None detected.</div>
        ) : (
          <div className="space-y-1.5">
            {intel.dangerous_apis.map((d, i) => (
              <div key={i} className="flex items-center justify-between text-xs bg-(--surface-3) rounded-lg p-2">
                <span className="mono">{d.api}() — line {d.line}</span>
                <span className="text-(--status-critical)">{d.cwe}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (tab === "Memory & Pointers") {
    const mem = intel?.available ? intel.memory : undefined;
    const ptr = intel?.available ? intel.pointers : undefined;
    return (
      <div className="space-y-4">
        <div className="text-xs font-semibold flex items-center gap-1.5"><MemoryStick size={13} /> Memory</div>
        {mem ? (
          <div className="grid grid-cols-2 gap-2">
            <MiniStat label="Allocations" value={String(mem.allocations)} icon={MemoryStick} color="var(--series-1)" />
            <MiniStat label="Frees" value={String(mem.frees)} icon={MemoryStick} color="var(--status-good)" />
            <MiniStat label="Balance" value={String(mem.balance)} icon={MemoryStick} color={mem.potential_leak ? "var(--status-critical)" : "var(--status-good)"} />
            <MiniStat label="Stack Buffers" value={String(mem.stack_buffers?.length ?? 0)} icon={MemoryStick} color="var(--series-6)" />
          </div>
        ) : <div className="text-xs text-(--text-muted) py-4 text-center">Not available.</div>}

        <div className="text-xs font-semibold pt-2 border-t border-(--border-hairline)">Pointers</div>
        {ptr ? (
          <div className="grid grid-cols-2 gap-2">
            <MiniStat label="Pointer Vars" value={String(ptr.pointer_variables)} icon={GaugeIcon} color="var(--series-7)" />
            <MiniStat label="Dereferences" value={String(ptr.dereferences)} icon={GaugeIcon} color="var(--series-4)" />
            <MiniStat label="NULL Checks" value={String(ptr.null_checks)} icon={GaugeIcon} color="var(--status-good)" />
            <MiniStat label="Coverage" value={`${ptr.null_check_coverage_pct}%`} icon={GaugeIcon} color={ptr.null_check_coverage_pct < 50 ? "var(--status-critical)" : "var(--status-good)"} />
          </div>
        ) : <div className="text-xs text-(--text-muted) py-4 text-center">Not available.</div>}
      </div>
    );
  }

  if (tab === "Call Graph") {
    const cg = intel?.available ? intel.call_graph : undefined;
    return (
      <div>
        <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Network size={13} /> Call Graph</div>
        {cg && cg.nodes.length > 0 ? (
          <CallGraphView nodes={cg.nodes} edges={cg.edges} criticalNames={intel?.available ? intel.critical_nodes : []} deadCodeNames={intel?.available ? intel.dead_code : []} />
        ) : <div className="text-xs text-(--text-muted) py-10 text-center">No function calls detected yet.</div>}
      </div>
    );
  }

  if (tab === "CFG") {
    const cfg = intel?.available ? intel.cfg : undefined;
    return (
      <div>
        <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Workflow size={13} /> Control Flow Graph — {cfg?.function ?? "-"}</div>
        {cfg && cfg.nodes.length > 0 ? (
          <CfgView nodes={cfg.nodes} edges={cfg.edges} />
        ) : <div className="text-xs text-(--text-muted) py-10 text-center">No control flow detected yet.</div>}
      </div>
    );
  }

  if (tab === "Attack Graph") {
    if (!intel?.available) return <div className="text-xs text-(--text-muted) py-10 text-center">Not available yet.</div>;
    // AttackGraphView only reads .filename / .verdict / .vuln_probability off `scan` --
    // a live, unsaved snippet has no scan id, so a minimal compatible object is built
    // here rather than pulling in the full ScanResult shape it isn't actually using.
    const pseudoScan = {
      filename: "live-editor.c", verdict: result.verdict, vuln_probability: result.vuln_probability ?? 0,
    } as unknown as ScanResult;
    return (
      <div>
        <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Crosshair size={13} /> Attack Graph</div>
        <AttackGraphView scan={pseudoScan} intel={intel} />
      </div>
    );
  }

  if (tab === "Knowledge Graph") {
    return (
      <div>
        <div className="text-xs font-semibold mb-2 flex items-center gap-1.5"><Share2 size={13} /> Knowledge Graph — this snippet</div>
        <LiveKnowledgeGraph intel={intel} />
      </div>
    );
  }

  // Suggestions
  return (
    <div className="space-y-4">
      <div className="text-xs font-semibold flex items-center gap-1.5"><Wand2 size={13} /> Recommendations</div>
      {!result.recommendations || result.recommendations.length === 0 ? (
        <div className="text-xs text-(--text-muted) py-6 text-center">No specific recommendations yet.</div>
      ) : (
        result.recommendations.map((panel, i) => (
          <div key={i}>
            <div className="text-xs font-semibold text-(--accent) mb-1.5">{panel.title}</div>
            <div className="space-y-1">
              {panel.tips.map((tip, j) => (
                <div key={j} className="text-xs text-(--text-secondary) flex items-start gap-1.5">
                  <span className="text-(--text-muted)">&bull;</span> {tip}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
      {result.suggested_rewrite?.changed && (
        <div className="pt-2 border-t border-(--border-hairline)">
          <div className="text-xs font-semibold mb-1.5">Suggested Secure Rewrite</div>
          {result.suggested_rewrite.requires_manual_sizing && (
            <div className="text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2 mb-1.5">
              Contains a <code className="mono">dest_size</code> placeholder — real buffer capacity could not be determined; fill it in manually.
            </div>
          )}
          <pre className="text-[11px] mono bg-(--surface-3) rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{result.suggested_rewrite.rewritten_code}</pre>
        </div>
      )}
    </div>
  );
}

function ReplayLink({ cwe }: { cwe: string }) {
  const url = replayUrl(cwe);
  if (!url) return null;
  return (
    <Link
      to={url}
      className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold text-(--accent) hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      ▶ Replay this exploit
    </Link>
  );
}

function LiveKnowledgeGraph({ intel }: { intel: LiveScanResult["intelligence"] }) {
  const { laidNodes, laidEdges } = useMemo(() => {
    if (!intel?.available) return { laidNodes: [], laidEdges: [] };
    const nodes: any[] = [];
    const edges: any[] = [];
    let eid = 0;
    const KIND_COLOR: Record<string, string> = { file: "#3987e5", function: "#199e70", cwe: "#d03b3b", dangerous_api: "#e66767", variable: "#fab219", buffer: "#c98500" };
    const addNode = (id: string, label: string, kind: string) => {
      if (nodes.some((n) => n.id === id)) return;
      const color = KIND_COLOR[kind] ?? "#9085e9";
      nodes.push({
        id, position: { x: 0, y: 0 }, width: 150, height: 40,
        data: { label },
        style: { background: `${color}1f`, border: `1.5px solid ${color}88`, borderRadius: kind === "cwe" || kind === "dangerous_api" ? 20 : 8, color: "#fff", fontSize: 11, fontFamily: "ui-monospace, monospace", padding: 6, width: 150, textAlign: "center" as const },
      });
    };
    const addEdge = (source: string, target: string, color = "#52514e") => {
      edges.push({ id: `e${eid++}`, source, target, style: { stroke: color, strokeWidth: 1.3 }, markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12 } });
    };

    addNode("file", "live-editor.c", "file");
    for (const f of intel.functions) {
      const fnId = `fn::${f.name}`;
      addNode(fnId, f.name, "function");
      addEdge("file", fnId, "#52514e");
      for (const api of f.dangerous_apis) {
        const apiId = `api::${api}`;
        addNode(apiId, api, "dangerous_api");
        addEdge(fnId, apiId, "#9085e9");
        const match = intel.dangerous_apis.find((d) => d.api === api);
        if (match?.cwe) {
          const cweId = `cwe::${match.cwe}`;
          addNode(cweId, match.cwe, "cwe");
          addEdge(apiId, cweId, "#d03b3b");
        }
      }
      for (const g of f.global_refs ?? []) {
        const varId = `var::${g}`;
        addNode(varId, g, "variable");
        addEdge(fnId, varId, "#fab219");
      }
    }
    for (const buf of intel.buffers ?? []) {
      const bufId = `buf::${buf.name}::${buf.line}`;
      addNode(bufId, `${buf.name} [${buf.declared_size}]`, "buffer");
      addEdge("file", bufId, "#c98500");
    }

    const { nodes: ln, edges: le } = layoutGraph(nodes, edges, "TB");
    return { laidNodes: ln, laidEdges: le };
  }, [intel]);

  if (!intel?.available || laidNodes.length <= 1) {
    return <div className="text-xs text-(--text-muted) py-10 text-center">Not enough structure yet — add a function or a dangerous call.</div>;
  }

  return (
    <div style={{ height: 420 }} className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <ReactFlow nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark" nodesDraggable nodesConnectable={false}>
        <Background color="#2c2c2a" gap={18} />
        <Controls showInteractive={false} />
        <FlowMiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
      </ReactFlow>
    </div>
  );
}

function MiniStat({ label, value, icon: Icon, color }: { label: string; value: string; icon: any; color: string }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-3">
      <Icon size={14} style={{ color }} className="mb-1" />
      <div className="text-sm font-bold tabular truncate">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
    </div>
  );
}
