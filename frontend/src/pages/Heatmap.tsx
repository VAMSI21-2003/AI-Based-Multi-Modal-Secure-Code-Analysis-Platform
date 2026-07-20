import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Flame, AlertCircle, BookOpen, Play } from "lucide-react";
import PageShell from "../components/PageShell";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import ChartCard from "../components/ChartCard";
import { useActiveScan } from "../hooks/useActiveScan";
import { severityColor, severityLabel } from "../utils/risk";
import { replayUrl } from "../utils/replay";
import type { LineRisk } from "../api/client";

export default function Heatmap() {
  const { scanId, scan, detail, loading, error } = useActiveScan();
  const [selected, setSelected] = useState<LineRisk | null>(null);

  const lineMap = useMemo(() => {
    const m = new Map<number, LineRisk>();
    detail?.line_risks.forEach((lr) => m.set(lr.line, lr));
    return m;
  }, [detail]);

  if (!scanId) {
    return (
      <PageShell title="Vulnerability Heatmap" subtitle="Line-level risk highlighting, VS Code diagnostics style">
        <ScanPickerEmpty icon={Flame} title="No scan selected" description="Run a scan to see a line-by-line risk heatmap of the exact statements driving the verdict." />
      </PageShell>
    );
  }

  if (loading || !scan || !detail) {
    return (
      <PageShell title="Vulnerability Heatmap" subtitle="Line-level risk highlighting">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Scanning lines..." />}
      </PageShell>
    );
  }

  const lines = scan.code?.split("\n") ?? [];
  const counts = [0, 0, 0, 0, 0];
  detail.line_risks.forEach((lr) => { counts[lr.severity]++; });

  return (
    <PageShell title="Vulnerability Heatmap" subtitle={`${scan.filename} · ${detail.line_risks.length} flagged line(s)`}>
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-3 mb-5">
        {[
          { sev: 4, label: "Critical" }, { sev: 3, label: "High" }, { sev: 2, label: "Medium" }, { sev: 1, label: "Low" },
        ].map(({ sev, label }) => (
          <div key={sev} className="card p-4 flex items-center justify-between">
            <div>
              <div className="text-xs text-(--text-muted) uppercase tracking-wider">{label}</div>
              <div className="text-2xl font-bold tabular mt-1">{counts[sev]}</div>
            </div>
            <span className="w-3 h-3 rounded-full" style={{ background: severityColor(sev), boxShadow: `0 0 10px ${severityColor(sev)}` }} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <ChartCard title="Source Code" subtitle="Click a highlighted line for details" className="xl:col-span-2">
          <div className="mono text-[12.5px] rounded-lg overflow-hidden border border-(--border-hairline)">
            {lines.map((lineText, i) => {
              const lineNo = i + 1;
              const risk = lineMap.get(lineNo);
              const sev = risk?.severity ?? 0;
              const isSelected = selected?.line === lineNo;
              return (
                <div
                  key={i}
                  onClick={() => risk && setSelected(risk)}
                  className={`flex ${risk ? "cursor-pointer" : ""} ${isSelected ? "ring-1 ring-inset ring-(--accent)" : ""}`}
                  style={{
                    background: sev > 0 ? `${severityColor(sev)}1c` : i % 2 === 0 ? "var(--surface-2)" : "transparent",
                    borderLeft: sev > 0 ? `3px solid ${severityColor(sev)}` : "3px solid transparent",
                  }}
                >
                  <span className="w-12 shrink-0 text-right pr-3 py-1 text-(--text-muted) select-none border-r border-(--border-hairline)">{lineNo}</span>
                  <span className="px-3 py-1 whitespace-pre text-(--text-secondary) flex-1 overflow-x-auto">{lineText || " "}</span>
                  {risk && (
                    <span className="pr-3 py-1 flex items-center gap-1 shrink-0">
                      <AlertCircle size={12} style={{ color: severityColor(sev) }} />
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </ChartCard>

        <div className="space-y-4">
          <ChartCard title="Issue Detail" subtitle={selected ? `Line ${selected.line}` : "Select a flagged line"}>
            {!selected ? (
              <div className="text-xs text-(--text-muted) py-6 text-center">Click any highlighted line in the source to inspect it.</div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: severityColor(selected.severity) }} />
                  <span className="text-sm font-semibold" style={{ color: severityColor(selected.severity) }}>{severityLabel(selected.severity)} Risk</span>
                </div>
                <div className="mono text-xs bg-(--surface-3) rounded-lg p-2.5 overflow-x-auto">{selected.code}</div>
                <div className="space-y-1.5">
                  {selected.reasons.map((r, i) => (
                    <div key={i} className="text-xs text-(--text-secondary) flex gap-2">
                      <span className="text-(--text-muted)">&bull;</span>{r}
                    </div>
                  ))}
                </div>
                {selected.cwe.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-2 border-t border-(--border-hairline)">
                    {selected.cwe.map((c) => (
                      <Link key={c} to={`/knowledge-base?cwe=${c}`} className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full bg-(--surface-3) hover:bg-(--surface-2) text-(--accent)">
                        <BookOpen size={10} /> {c}
                      </Link>
                    ))}
                    {replayUrl(selected.cwe[0]) && (
                      <Link to={replayUrl(selected.cwe[0])!} className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full bg-(--accent)/15 hover:bg-(--accent)/25 text-(--accent)">
                        <Play size={10} /> Replay this exploit
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}
          </ChartCard>

          <ChartCard title="All Flagged Lines" subtitle={`${detail.line_risks.length} total`}>
            <div className="space-y-1.5 max-h-72 overflow-y-auto scrollbar-thin">
              {detail.line_risks.length === 0 && <div className="text-xs text-(--text-muted)">No dangerous patterns detected.</div>}
              {detail.line_risks.map((lr) => (
                <button
                  key={lr.line}
                  onClick={() => setSelected(lr)}
                  className="w-full flex items-center justify-between text-xs px-2.5 py-1.5 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) text-left"
                >
                  <span className="text-(--text-muted)">Line {lr.line}</span>
                  <span className="font-medium" style={{ color: severityColor(lr.severity) }}>{severityLabel(lr.severity)}</span>
                </button>
              ))}
            </div>
          </ChartCard>
        </div>
      </div>
    </PageShell>
  );
}
