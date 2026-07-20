import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Network, FolderGit2, FileCode2, Workflow, GitBranch, ArrowUpRight, AlertTriangle, Info,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import StatCard from "../components/StatCard";
import { Spinner, EmptyState } from "../components/Loading";
import { layoutGraph } from "../components/graphs/layout";
import { getBatches, getDependencyGraph, type DependencyGraph } from "../api/client";
import { RISK_HEX, timeAgo } from "../utils/risk";

export default function DependencyGraphPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");
  const [data, setData] = useState<DependencyGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);
  const [view, setView] = useState<"files" | "functions">("files");

  useEffect(() => {
    if (!batchId) {
      getBatches().then(setBatches);
      return;
    }
    setLoading(true);
    setError(null);
    getDependencyGraph(batchId)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Failed to load dependency graph"))
      .finally(() => setLoading(false));
  }, [batchId]);

  if (!batchId) {
    return (
      <PageShell title="Dependency Graph" subtitle="Cross-file function calls, #include relationships, and dependency cycles">
        {!batches ? <Spinner label="Loading projects..." /> : batches.length === 0 ? (
          <EmptyState
            icon={FolderGit2}
            title="No multi-file projects scanned yet"
            description="Scan a folder or zip archive with 2+ files from Code Scanner → Batch Upload to see its dependency graph here."
            action={<Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">Go to Code Scanner</Link>}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {batches.map((b) => (
              <button key={b.batch_id} onClick={() => navigate(`/dependency-graph?batch=${b.batch_id}`)} className="card card-hover p-5 text-left">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-semibold">{b.project_name}</div>
                  <ArrowUpRight size={14} className="text-(--text-muted)" />
                </div>
                <div className="text-xs text-(--text-muted)">{b.total_files} files &middot; {timeAgo(b.created_at)}</div>
              </button>
            ))}
          </div>
        )}
      </PageShell>
    );
  }

  if (loading || !data) {
    return (
      <PageShell title="Dependency Graph" subtitle="Cross-file function calls, #include relationships, and dependency cycles">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Building dependency graph..." />}
      </PageShell>
    );
  }

  const cycles = view === "files" ? data.file_cycles : data.function_cycles;

  return (
    <PageShell
      title={`${data.project_name} — Dependency Graph`}
      subtitle="Cross-file function calls, #include relationships, and dependency cycles"
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Files" value={data.stats.total_files} icon={FileCode2} accent="var(--series-1)" />
        <StatCard label="Functions" value={data.stats.total_functions} icon={Workflow} accent="var(--series-7)" />
        <StatCard label="Cross-File Calls" value={data.stats.cross_file_edges} icon={Network} accent="var(--series-4)" />
        <StatCard label="Cycles Detected" value={data.stats.file_cycles_detected + data.stats.function_cycles_detected} icon={GitBranch} accent={data.stats.file_cycles_detected + data.stats.function_cycles_detected > 0 ? "var(--status-critical)" : "var(--status-good)"} />
      </div>

      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => setView("files")} className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${view === "files" ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary) hover:bg-(--surface-3)"}`}>
          File Dependencies (#include)
        </button>
        <button onClick={() => setView("functions")} className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${view === "functions" ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary) hover:bg-(--surface-3)"}`}>
          Cross-File Function Calls
        </button>
      </div>

      <ChartCard title={view === "files" ? "File Dependency Graph" : "Function Call Graph (cross-file)"} subtitle={view === "files" ? "Local #include relationships between scanned files" : "Function calls that cross a file boundary, colour-coded by owning file's risk"} className="mb-5">
        {view === "files" ? <FileGraph data={data} /> : <FunctionGraph data={data} />}
      </ChartCard>

      {cycles.length > 0 && (
        <ChartCard title={`Dependency Cycles (${cycles.length})`} subtitle="Circular dependencies -- these make the codebase harder to reason about and can indicate tangled ownership">
          <div className="space-y-2">
            {cycles.map((cycle, i) => (
              <div key={i} className="flex items-center gap-2 flex-wrap text-xs mono p-2.5 rounded-lg bg-(--status-critical)/10 border border-(--status-critical)/25">
                <AlertTriangle size={13} className="text-(--status-critical) shrink-0" />
                {cycle.map((n, j) => (
                  <span key={j} className="flex items-center gap-2">
                    <span className="text-(--text-primary)">{n.split("::").pop()}</span>
                    {j < cycle.length - 1 && <span className="text-(--status-critical)">&rarr;</span>}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </ChartCard>
      )}

      <div className="flex items-start gap-2 mt-5 text-xs text-(--text-muted) px-1">
        <Info size={13} className="shrink-0 mt-0.5" />
        {data.note}
      </div>
    </PageShell>
  );
}

function FileGraph({ data }: { data: DependencyGraph }) {
  const cycleEdgeKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const cycle of data.file_cycles) {
      for (let i = 0; i < cycle.length - 1; i++) keys.add(`${cycle[i]}->${cycle[i + 1]}`);
    }
    return keys;
  }, [data.file_cycles]);

  const { laidNodes, laidEdges } = useMemo(() => {
    const rfNodes = data.file_nodes.map((n) => {
      const color = RISK_HEX[n.risk_level] ?? "#898781";
      return {
        id: n.id,
        data: { label: n.label },
        position: { x: 0, y: 0 },
        width: 160,
        height: 44,
        style: {
          background: `${color}1f`, border: `1.5px solid ${color}88`, borderRadius: 8,
          color: "#fff", fontSize: 12, fontFamily: "ui-monospace, monospace", padding: 6,
          width: 160, textAlign: "center" as const,
        },
      };
    });
    const rfEdges = data.file_edges.map((e, i) => {
      const isCycle = cycleEdgeKeys.has(`${e.source}->${e.target}`);
      return {
        id: `fe${i}`, source: e.source, target: e.target,
        style: { stroke: isCycle ? "#d03b3b" : "#52514e", strokeWidth: isCycle ? 2.5 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isCycle ? "#d03b3b" : "#52514e", width: 16, height: 16 },
      };
    });
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "LR");
    return { laidNodes: ln, laidEdges: le };
  }, [data.file_nodes, data.file_edges, cycleEdgeKeys]);

  if (data.file_nodes.length === 0) return <div className="h-[320px] flex items-center justify-center text-sm text-(--text-muted)">No files in this project.</div>;
  if (data.file_edges.length === 0) return (
    <div className="h-[200px] flex flex-col items-center justify-center text-sm text-(--text-muted) gap-1">
      <div>No local #include relationships detected between the scanned files.</div>
      <div className="text-xs">(Each file only includes system/library headers, or headers weren't part of this batch.)</div>
    </div>
  );

  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)" style={{ height: 420 }}>
      <ReactFlow nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark" nodesDraggable nodesConnectable={false}>
        <Background color="#2c2c2a" gap={18} />
        <Controls showInteractive={false} />
        <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
      </ReactFlow>
    </div>
  );
}

function FunctionGraph({ data }: { data: DependencyGraph }) {
  const cycleEdgeKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const cycle of data.function_cycles) {
      for (let i = 0; i < cycle.length - 1; i++) keys.add(`${cycle[i]}->${cycle[i + 1]}`);
    }
    return keys;
  }, [data.function_cycles]);

  const crossFileNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of data.function_edges) { ids.add(e.source); ids.add(e.target); }
    return ids;
  }, [data.function_edges]);

  const { laidNodes, laidEdges } = useMemo(() => {
    const visibleNodes = data.function_nodes.filter((n) => crossFileNodeIds.has(n.id));
    const rfNodes = visibleNodes.map((n) => {
      const color = n.kind === "dangerous" ? "#d03b3b" : n.kind === "complex" ? "#fab219" : (RISK_HEX[n.risk_level] ?? "#3987e5");
      return {
        id: n.id,
        data: { label: `${n.label}\n(${n.file})` },
        position: { x: 0, y: 0 },
        width: 170,
        height: 46,
        style: {
          background: `${color}1f`, border: `1.5px solid ${color}88`, borderRadius: 8,
          color: "#fff", fontSize: 11, fontFamily: "ui-monospace, monospace", padding: 6,
          width: 170, textAlign: "center" as const, whiteSpace: "pre-line" as const,
        },
      };
    });
    const rfEdges = data.function_edges.map((e, i) => {
      const isCycle = cycleEdgeKeys.has(`${e.source}->${e.target}`);
      return {
        id: `fne${i}`, source: e.source, target: e.target,
        style: { stroke: isCycle ? "#d03b3b" : (e.cross_file ? "#9085e9" : "#52514e"), strokeWidth: isCycle ? 2.5 : 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isCycle ? "#d03b3b" : (e.cross_file ? "#9085e9" : "#52514e"), width: 16, height: 16 },
      };
    });
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "LR");
    return { laidNodes: ln, laidEdges: le };
  }, [data.function_nodes, data.function_edges, cycleEdgeKeys, crossFileNodeIds]);

  if (laidNodes.length === 0) return (
    <div className="h-[200px] flex flex-col items-center justify-center text-sm text-(--text-muted) gap-1">
      <div>No cross-file function calls detected.</div>
      <div className="text-xs">Every call in this project resolves within its own file (or to an external/library function).</div>
    </div>
  );

  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <div style={{ height: 420 }}>
        <ReactFlow nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark" nodesDraggable nodesConnectable={false}>
          <Background color="#2c2c2a" gap={18} />
          <Controls showInteractive={false} />
          <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[11px] text-(--text-muted) px-3 py-2 border-t border-(--border-hairline) bg-(--surface-2)">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border border-(--status-critical)" style={{ background: "rgba(208,59,59,0.2)" }} /> Uses dangerous API</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border" style={{ borderColor: "#fab219", background: "rgba(250,178,25,0.2)" }} /> High complexity</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border-2" style={{ borderColor: "#d03b3b" }} /> Part of a cycle</span>
      </div>
    </div>
  );
}
