import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  FolderGit2, Search, Layers, Flame, ArrowUpRight, Globe2, PenTool, Repeat,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import { layoutGraph } from "../components/graphs/layout";
import { getBatches, getDependencyGraph, type DependencyGraph, type DependencyFunctionNode } from "../api/client";
import { timeAgo } from "../utils/risk";

export default function CallGraphExplorer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");
  const [data, setData] = useState<DependencyGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);
  const [query, setQuery] = useState("");
  const [collapseLeaves, setCollapseLeaves] = useState(false);
  const [highlightDangerous, setHighlightDangerous] = useState(true);

  useEffect(() => {
    if (!batchId) { getBatches().then(setBatches); return; }
    setLoading(true);
    setError(null);
    getDependencyGraph(batchId)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Failed to load call graph"))
      .finally(() => setLoading(false));
  }, [batchId]);

  if (!batchId) {
    return (
      <PageShell title="Call Graph Explorer" subtitle="Every function in the project, who calls whom, recursion, shared globals, and pointer flow">
        {!batches ? <Spinner label="Loading projects..." /> : batches.length === 0 ? (
          <EmptyState icon={FolderGit2} title="No multi-file projects scanned yet" description="Scan a folder or zip archive with 2+ files to explore its call graph." action={<Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">Go to Code Scanner</Link>} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {batches.map((b) => (
              <button key={b.batch_id} onClick={() => navigate(`/call-graph-explorer?batch=${b.batch_id}`)} className="card card-hover p-5 text-left">
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
      <PageShell title="Call Graph Explorer" subtitle="Every function in the project, who calls whom, recursion, shared globals, and pointer flow">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Building call graph..." />}
      </PageShell>
    );
  }

  return (
    <PageShell title={`${data.project_name} — Call Graph Explorer`} subtitle="Every function, who calls whom, recursion, shared globals, and pointer flow">
      <div className="flex flex-col md:flex-row items-start md:items-center gap-3 mb-4">
        <div className="relative flex-1 w-full md:w-auto">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-muted)" />
          <input
            value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search function names..."
            className="w-full md:w-72 bg-(--surface-3) border border-(--border-hairline) rounded-lg pl-8 pr-3 py-2 text-xs mono focus-ring outline-none"
          />
        </div>
        <button onClick={() => setCollapseLeaves((c) => !c)} className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition-colors ${collapseLeaves ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary)"}`}>
          <Layers size={13} /> Collapse leaf nodes
        </button>
        <button onClick={() => setHighlightDangerous((h) => !h)} className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold border transition-colors ${highlightDangerous ? "bg-(--status-critical)/15 border-(--status-critical)/40 text-(--status-critical)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary)"}`}>
          <Flame size={13} /> Highlight dangerous call chains
        </button>
        <div className="text-xs text-(--text-muted) md:ml-auto">{data.function_nodes.length} functions &middot; {data.function_edges.length} calls</div>
      </div>

      <ChartCard title="Call Graph" subtitle="Every same-file and cross-file function call in this project — drag to rearrange, scroll to zoom">
        <CallGraphCanvas data={data} query={query} collapseLeaves={collapseLeaves} highlightDangerous={highlightDangerous} />
      </ChartCard>
    </PageShell>
  );
}

function CallGraphCanvas({ data, query, collapseLeaves, highlightDangerous }: {
  data: DependencyGraph; query: string; collapseLeaves: boolean; highlightDangerous: boolean;
}) {
  const q = query.trim().toLowerCase();

  const dangerousChainNodes = useMemo(() => {
    if (!highlightDangerous) return new Set<string>();
    const reverse = new Map<string, string[]>();
    for (const e of data.function_edges) {
      if (!reverse.has(e.target)) reverse.set(e.target, []);
      reverse.get(e.target)!.push(e.source);
    }
    const dangerous = data.function_nodes.filter((n) => n.kind === "dangerous").map((n) => n.id);
    const visited = new Set<string>();
    const queue = [...dangerous];
    while (queue.length) {
      const cur = queue.pop()!;
      if (visited.has(cur)) continue;
      visited.add(cur);
      for (const caller of reverse.get(cur) ?? []) queue.push(caller);
    }
    return visited;
  }, [data, highlightDangerous]);

  const { nodes: visibleNodes, edges: visibleEdges } = useMemo(() => {
    const edgeCount = new Map<string, number>();
    for (const e of data.function_edges) {
      edgeCount.set(e.source, (edgeCount.get(e.source) ?? 0) + 1);
      edgeCount.set(e.target, (edgeCount.get(e.target) ?? 0) + 1);
    }
    let nodes = data.function_nodes;
    if (collapseLeaves) nodes = nodes.filter((n) => (edgeCount.get(n.id) ?? 0) > 0);
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = data.function_edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    return { nodes, edges };
  }, [data, collapseLeaves]);

  const { laidNodes, laidEdges } = useMemo(() => {
    const rfNodes = visibleNodes.map((n: DependencyFunctionNode) => {
      const matches = !q || n.label.toLowerCase().includes(q);
      const inChain = dangerousChainNodes.has(n.id);
      let color = n.kind === "dangerous" ? "#d03b3b" : n.kind === "complex" ? "#fab219" : "#3987e5";
      const badges: string[] = [];
      if (n.is_recursive) badges.push("↻");
      if ((n.global_refs?.length ?? 0) > 0) badges.push("🌐");
      if ((n.pointer_ops ?? 0) > 0) badges.push("→*");
      const label = `${n.label}${badges.length ? "  " + badges.join(" ") : ""}\n${n.file.split(/[\\/]/).pop()}`;
      return {
        id: n.id,
        data: { label },
        position: { x: 0, y: 0 },
        width: 175,
        height: 50,
        style: {
          background: `${color}1f`,
          border: `${highlightDangerous && inChain ? 2.5 : 1.5}px solid ${highlightDangerous && inChain ? "#d03b3b" : `${color}88`}`,
          borderRadius: 8, color: "#fff", fontSize: 11, fontFamily: "ui-monospace, monospace", padding: 6,
          width: 175, textAlign: "center" as const, whiteSpace: "pre-line" as const,
          opacity: matches ? 1 : 0.2,
          boxShadow: highlightDangerous && inChain ? "0 0 16px rgba(208,59,59,0.5)" : undefined,
        },
      };
    });
    const rfEdges = visibleEdges.map((e, i) => {
      const inChain = highlightDangerous && dangerousChainNodes.has(e.source) && dangerousChainNodes.has(e.target);
      const color = inChain ? "#d03b3b" : e.cross_file ? "#9085e9" : "#52514e";
      return {
        id: `cge${i}`, source: e.source, target: e.target,
        style: { stroke: color, strokeWidth: inChain ? 2.2 : 1.4 },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
      };
    });
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "TB");
    return { laidNodes: ln, laidEdges: le };
  }, [visibleNodes, visibleEdges, q, dangerousChainNodes, highlightDangerous]);

  if (visibleNodes.length === 0) {
    return <div className="h-[320px] flex items-center justify-center text-sm text-(--text-muted)">No functions to display{collapseLeaves ? " (try disabling \"Collapse leaf nodes\")" : ""}.</div>;
  }

  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <div style={{ height: 560 }}>
        <ReactFlow nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark" nodesDraggable nodesConnectable={false}>
          <Background color="#2c2c2a" gap={18} />
          <Controls showInteractive={false} />
          <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[11px] text-(--text-muted) px-3 py-2 border-t border-(--border-hairline) bg-(--surface-2)">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border border-(--status-critical)" style={{ background: "rgba(208,59,59,0.2)" }} /> Dangerous API</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border" style={{ borderColor: "#fab219", background: "rgba(250,178,25,0.2)" }} /> High complexity</span>
        <span className="flex items-center gap-1.5"><Repeat size={11} /> ↻ recursive</span>
        <span className="flex items-center gap-1.5"><Globe2 size={11} /> 🌐 references a global variable</span>
        <span className="flex items-center gap-1.5"><PenTool size={11} /> →* uses pointers</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-0.5" style={{ background: "#9085e9" }} /> cross-file call</span>
      </div>
    </div>
  );
}
