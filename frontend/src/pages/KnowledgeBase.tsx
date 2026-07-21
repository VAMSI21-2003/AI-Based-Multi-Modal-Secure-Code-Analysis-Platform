import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, ShieldAlert, ExternalLink, Skull, Gauge as GaugeIcon } from "lucide-react";
import PageShell from "../components/PageShell";
import { Spinner } from "../components/Loading";
import { getKnowledgeBase, type KnowledgeEntry } from "../api/client";

const SEVERITY_COLOR: Record<string, string> = {
  Critical: "var(--status-critical)", High: "var(--status-serious)",
  Medium: "var(--status-warning)", Info: "var(--text-muted)",
};

export default function KnowledgeBase() {
  const [entries, setEntries] = useState<KnowledgeEntry[] | null>(null);
  const [query, setQuery] = useState("");
  const [params] = useSearchParams();
  const highlightId = params.get("cwe");
  const refs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    let cancelled = false;
    getKnowledgeBase().then((e) => { if (!cancelled) setEntries(e); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (highlightId && refs.current[highlightId]) {
      refs.current[highlightId]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightId, entries]);

  const filtered = entries?.filter((e) =>
    !query || e.name.toLowerCase().includes(query.toLowerCase()) || e.id.toLowerCase().includes(query.toLowerCase()) || e.aka.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <PageShell title="Vulnerability Knowledge Base" subtitle="CWE reference library with mitigations and secure alternatives">
      <div className="relative mb-5 max-w-md">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-muted)" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, CWE ID, or alias..."
          className="w-full bg-(--surface-2) border border-(--border-hairline) rounded-lg pl-9 pr-3 py-2.5 text-sm focus-ring outline-none"
        />
      </div>

      {!entries ? <Spinner label="Loading knowledge base..." /> : (
        <div className="space-y-4">
          {filtered?.map((entry) => (
            <div
              key={entry.id}
              ref={(el) => { refs.current[entry.id] = el; }}
              className={`card p-5 transition-shadow ${highlightId === entry.id ? "ring-2 ring-(--accent)" : ""}`}
            >
              <div className="flex items-start justify-between flex-wrap gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="mono text-xs font-bold px-2 py-0.5 rounded-md bg-(--surface-3) text-(--accent)">{entry.id}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ color: SEVERITY_COLOR[entry.severity], background: `${SEVERITY_COLOR[entry.severity]}1f` }}>
                      {entry.severity}
                    </span>
                    {entry.cvss?.score != null && (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-(--surface-3) text-(--text-secondary)" title={entry.cvss.vector ?? undefined}>
                        <GaugeIcon size={10} /> CVSS {entry.cvss.score.toFixed(1)}
                      </span>
                    )}
                  </div>
                  <div className="text-base font-semibold mt-2">{entry.name}</div>
                  <div className="text-xs text-(--text-muted)">{entry.aka}</div>
                </div>
                <ShieldAlert size={20} className="text-(--text-muted)" />
              </div>

              <p className="text-sm text-(--text-secondary) mt-3">{entry.description}</p>

              <div className="text-xs mt-2 p-2.5 rounded-lg bg-(--status-serious)/10 text-(--text-secondary)">
                <span className="font-semibold text-(--status-serious)">Impact: </span>{entry.impact}
              </div>

              {(entry.vulnerable_example || entry.secure_example) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                  {entry.vulnerable_example && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-(--status-critical) font-semibold mb-1.5">Vulnerable</div>
                      <pre className="mono text-[11px] bg-(--surface-3) rounded-lg p-3 overflow-x-auto border-l-2 border-(--status-critical)">{entry.vulnerable_example}</pre>
                    </div>
                  )}
                  {entry.secure_example && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-(--status-good) font-semibold mb-1.5">Secure</div>
                      <pre className="mono text-[11px] bg-(--surface-3) rounded-lg p-3 overflow-x-auto border-l-2 border-(--status-good)">{entry.secure_example}</pre>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-4">
                <div className="text-xs font-semibold text-(--text-primary) mb-1.5">Mitigation</div>
                <ul className="space-y-1">
                  {entry.mitigation.map((m, i) => (
                    <li key={i} className="text-xs text-(--text-secondary) flex gap-2"><span className="text-(--accent)">&bull;</span>{m}</li>
                  ))}
                </ul>
              </div>

              {entry.cve_examples.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {entry.cve_examples.map((cve, i) => (
                    <span key={i} className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-full bg-(--surface-3) text-(--text-muted)">
                      <ExternalLink size={9} /> {cve}
                    </span>
                  ))}
                </div>
              )}

              {entry.real_attacks && entry.real_attacks.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-semibold text-(--text-primary) mb-1.5 flex items-center gap-1.5"><Skull size={12} className="text-(--status-critical)" /> Real-World Incidents</div>
                  <ul className="space-y-1">
                    {entry.real_attacks.map((a, i) => (
                      <li key={i} className="text-xs text-(--text-secondary) flex gap-2"><span className="text-(--status-critical)">&bull;</span>{a}</li>
                    ))}
                  </ul>
                </div>
              )}

              {(entry.mitre_url || entry.owasp_url) && (
                <div className="mt-4 pt-3 border-t border-(--border-hairline) flex gap-3">
                  {entry.mitre_url && (
                    <a href={entry.mitre_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-(--accent) hover:underline">
                      <ExternalLink size={10} /> MITRE CWE Reference
                    </a>
                  )}
                  {entry.owasp_url && (
                    <a href={entry.owasp_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[11px] text-(--accent) hover:underline">
                      <ExternalLink size={10} /> OWASP Reference
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
