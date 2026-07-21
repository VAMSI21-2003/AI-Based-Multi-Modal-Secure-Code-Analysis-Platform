import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { Folder, FolderOpen, FileCode2, ChevronRight, ChevronDown, ExternalLink, Code2 } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import RiskBadge from "../components/RiskBadge";
import { getProjectSummary, getBatches, getCodeIntelligence, type ProjectSummary, type ScanResult, type CodeIntelligence } from "../api/client";
import { RISK_HEX } from "../utils/risk";

interface TreeNode { name: string; path: string; children: Map<string, TreeNode>; file?: ScanResult; avgRisk?: number; worstRisk?: string; fileCount?: number; }

function buildTree(files: ScanResult[]): TreeNode {
  const root: TreeNode = { name: "", path: "", children: new Map() };
  for (const f of files) {
    const parts = f.filename.split(/[\\/]/);
    let node = root;
    let path = "";
    parts.forEach((part, i) => {
      path = path ? `${path}/${part}` : part;
      if (!node.children.has(part)) node.children.set(part, { name: part, path, children: new Map() });
      node = node.children.get(part)!;
      if (i === parts.length - 1) node.file = f;
    });
  }
  computeFolderScores(root);
  return root;
}

const RISK_RANK: Record<string, number> = { SAFE: 0, "LOW RISK": 1, "MEDIUM RISK": 2, "HIGH RISK": 3, CRITICAL: 4 };

// Post-order: every folder's score is the average vuln_probability of every
// file beneath it (real, already-computed per-scan values -- no new model).
function computeFolderScores(node: TreeNode): { sum: number; count: number; worst: string } {
  if (node.file) {
    node.avgRisk = node.file.vuln_probability;
    node.worstRisk = node.file.risk_level;
    node.fileCount = 1;
    return { sum: node.file.vuln_probability, count: 1, worst: node.file.risk_level };
  }
  let sum = 0, count = 0, worst = "SAFE";
  for (const child of node.children.values()) {
    const r = computeFolderScores(child);
    sum += r.sum; count += r.count;
    if (RISK_RANK[r.worst] > RISK_RANK[worst]) worst = r.worst;
  }
  if (count > 0) { node.avgRisk = sum / count; node.worstRisk = worst; node.fileCount = count; }
  return { sum, count, worst };
}

export default function FileExplorer() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");
  const [data, setData] = useState<ProjectSummary | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<ScanResult | null>(null);
  const [intel, setIntel] = useState<CodeIntelligence | null>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    if (!batchId) { getBatches().then((b) => { if (!cancelled) setBatches(b); }); return () => { cancelled = true; }; }
    getProjectSummary(batchId).then((d) => {
      if (cancelled) return;
      setData(d);
      setExpanded(new Set(["__root__"]));
    });
    return () => { cancelled = true; };
  }, [batchId]);

  const tree = useMemo(() => (data ? buildTree(data.files) : null), [data]);

  const selectFile = (f: ScanResult) => {
    setSelected(f);
    setIntel(null);
    setIntelLoading(true);
    getCodeIntelligence(f.id).then(setIntel).finally(() => setIntelLoading(false));
  };

  const toggle = (path: string) => setExpanded((s) => { const n = new Set(s); n.has(path) ? n.delete(path) : n.add(path); return n; });

  if (!batchId) {
    return (
      <PageShell title="File Explorer" subtitle="Interactive project tree — risk, complexity, LOC, functions, security score">
        {!batches ? <Spinner label="Loading projects..." /> : batches.length === 0 ? (
          <EmptyState icon={Folder} title="No projects yet" description="Batch-scan a project first (Code Scanner → Batch Upload)." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {batches.map((b) => (
              <button key={b.batch_id} onClick={() => navigate(`/file-explorer?batch=${b.batch_id}`)} className="card card-hover p-5 text-left">
                <div className="text-sm font-semibold">{b.project_name}</div>
                <div className="text-xs text-(--text-muted) mt-1">{b.total_files} files</div>
              </button>
            ))}
          </div>
        )}
      </PageShell>
    );
  }

  if (!data || !tree) return <PageShell title="File Explorer" subtitle="Loading project"><Spinner label="Loading project tree..." /></PageShell>;

  return (
    <PageShell title={data.project_name} subtitle="File Explorer">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <ChartCard title="Project Tree" className="xl:col-span-1">
          <div className="text-xs">
            <TreeView node={tree} depth={0} expanded={expanded} toggle={toggle} onSelect={selectFile} selected={selected} />
          </div>
        </ChartCard>

        <div className="xl:col-span-2">
          {!selected ? (
            <EmptyState icon={FileCode2} title="Select a file" description="Choose a file from the tree to see its risk, complexity, and structure." />
          ) : (
            <div className="space-y-5">
              <ChartCard title={selected.filename} subtitle={selected.project_name}
                actions={
                  <div className="flex items-center gap-3">
                    <Link to={`/scan-center?tab=live-ide&scan=${selected.id}`} className="inline-flex items-center gap-1.5 text-xs text-(--accent) hover:underline"><Code2 size={12} /> Open in Live IDE</Link>
                    <Link to={`/analysis?scan=${selected.id}`} className="inline-flex items-center gap-1.5 text-xs text-(--accent) hover:underline"><ExternalLink size={12} /> Full Analysis</Link>
                  </div>
                }
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Stat label="Risk" value={<RiskBadge level={selected.risk_level} size="sm" />} />
                  <Stat label="Vuln Probability" value={`${selected.vuln_probability.toFixed(1)}%`} />
                  <Stat label="LOC" value={selected.loc} />
                  <Stat label="Lines" value={selected.lines} />
                </div>
              </ChartCard>

              <ChartCard title="Code Intelligence" subtitle="Complexity, functions, and composite scores (loaded on demand)">
                {intelLoading ? <Spinner label="Analysing..." /> : !intel?.available ? (
                  <div className="text-xs text-(--text-muted)">Not available for this file.</div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Stat label="Functions" value={intel.function_count} />
                    <Stat label="Avg. Complexity" value={intel.scores.cyclomatic_complexity_avg ?? "-"} />
                    <Stat label="Quality Score" value={`${intel.scores.quality}%`} />
                    <Stat label="Security Score" value={`${intel.scores.security_score}%`} />
                  </div>
                )}
              </ChartCard>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
      <div className="text-sm font-bold mt-1">{value}</div>
    </div>
  );
}

function TreeView({ node, depth, expanded, toggle, onSelect, selected }: {
  node: TreeNode; depth: number; expanded: Set<string>; toggle: (p: string) => void; onSelect: (f: ScanResult) => void; selected: ScanResult | null;
}) {
  const folders = Array.from(node.children.values()).filter((c) => c.children.size > 0 || !c.file);
  const files = Array.from(node.children.values()).filter((c) => c.file);
  const isRoot = depth === 0;
  const isOpen = isRoot || expanded.has(node.path);

  return (
    <div>
      {!isRoot && (
        <button onClick={() => toggle(node.path)} className="w-full flex items-center gap-1.5 py-1 rounded hover:bg-(--surface-3)" style={{ paddingLeft: depth * 14 }} title={node.worstRisk ? `Folder average: ${node.avgRisk?.toFixed(0)}% risk · worst file: ${node.worstRisk}` : undefined}>
          {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {isOpen ? <FolderOpen size={13} style={{ color: node.worstRisk ? RISK_HEX[node.worstRisk] : "var(--series-4)" }} /> : <Folder size={13} style={{ color: node.worstRisk ? RISK_HEX[node.worstRisk] : "var(--series-4)" }} />}
          <span className="truncate flex-1 text-left">{node.name}</span>
          {node.avgRisk !== undefined && (
            <span className="text-[10px] tabular text-(--text-muted) shrink-0">{node.avgRisk.toFixed(0)}%</span>
          )}
        </button>
      )}
      {isOpen && (
        <div>
          {folders.map((child) => (
            <TreeView key={child.path} node={child} depth={depth + 1} expanded={expanded} toggle={toggle} onSelect={onSelect} selected={selected} />
          ))}
          {files.map((child) => (
            <button
              key={child.path}
              onClick={() => child.file && onSelect(child.file)}
              className={`w-full flex items-center gap-1.5 py-1 rounded hover:bg-(--surface-3) ${selected?.id === child.file?.id ? "bg-(--surface-3)" : ""}`}
              style={{ paddingLeft: (depth + 1) * 14 }}
            >
              <FileCode2 size={12} className="text-(--text-muted)" />
              <span className="truncate mono flex-1 text-left">{child.name}</span>
              {child.file && <span className="w-2 h-2 rounded-full shrink-0" style={{ background: RISK_HEX[child.file.risk_level] }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
