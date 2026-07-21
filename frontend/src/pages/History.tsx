import { useEffect, useRef, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Search, Download, Trash2, ArrowUpDown, ChevronLeft, ChevronRight, History as HistoryIcon, Eye,
  Pin, PinOff, Tag as TagIcon, X,
} from "lucide-react";
import toast from "react-hot-toast";
import PageShell from "../components/PageShell";
import { Spinner, EmptyState } from "../components/Loading";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import { getHistory, deleteScan, exportHistoryUrl, togglePin, setScanTags, type ScanResult } from "../api/client";
import { timeAgo } from "../utils/risk";

const PAGE_SIZE = 15;

export default function HistoryPage() {
  const [results, setResults] = useState<ScanResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [projects, setProjects] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [verdict, setVerdict] = useState("");
  const [project, setProject] = useState("");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [tagFilter, setTagFilter] = useState("");
  const [sort, setSort] = useState("date");
  const [order, setOrder] = useState("desc");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [editingTagsFor, setEditingTagsFor] = useState<string | null>(null);
  const [tagDraft, setTagDraft] = useState("");

  // Rapid filter changes (e.g. typing in the search box) can fire several
  // overlapping getHistory() requests -- a monotonic sequence number (same
  // pattern already used in LiveIDE.tsx's live-scan debounce) ensures only
  // the LATEST request's response is ever applied, regardless of the order
  // responses actually arrive back in.
  const loadSeqRef = useRef(0);

  const load = useCallback(() => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    getHistory({
      search: search || undefined, risk_level: riskLevel || undefined, verdict: verdict || undefined,
      project: project || undefined, pinned: pinnedOnly || undefined, tag: tagFilter || undefined,
      sort, order, limit: PAGE_SIZE, offset,
    }).then((d) => {
      if (seq !== loadSeqRef.current) return;
      setResults(d.results); setTotal(d.total); setProjects(d.projects); setAllTags(d.tags || []);
    }).finally(() => { if (seq === loadSeqRef.current) setLoading(false); });
  }, [search, riskLevel, verdict, project, pinnedOnly, tagFilter, sort, order, offset]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setOffset(0); }, [search, riskLevel, verdict, project, pinnedOnly, tagFilter, sort, order]);

  const onTogglePin = async (id: string) => {
    try {
      const r = await togglePin(id);
      toast.success(r.is_pinned ? "Pinned" : "Unpinned");
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to toggle pin");
    }
  };

  const openTagEditor = (scan: ScanResult) => {
    setEditingTagsFor(scan.id);
    setTagDraft(scan.tags.join(", "));
  };

  const saveTags = async (id: string) => {
    const tags = tagDraft.split(",").map((t) => t.trim()).filter(Boolean);
    try {
      await setScanTags(id, tags);
      toast.success("Tags updated");
      setEditingTagsFor(null);
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to update tags");
    }
  };

  const toggleSort = (field: string) => {
    if (sort === field) setOrder((o) => (o === "asc" ? "desc" : "asc"));
    else { setSort(field); setOrder("desc"); }
  };

  const onDelete = async (id: string) => {
    if (!confirm("Delete this scan from history? This cannot be undone.")) return;
    try {
      await deleteScan(id);
      toast.success("Scan deleted");
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to delete scan");
    }
  };

  return (
    <PageShell
      title="Scan History"
      subtitle={`${total} scan${total !== 1 ? "s" : ""} recorded`}
      actions={
        <>
          <a href={exportHistoryUrl("csv", { search, risk_level: riskLevel, verdict, project })} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <Download size={13} /> CSV
          </a>
          <a href={exportHistoryUrl("json", { search, risk_level: riskLevel, verdict, project })} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)">
            <Download size={13} /> JSON
          </a>
        </>
      }
    >
      <div className="card p-3 mb-4 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-muted)" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search filename or project..."
            className="w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg pl-8 pr-3 py-1.5 text-xs focus-ring outline-none" />
        </div>
        <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)} className="bg-(--surface-3) border border-(--border-hairline) rounded-lg px-2.5 py-1.5 text-xs focus-ring outline-none">
          <option value="">All Risk Levels</option>
          {["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"].map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={verdict} onChange={(e) => setVerdict(e.target.value)} className="bg-(--surface-3) border border-(--border-hairline) rounded-lg px-2.5 py-1.5 text-xs focus-ring outline-none">
          <option value="">All Verdicts</option>
          <option value="VULNERABLE">Vulnerable</option>
          <option value="NOT VULNERABLE">Not Vulnerable</option>
        </select>
        <select value={project} onChange={(e) => setProject(e.target.value)} className="bg-(--surface-3) border border-(--border-hairline) rounded-lg px-2.5 py-1.5 text-xs focus-ring outline-none">
          <option value="">All Projects</option>
          {projects.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {allTags.length > 0 && (
          <select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} className="bg-(--surface-3) border border-(--border-hairline) rounded-lg px-2.5 py-1.5 text-xs focus-ring outline-none">
            <option value="">All Tags</option>
            {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <button
          onClick={() => setPinnedOnly((p) => !p)}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors ${pinnedOnly ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-3) border-(--border-hairline) text-(--text-secondary) hover:bg-(--surface-2)"}`}
        >
          <Pin size={12} /> Pinned Only
        </button>
      </div>

      {loading && !results ? <Spinner label="Loading history..." /> : !results || results.length === 0 ? (
        <EmptyState icon={HistoryIcon} title="No scans found" description="Try adjusting your filters, or run a new scan." />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-(--border-hairline) text-left text-[11px] uppercase tracking-wider text-(--text-muted)">
                <th className="px-3 py-3 font-medium w-8"></th>
                <Th label="File" field="filename" sort={sort} order={order} onClick={toggleSort} />
                <th className="px-4 py-3 font-medium">Project</th>
                <th className="px-4 py-3 font-medium">Verdict</th>
                <Th label="Risk" field="risk" sort={sort} order={order} onClick={toggleSort} />
                <Th label="Confidence" field="confidence" sort={sort} order={order} onClick={toggleSort} />
                <th className="px-4 py-3 font-medium">Tags</th>
                <Th label="Date" field="date" sort={sort} order={order} onClick={toggleSort} />
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id} className="border-b border-(--border-hairline) last:border-0 hover:bg-(--surface-3) transition-colors">
                  <td className="px-3 py-2.5">
                    <button onClick={() => onTogglePin(r.id)} className={r.is_pinned ? "text-(--accent)" : "text-(--text-muted) hover:text-(--accent)"} title={r.is_pinned ? "Unpin" : "Pin"}>
                      {r.is_pinned ? <Pin size={14} fill="currentColor" /> : <PinOff size={14} />}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 mono text-xs">{r.filename}</td>
                  <td className="px-4 py-2.5 text-xs text-(--text-secondary)">{r.project_name}</td>
                  <td className="px-4 py-2.5"><VerdictPill verdict={r.verdict} /></td>
                  <td className="px-4 py-2.5"><RiskBadge level={r.risk_level} size="sm" /></td>
                  <td className="px-4 py-2.5 text-xs tabular">{r.confidence.toFixed(1)}%</td>
                  <td className="px-4 py-2.5">
                    {editingTagsFor === r.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus value={tagDraft} onChange={(e) => setTagDraft(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") saveTags(r.id); if (e.key === "Escape") setEditingTagsFor(null); }}
                          placeholder="tag1, tag2"
                          className="w-32 bg-(--surface-3) border border-(--border-hairline) rounded px-2 py-1 text-[11px] focus-ring outline-none"
                        />
                        <button onClick={() => saveTags(r.id)} className="text-(--status-good) text-[11px] font-semibold">✓</button>
                        <button onClick={() => setEditingTagsFor(null)} className="text-(--text-muted)"><X size={12} /></button>
                      </div>
                    ) : (
                      <button onClick={() => openTagEditor(r)} className="flex items-center gap-1 flex-wrap max-w-[180px] group">
                        {r.tags.length === 0 ? (
                          <span className="text-[11px] text-(--text-muted) group-hover:text-(--accent) inline-flex items-center gap-1"><TagIcon size={11} /> Add tag</span>
                        ) : r.tags.slice(0, 3).map((t) => (
                          <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-(--surface-3) text-(--text-secondary) group-hover:text-(--accent)">{t}</span>
                        ))}
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-(--text-muted)">{timeAgo(r.created_at)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1">
                      <Link to={`/analysis?scan=${r.id}`} className="p-1.5 rounded-md hover:bg-(--surface-2) text-(--text-muted) hover:text-(--accent)" title="View analysis">
                        <Eye size={14} />
                      </Link>
                      <button onClick={() => onDelete(r.id)} className="p-1.5 rounded-md hover:bg-(--surface-2) text-(--text-muted) hover:text-(--status-critical)" title="Delete">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex items-center justify-between px-4 py-3 border-t border-(--border-hairline) text-xs text-(--text-muted)">
            <span>Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
            <div className="flex gap-1.5">
              <button disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                className="p-1.5 rounded-md bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30 disabled:cursor-not-allowed">
                <ChevronLeft size={14} />
              </button>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset((o) => o + PAGE_SIZE)}
                className="p-1.5 rounded-md bg-(--surface-3) hover:bg-(--surface-2) disabled:opacity-30 disabled:cursor-not-allowed">
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}

function Th({ label, field, sort, order, onClick }: { label: string; field: string; sort: string; order: string; onClick: (f: string) => void }) {
  return (
    <th className="px-4 py-3 font-medium cursor-pointer select-none" onClick={() => onClick(field)}>
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown size={11} className={sort === field ? "text-(--accent)" : "text-(--text-muted)"} />
        {sort === field && <span className="text-[9px]">{order === "asc" ? "↑" : "↓"}</span>}
      </span>
    </th>
  );
}
