import { useState } from "react";
import { Link } from "react-router-dom";
import { Search, FileCode2, ArrowUpRight } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { EmptyState, Spinner } from "../components/Loading";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import { searchVulnerabilities, type SearchResponse, type SearchCategory } from "../api/client";
import { timeAgo } from "../utils/risk";

const CATEGORIES: { value: SearchCategory; label: string }[] = [
  { value: "all", label: "All" },
  { value: "cwe", label: "CWE" },
  { value: "api", label: "API" },
  { value: "function", label: "Function" },
  { value: "variable", label: "Variable" },
  { value: "pointer", label: "Pointer" },
  { value: "loop", label: "Loop" },
  { value: "risk", label: "Risk" },
];

export default function VulnSearch() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<SearchCategory>("all");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const d = await searchVulnerabilities(query.trim(), category);
      setData(d);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageShell title="Vulnerability Search Engine" subtitle="Search every stored scan by CWE, API, function, variable, pointer, loop, or risk level">
      <ChartCard title="Search" subtitle="Searches the most recent 40 scans' real code and analysis output — not an index, computed on demand" className="mb-5">
        <div className="flex flex-col md:flex-row gap-3 mb-3">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-muted)" />
            <input
              value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder="e.g. strcpy, CWE-120, malloc, main, buffer..."
              className="w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg pl-9 pr-3 py-2.5 text-sm mono focus-ring outline-none"
            />
          </div>
          <button onClick={runSearch} disabled={loading || !query.trim()} className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 disabled:opacity-50">
            <Search size={15} /> {loading ? "Searching..." : "Search"}
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => setCategory(c.value)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${category === c.value ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary) hover:bg-(--surface-3)"}`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </ChartCard>

      {loading ? <Spinner label="Searching stored scans..." /> : !searched ? (
        <EmptyState icon={Search} title="Search across every scan you've ever run" description="Try a CWE id (CWE-120), a dangerous API (strcpy, gets, malloc), a function name, or a risk level (CRITICAL)." />
      ) : !data || data.results.length === 0 ? (
        <EmptyState icon={Search} title={`No matches for "${query}"`} description={`Searched ${data?.scanned ?? 0} recent scan(s) in category "${category}". Try a broader term or a different category.`} />
      ) : (
        <ChartCard title={`${data.results.length} file(s) matched`} subtitle={`"${data.query}" · category: ${data.category} · ${data.scanned} scans searched`}>
          <div className="divide-y divide-(--border-hairline)">
            {data.results.map((r) => (
              <div key={r.scan_id} className="py-3.5">
                <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileCode2 size={14} className="text-(--text-muted) shrink-0" />
                    <span className="text-sm font-medium mono truncate">{r.filename}</span>
                    <span className="text-xs text-(--text-muted) shrink-0">{r.project_name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <RiskBadge level={r.risk_level} size="sm" />
                    <VerdictPill verdict={r.verdict as any} />
                    <span className="text-xs text-(--text-muted)">{timeAgo(r.created_at)}</span>
                    <Link to={`/analysis?scan=${r.scan_id}`} className="text-(--accent) hover:underline text-xs inline-flex items-center gap-0.5">
                      Open <ArrowUpRight size={11} />
                    </Link>
                  </div>
                </div>
                <div className="space-y-1 pl-6">
                  {r.matches.map((m, i) => (
                    <div key={i} className="text-xs text-(--text-secondary) flex items-start gap-2">
                      <span className="text-[10px] uppercase tracking-wider text-(--accent) font-semibold shrink-0 w-14">{m.kind}</span>
                      <span className="min-w-0">
                        {m.line && <span className="text-(--text-muted) mono">L{m.line}: </span>}
                        {m.detail}
                        {m.cwe.length > 0 && <span className="text-(--text-muted)"> [{m.cwe.join(", ")}]</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      )}
    </PageShell>
  );
}
