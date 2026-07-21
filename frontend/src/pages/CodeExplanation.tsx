import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  BrainCircuit, AlertTriangle, MemoryStick, Repeat, Box, Variable, ListTree, GitBranch, Workflow, BookOpen,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import Gauge from "../components/Gauge";
import CallGraphView from "../components/graphs/CallGraphView";
import CfgView from "../components/graphs/CfgView";
import { getCodeIntelligence, type CodeIntelligence } from "../api/client";
import { severityColor, severityLabel } from "../utils/risk";

function scoreColor(v: number) {
  if (v >= 80) return "var(--status-good)";
  if (v >= 60) return "var(--status-low)";
  if (v >= 40) return "var(--status-warning)";
  return "var(--status-critical)";
}

export default function CodeExplanation() {
  const [params] = useSearchParams();
  const scanId = params.get("scan");
  const [data, setData] = useState<CodeIntelligence | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cfgFn, setCfgFn] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCodeIntelligence(scanId, cfgFn)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to analyse code"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scanId, cfgFn]);

  useEffect(() => { setCfgFn(undefined); }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="AI Code Explanation" subtitle="Deep static analysis: complexity, memory, call graph, CFG, and quality scores">
        <ScanPickerEmpty icon={BrainCircuit} title="No scan selected" description="Run a scan to get a full code-intelligence breakdown of the uploaded program." />
      </PageShell>
    );
  }

  if ((loading && !data) || !data) {
    return (
      <PageShell title="AI Code Explanation" subtitle="Deep static analysis">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Analysing program structure..." />}
      </PageShell>
    );
  }

  if (!data.available) {
    return (
      <PageShell title="AI Code Explanation" subtitle="Deep static analysis">
        <div className="card p-4 text-sm text-(--status-warning)">Analysis unavailable: {data.error || "parser error"}</div>
      </PageShell>
    );
  }

  const s = data.scores;

  return (
    <PageShell title="AI Code Explanation" subtitle={data.file_summary}>
      {/* ── Composite scores ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <ChartCard title="Code Quality" className="flex flex-col items-center"><Gauge value={s.quality} color={scoreColor(s.quality)} /></ChartCard>
        <ChartCard title="Maintainability" className="flex flex-col items-center"><Gauge value={s.maintainability_index} color={scoreColor(s.maintainability_index)} /></ChartCard>
        <ChartCard title="Security Score" className="flex flex-col items-center"><Gauge value={s.security_score} color={scoreColor(s.security_score)} /></ChartCard>
        <ChartCard title="Performance" className="flex flex-col items-center"><Gauge value={s.performance_score} color={scoreColor(s.performance_score)} /></ChartCard>
        <ChartCard title="Cyclomatic Complexity" className="flex flex-col items-center justify-center">
          <div className="text-4xl font-bold tabular" style={{ color: scoreColor(100 - Math.min(100, s.cyclomatic_complexity_total * 5)) }}>
            {s.cyclomatic_complexity_total}
          </div>
          <div className="text-xs text-(--text-muted) mt-1">total across {data.function_count} function(s)</div>
          {s.cyclomatic_complexity_avg !== undefined && <div className="text-[11px] text-(--text-muted)">avg {s.cyclomatic_complexity_avg} / function</div>}
        </ChartCard>
      </div>

      {/* ── Function summaries ───────────────────────────────────────────── */}
      <ChartCard title="Function Summary" subtitle="AI code-intelligence summary per function (deterministic static analysis, not an LLM call)" className="mb-5">
        <div className="space-y-3">
          {data.functions.map((f) => (
            <div key={f.name} className="p-3 rounded-lg bg-(--surface-3)">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-1.5">
                <span className="mono text-sm font-semibold text-(--accent)">{f.name}()</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--surface-2) text-(--text-secondary)">LOC {f.loc}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--surface-2) text-(--text-secondary)">CC {f.cyclomatic_complexity}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--surface-2) text-(--text-secondary)">MI {f.maintainability_index}</span>
                  {f.is_recursive && <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--series-7)/20 text-(--series-7)">recursive</span>}
                  {f.dangerous_apis.length > 0 && <span className="text-[10px] px-2 py-0.5 rounded-full bg-(--status-critical)/20 text-(--status-critical)">{f.dangerous_apis.length} risky call(s)</span>}
                </div>
              </div>
              <p className="text-xs text-(--text-secondary) leading-relaxed">{f.summary}</p>
            </div>
          ))}
        </div>
      </ChartCard>

      {/* ── Memory + Dangerous APIs ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="Memory Usage Analysis" subtitle={<span className="flex items-center gap-1.5"><MemoryStick size={12} /> Allocation / free balance & stack usage</span>}>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <Stat label="Allocations" value={data.memory.allocations} />
            <Stat label="Frees" value={data.memory.frees} />
            <Stat label="Stack Buffers" value={data.memory.stack_buffers.length} />
            <Stat label="Est. Stack Bytes" value={data.memory.stack_bytes_estimate} />
          </div>
          {data.memory.potential_leak && (
            <div className="text-xs p-2.5 rounded-lg bg-(--status-critical)/10 text-(--status-critical) mb-2">⚠ Allocation/free imbalance — possible memory leak ({data.memory.balance} unreleased).</div>
          )}
          {data.memory.potential_double_free_risk && (
            <div className="text-xs p-2.5 rounded-lg bg-(--status-serious)/10 text-(--status-serious) mb-2">⚠ More frees than allocations detected — check for double-free.</div>
          )}
          {data.memory.variable_length_arrays.length > 0 && (
            <div className="text-xs p-2.5 rounded-lg bg-(--status-warning)/10 text-(--status-warning)">
              ⚠ {data.memory.variable_length_arrays.length} variable-length array(s): {data.memory.variable_length_arrays.map(v => v.name).join(", ")}
            </div>
          )}
          {!data.memory.potential_leak && !data.memory.potential_double_free_risk && data.memory.allocations === 0 && (
            <div className="text-xs text-(--text-muted)">No dynamic memory allocation detected.</div>
          )}
        </ChartCard>

        <ChartCard title="Dangerous APIs" subtitle={<span className="flex items-center gap-1.5"><AlertTriangle size={12} /> Known-risky calls detected in this program</span>}>
          {data.dangerous_apis.length === 0 ? (
            <div className="text-xs text-(--status-good) flex items-center gap-1.5 py-4">No dangerous API calls detected.</div>
          ) : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto scrollbar-thin">
              {data.dangerous_apis.map((d) => (
                <div key={d.api} className="flex items-center justify-between p-2.5 rounded-lg bg-(--surface-3)">
                  <div>
                    <span className="mono text-xs font-semibold">{d.api}()</span>
                    <span className="text-[10px] text-(--text-muted) ml-2">&times;{d.count}</span>
                    <div className="text-[11px] text-(--text-muted)">{d.description}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] font-semibold" style={{ color: severityColor(d.severity) }}>{severityLabel(d.severity)}</span>
                    {d.cwe && (
                      <Link to={`/knowledge-base?cwe=${d.cwe}`} className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-full bg-(--surface-2) text-(--accent) hover:bg-(--surface-1)">
                        <BookOpen size={10} /> {d.cwe}
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      {/* ── Pointer + Buffer analysis ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="Pointer Analysis">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Pointer Variables" value={data.pointers.pointer_variables} />
            <Stat label="Dereferences" value={data.pointers.dereferences} />
            <Stat label="Double Pointers" value={data.pointers.double_pointers} />
            <Stat label="NULL Checks" value={data.pointers.null_checks} />
          </div>
          <div className="mt-3">
            <div className="flex justify-between text-xs mb-1"><span className="text-(--text-muted)">Null-check coverage (heuristic)</span><span className="font-semibold">{data.pointers.null_check_coverage_pct}%</span></div>
            <div className="h-1.5 rounded-full bg-(--surface-3) overflow-hidden"><div className="h-full rounded-full bg-(--series-1)" style={{ width: `${Math.min(100, data.pointers.null_check_coverage_pct)}%` }} /></div>
          </div>
        </ChartCard>

        <ChartCard title="Buffer Analysis" subtitle={<span className="flex items-center gap-1.5"><Box size={12} /> Fixed-size buffers and nearby risky usage</span>}>
          {data.buffers.length === 0 ? <div className="text-xs text-(--text-muted) py-4">No fixed-size buffers declared.</div> : (
            <div className="space-y-1.5 max-h-56 overflow-y-auto scrollbar-thin">
              {data.buffers.map((b, i) => (
                <div key={i} className="flex items-center justify-between text-xs p-2 rounded-lg bg-(--surface-3)">
                  <span className="mono">{b.name}[{b.declared_size}] <span className="text-(--text-muted)">L{b.line}</span></span>
                  {b.nearby_risk_lines.length > 0 && <span className="text-[10px] text-(--status-critical)">risk @ L{b.nearby_risk_lines.join(", ")}</span>}
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      {/* ── Loop analysis ─────────────────────────────────────────────────── */}
      <ChartCard title="Loop Analysis" subtitle={<span className="flex items-center gap-1.5"><Repeat size={12} /> Iteration constructs, nesting, and infinite-loop risk</span>} className="mb-5">
        {data.loops.length === 0 ? <div className="text-xs text-(--text-muted)">No loops detected.</div> : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-(--text-muted) uppercase tracking-wider text-[10px]">
                <th className="py-1.5 pr-3">Type</th><th className="py-1.5 pr-3">Line</th><th className="py-1.5 pr-3">Condition</th>
                <th className="py-1.5 pr-3">Loop Depth</th><th className="py-1.5 pr-3">Has Break</th><th className="py-1.5">Flag</th>
              </tr>
            </thead>
            <tbody>
              {data.loops.map((l, i) => (
                <tr key={i} className="border-t border-(--border-hairline)">
                  <td className="py-1.5 pr-3 mono">{l.type}</td>
                  <td className="py-1.5 pr-3 tabular">{l.line}</td>
                  <td className="py-1.5 pr-3 mono text-(--text-secondary)">{l.condition_preview || "—"}</td>
                  <td className="py-1.5 pr-3 tabular">{l.nesting_depth}</td>
                  <td className="py-1.5 pr-3">{l.has_break ? "Yes" : "No"}</td>
                  <td className="py-1.5">{l.possibly_infinite && <span className="text-(--status-critical) font-semibold">possibly infinite</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartCard>

      {/* ── Call graph ────────────────────────────────────────────────────── */}
      <ChartCard title="Call Graph" subtitle={<span className="flex items-center gap-1.5"><GitBranch size={12} /> Interactive — drag nodes, scroll to zoom</span>} className="mb-5">
        <CallGraphView
          nodes={data.call_graph.nodes}
          edges={data.call_graph.edges}
          searchable
          recursiveNames={data.functions.filter((f) => f.is_recursive).map((f) => f.name)}
          deadCodeNames={data.dead_code}
          criticalNames={data.critical_nodes}
        />
      </ChartCard>

      {/* ── CFG ───────────────────────────────────────────────────────────── */}
      <ChartCard
        title="Control Flow Graph"
        subtitle={<span className="flex items-center gap-1.5"><Workflow size={12} /> Approximate CFG for the selected function</span>}
        className="mb-5"
        actions={
          data.cfg.available_functions.length > 1 ? (
            <select
              value={cfgFn ?? data.cfg.function ?? ""}
              onChange={(e) => setCfgFn(e.target.value)}
              className="bg-(--surface-3) border border-(--border-hairline) rounded-lg px-2.5 py-1.5 text-xs focus-ring outline-none"
            >
              {data.cfg.available_functions.map((f) => <option key={f} value={f}>{f}()</option>)}
            </select>
          ) : undefined
        }
      >
        <CfgView nodes={data.cfg.nodes} edges={data.cfg.edges} />
        <div className="flex flex-wrap items-center gap-3 text-[10px] text-(--text-muted) mt-2">
          <Legend color="#0ca30c" label="Entry" /><Legend color="#d03b3b" label="Exit" /><Legend color="#fab219" label="Branch" />
          <Legend color="#9085e9" label="Loop" /><Legend color="#3987e5" label="Return" /><Legend color="#ec835a" label="Break/Continue" />
        </div>
      </ChartCard>

      {/* ── Variable + Function statistics ───────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ChartCard title="Variable Statistics" subtitle={<span className="flex items-center gap-1.5"><Variable size={12} /> Declarations and mutation frequency</span>}>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <Stat label="Declared" value={data.variables.total_declared} />
            <Stat label="Parameters" value={data.variables.parameters} />
            <Stat label="Locals" value={data.variables.locals} />
          </div>
          <div className="text-xs font-semibold mb-1.5 text-(--text-secondary)">Most Mutated</div>
          <div className="space-y-1">
            {data.variables.most_mutated.length === 0 && <div className="text-xs text-(--text-muted)">No reassignments detected.</div>}
            {data.variables.most_mutated.map((v) => (
              <div key={v.name} className="flex justify-between text-xs px-2 py-1 rounded bg-(--surface-3)">
                <span className="mono">{v.name}</span><span className="tabular text-(--text-muted)">{v.count}&times;</span>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Function Statistics" subtitle={<span className="flex items-center gap-1.5"><ListTree size={12} /> Per-function metrics table</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-(--text-muted) uppercase tracking-wider text-[10px]">
                  <th className="py-1.5 pr-3">Function</th><th className="py-1.5 pr-3">LOC</th><th className="py-1.5 pr-3">CC</th>
                  <th className="py-1.5 pr-3">Nesting</th><th className="py-1.5 pr-3">Calls</th><th className="py-1.5">MI</th>
                </tr>
              </thead>
              <tbody>
                {data.functions.map((f) => (
                  <tr key={f.name} className="border-t border-(--border-hairline)">
                    <td className="py-1.5 pr-3 mono font-medium">{f.name}</td>
                    <td className="py-1.5 pr-3 tabular">{f.loc}</td>
                    <td className="py-1.5 pr-3 tabular">{f.cyclomatic_complexity}</td>
                    <td className="py-1.5 pr-3 tabular">{f.max_nesting}</td>
                    <td className="py-1.5 pr-3 tabular">{f.call_count}</td>
                    <td className="py-1.5 tabular">{f.maintainability_index}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>
    </PageShell>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
      <div className="text-lg font-bold tabular mt-0.5">{value}</div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: `${color}33`, border: `1.5px solid ${color}` }} /> {label}</span>;
}
