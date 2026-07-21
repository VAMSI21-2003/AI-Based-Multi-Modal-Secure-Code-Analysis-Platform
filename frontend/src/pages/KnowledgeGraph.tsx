import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Share2, ArrowUpRight, FileCode2, Workflow, AlertTriangle, Bug, PenTool, Square, MemoryStick, Variable,
  Database, Folder, Target,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import { layoutGraph } from "../components/graphs/layout";
import { getBatches, getKnowledgeGraph, type KnowledgeGraphResponse, type KnowledgeNodeKind } from "../api/client";
import { timeAgo } from "../utils/risk";

const KIND_META: Record<KnowledgeNodeKind, { color: string; icon: any; label: string; explain: string }> = {
  repository: { color: "#6b7280", icon: Database, label: "Repository", explain: "The scanned project root — every folder and file in this batch lives beneath it." },
  folder: { color: "#52514e", icon: Folder, label: "Folder", explain: "A directory in the project tree, grouping the files and subfolders beneath it." },
  file: { color: "#3987e5", icon: FileCode2, label: "File", explain: "A scanned source file, analysed independently through the full detection pipeline." },
  function: { color: "#199e70", icon: Workflow, label: "Function", explain: "A function defined in its file, with its own complexity, calls, and dangerous-API usage." },
  cwe: { color: "#d03b3b", icon: AlertTriangle, label: "CWE", explain: "A standard weakness category (MITRE CWE) that a dangerous API call was matched against." },
  dangerous_api: { color: "#e66767", icon: Bug, label: "Dangerous API", explain: "A commonly-misused C/C++ library call detected in the source (e.g. strcpy, malloc, system)." },
  pointer: { color: "#9085e9", icon: PenTool, label: "Pointers", explain: "Aggregate pointer usage for a file — variable count and how much of it is NULL-checked." },
  buffer: { color: "#c98500", icon: Square, label: "Buffer", explain: "A fixed-size stack buffer declaration — a common target for overflow findings nearby." },
  memory: { color: "#d95926", icon: MemoryStick, label: "Memory", explain: "Aggregate allocation/free activity for a file, and whether allocations and frees balance." },
  variable: { color: "#fab219", icon: Variable, label: "Global Variable", explain: "A global variable referenced by one or more functions in this file." },
  prediction: { color: "#8b5cf6", icon: Target, label: "Prediction", explain: "The trained model's verdict for this file — risk level, probability, and confidence." },
};

const RELATION_COLOR: Record<string, string> = {
  contains: "#52514e", calls: "#3987e5", uses: "#9085e9", reads: "#fab219", writes: "#e66767",
  allocates: "#199e70", frees: "#d95926", causes: "#d03b3b", related_to: "#6b7280",
};

const RELATION_EXPLAIN: Record<string, string> = {
  contains: "structurally contains", calls: "calls", uses: "uses", reads: "reads",
  writes: "writes into", allocates: "allocates", frees: "frees", causes: "is classified as",
  related_to: "is related to",
};

export default function KnowledgeGraph() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");
  const [data, setData] = useState<KnowledgeGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);
  const [activeKinds, setActiveKinds] = useState<Set<KnowledgeNodeKind>>(new Set(Object.keys(KIND_META) as KnowledgeNodeKind[]));
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!batchId) { getBatches().then((b) => { if (!cancelled) setBatches(b); }); return () => { cancelled = true; }; }
    setLoading(true);
    setError(null);
    getKnowledgeGraph(batchId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to load knowledge graph"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [batchId]);

  const toggleKind = (k: KnowledgeNodeKind) => {
    setActiveKinds((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });
  };

  if (!batchId) {
    return (
      <PageShell title="Security Knowledge Graph" subtitle="Repository, folders, files, functions, predictions, CWEs, dangerous APIs, pointers, buffers, memory, and globals — one unified graph">
        {!batches ? <Spinner label="Loading projects..." /> : batches.length === 0 ? (
          <EmptyState icon={Share2} title="No multi-file projects scanned yet" description="Scan a folder or zip archive with 2+ files to build its knowledge graph." action={<Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">Go to Code Scanner</Link>} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {batches.map((b) => (
              <button key={b.batch_id} onClick={() => navigate(`/knowledge-graph?batch=${b.batch_id}`)} className="card card-hover p-5 text-left">
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
      <PageShell title="Security Knowledge Graph" subtitle="Repository, folders, files, functions, predictions, CWEs, dangerous APIs, pointers, buffers, memory, and globals — one unified graph">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Building knowledge graph..." />}
      </PageShell>
    );
  }

  const selectedNode = selected ? data.nodes.find((n) => n.id === selected) : null;

  return (
    <PageShell title={`${data.project_name} — Security Knowledge Graph`} subtitle="Hover a node for an explanation — click to open its analysis">
      <div className="flex flex-wrap items-center gap-1.5 mb-4">
        {(Object.keys(KIND_META) as KnowledgeNodeKind[]).map((k) => {
          const meta = KIND_META[k];
          const count = data.kind_counts[k] ?? 0;
          if (count === 0) return null;
          const active = activeKinds.has(k);
          return (
            <button
              key={k}
              onClick={() => toggleKind(k)}
              className="px-2.5 py-1.5 rounded-full text-[11px] font-semibold border transition-colors flex items-center gap-1.5"
              style={active ? { background: `${meta.color}22`, borderColor: `${meta.color}66`, color: meta.color } : { background: "var(--surface-2)", borderColor: "var(--border-hairline)", color: "var(--text-muted)" }}
            >
              <meta.icon size={11} /> {meta.label} <span className="tabular opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-5">
        <ChartCard title="Knowledge Graph" subtitle={`${data.nodes.length} nodes · ${data.edges.length} relationships`}>
          <GraphCanvas data={data} activeKinds={activeKinds} selected={selected} onSelect={setSelected} />
        </ChartCard>

        <ChartCard title="Node Detail" subtitle={selectedNode ? KIND_META[selectedNode.kind].label : "Select a node"}>
          {!selectedNode ? (
            <div className="text-xs text-(--text-muted) py-10 text-center">Click a node in the graph to see its details and jump to the relevant page.</div>
          ) : (
            <NodeDetail node={selectedNode} batchId={batchId} />
          )}
        </ChartCard>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-[11px] text-(--text-muted) mt-4 px-1">
        {Object.entries(RELATION_COLOR).map(([rel, color]) => (
          <span key={rel} className="flex items-center gap-1.5" title={RELATION_EXPLAIN[rel]}>
            <span className="w-4 h-0.5" style={{ background: color }} /> {rel}
          </span>
        ))}
      </div>
    </PageShell>
  );
}

const WIDE_KINDS = new Set<KnowledgeNodeKind>(["file", "repository", "folder"]);
const PILL_KINDS = new Set<KnowledgeNodeKind>(["cwe", "dangerous_api", "prediction"]);

function describeNode(node: any): string | null {
  switch (node.kind as KnowledgeNodeKind) {
    case "repository": return `${node.total_files} file(s) in this project`;
    case "folder": return node.path;
    case "file": return `${node.risk_level} · ${node.vuln_probability?.toFixed(1)}% risk`;
    case "function": return `${node.loc} LOC · complexity ${node.complexity}`;
    case "cwe": return `${node.name} · ${node.severity} severity`;
    case "buffer": return `declared at line ${node.line}`;
    case "memory": return `${node.allocations} alloc(s), ${node.frees} free(s)${node.leak_risk ? " — possible leak" : ""}`;
    case "pointer": return `${node.count} pointer var(s), ${node.coverage}% NULL-checked`;
    case "prediction": return `${node.confidence?.toFixed(1)}% confidence`;
    case "variable": return `global in ${node.file}`;
    default: return null;
  }
}

// dagre's layout algorithm runs synchronously on the main thread with no
// yielding. On a real repository scan (hundreds of files) the knowledge
// graph can easily reach 5,000-10,000+ nodes once functions, pointers,
// buffers, and variables are all included -- laying that out directly
// freezes the tab for minutes. Cap what actually reaches dagre; the kind
// filters above remain the way to deliberately see more of one category.
const MAX_LAID_OUT_NODES = 350;
const KIND_PRIORITY: KnowledgeNodeKind[] = [
  "repository", "folder", "prediction", "cwe", "dangerous_api", "file", "memory", "pointer", "buffer", "variable", "function",
];

function GraphCanvas({ data, activeKinds, selected, onSelect }: {
  data: KnowledgeGraphResponse; activeKinds: Set<KnowledgeNodeKind>; selected: string | null; onSelect: (id: string) => void;
}) {
  const [hover, setHover] = useState<{ node: any; x: number; y: number } | null>(null);

  const { laidNodes, laidEdges, truncated, totalVisible } = useMemo(() => {
    let visibleNodes = data.nodes.filter((n) => activeKinds.has(n.kind));
    const totalVisible = visibleNodes.length;
    let truncated = false;
    if (visibleNodes.length > MAX_LAID_OUT_NODES) {
      truncated = true;
      const byKind = new Map<KnowledgeNodeKind, typeof visibleNodes>();
      for (const n of visibleNodes) {
        if (!byKind.has(n.kind)) byKind.set(n.kind, []);
        byKind.get(n.kind)!.push(n);
      }
      const kept: typeof visibleNodes = [];
      for (const kind of KIND_PRIORITY) {
        const group = byKind.get(kind);
        if (!group) continue;
        const remaining = MAX_LAID_OUT_NODES - kept.length;
        if (remaining <= 0) break;
        kept.push(...group.slice(0, remaining));
      }
      visibleNodes = kept;
    }
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    const visibleEdges = data.edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));

    const rfNodes = visibleNodes.map((n) => {
      const meta = KIND_META[n.kind];
      const isSelected = n.id === selected;
      const width = WIDE_KINDS.has(n.kind) ? 170 : 140;
      return {
        id: n.id,
        data: { label: n.label },
        position: { x: 0, y: 0 },
        width,
        height: 40,
        style: {
          background: `${meta.color}1f`,
          border: `${isSelected ? 2.5 : 1.5}px solid ${meta.color}${isSelected ? "" : "88"}`,
          borderRadius: PILL_KINDS.has(n.kind) ? 20 : 8,
          color: "#fff", fontSize: 11, fontFamily: "ui-monospace, monospace", padding: 6,
          width, textAlign: "center" as const,
          boxShadow: isSelected ? `0 0 16px ${meta.color}` : undefined,
        },
      };
    });
    const rfEdges = visibleEdges.map((e, i) => {
      const color = RELATION_COLOR[e.relation] ?? "#52514e";
      return {
        id: `kge${i}`, source: e.source, target: e.target,
        style: { stroke: color, strokeWidth: 1.3 },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 12, height: 12 },
      };
    });
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "TB");
    return { laidNodes: ln, laidEdges: le, truncated, totalVisible };
  }, [data, activeKinds, selected]);

  if (laidNodes.length === 0) {
    return <div className="h-[320px] flex items-center justify-center text-sm text-(--text-muted)">No nodes match the active filters.</div>;
  }

  const hoverData = hover ? data.nodes.find((n) => n.id === hover.node.id) : null;
  const hoverMeta = hoverData ? KIND_META[hoverData.kind as KnowledgeNodeKind] : null;

  return (
    <div>
      {truncated && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-(--status-warning)/10 border border-(--status-warning)/30 text-xs text-(--status-warning)">
          Showing {laidNodes.length} of {totalVisible} nodes — this graph is too large to render in full. Use the filters above to narrow down to specific kinds.
        </div>
      )}
      <div className="relative rounded-lg overflow-hidden border border-(--border-hairline)" style={{ height: 580 }}>
      <ReactFlow
        nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark"
        nodesDraggable nodesConnectable={false}
        onNodeClick={(_e, node) => onSelect(node.id)}
        onNodeMouseEnter={(e, node) => setHover({ node, x: e.clientX, y: e.clientY })}
        onNodeMouseMove={(e, node) => setHover({ node, x: e.clientX, y: e.clientY })}
        onNodeMouseLeave={() => setHover(null)}
      >
        <Background color="#2c2c2a" gap={18} />
        <Controls showInteractive={false} />
        <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
      </ReactFlow>
      {hoverData && hoverMeta && (
        <div
          className="fixed z-50 pointer-events-none max-w-xs rounded-lg border border-(--border-hairline-strong) p-3 text-xs"
          style={{ left: hover!.x + 16, top: hover!.y + 16, background: "rgba(20,20,24,0.97)", boxShadow: "0 12px 30px -8px rgba(0,0,0,0.6)" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <hoverMeta.icon size={12} style={{ color: hoverMeta.color }} />
            <span className="font-semibold mono">{hoverData.label}</span>
          </div>
          <div className="text-(--text-muted) mb-1">{hoverMeta.label}</div>
          <div className="text-(--text-secondary)">{hoverMeta.explain}</div>
          {describeNode(hoverData) && <div className="text-(--text-secondary) mt-1 tabular">{describeNode(hoverData)}</div>}
        </div>
      )}
      </div>
    </div>
  );
}

function NodeDetail({ node, batchId }: { node: any; batchId: string }) {
  const meta = KIND_META[node.kind as KnowledgeNodeKind];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${meta.color}26` }}>
          <meta.icon size={15} style={{ color: meta.color }} />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold mono truncate">{node.label}</div>
          <div className="text-[11px] text-(--text-muted)">{meta.label}</div>
        </div>
      </div>
      <div className="text-xs text-(--text-secondary) mb-2">{meta.explain}</div>
      <div className="space-y-1.5 text-xs">
        {describeNode(node) && <div className="text-(--text-secondary) tabular">{describeNode(node)}</div>}
      </div>
      <div className="pt-2 border-t border-(--border-hairline) flex flex-col gap-1.5 items-start">
        {node.kind === "repository" && <Link to={`/project-scanner?batch=${batchId}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open Repository Scanner <ArrowUpRight size={11} /></Link>}
        {node.kind === "folder" && <Link to={`/file-explorer?batch=${batchId}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open in File Explorer <ArrowUpRight size={11} /></Link>}
        {node.kind === "file" && <Link to={`/file-explorer?batch=${batchId}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open in File Explorer <ArrowUpRight size={11} /></Link>}
        {node.kind === "file" && node.scan_id && <Link to={`/analysis?scan=${node.scan_id}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open Full Analysis <ArrowUpRight size={11} /></Link>}
        {node.kind === "prediction" && node.scan_id && <Link to={`/analysis?scan=${node.scan_id}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open Full Analysis <ArrowUpRight size={11} /></Link>}
        {node.kind === "function" && <Link to={`/call-graph-explorer?batch=${batchId}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open in Call Graph Explorer <ArrowUpRight size={11} /></Link>}
        {node.kind === "cwe" && <Link to={`/knowledge-base?cwe=${node.label}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open in Knowledge Base <ArrowUpRight size={11} /></Link>}
        {node.kind === "dangerous_api" && <Link to="/copilot" className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Ask Security Copilot about this API <ArrowUpRight size={11} /></Link>}
        {(node.kind === "pointer" || node.kind === "memory" || node.kind === "buffer" || node.kind === "variable") && <Link to={`/dependency-graph?batch=${batchId}`} className="text-xs text-(--accent) hover:underline inline-flex items-center gap-1">Open in Dependency Graph <ArrowUpRight size={11} /></Link>}
      </div>
    </div>
  );
}
