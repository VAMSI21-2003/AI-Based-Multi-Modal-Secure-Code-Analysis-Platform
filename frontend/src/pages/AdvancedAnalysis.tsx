import { useEffect, useState } from "react";
import { SearchCode, CheckCircle2 } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import { useActiveScan } from "../hooks/useActiveScan";
import { getCodeIntelligence, type CodeIntelligence } from "../api/client";

export default function AdvancedAnalysis() {
  const { scanId, scan, loading } = useActiveScan();
  const [intel, setIntel] = useState<CodeIntelligence | null>(null);

  useEffect(() => { if (scanId) getCodeIntelligence(scanId).then(setIntel); }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="Advanced Static Analysis" subtitle="Dead code, unused variables, shadowing, magic numbers, and more">
        <ScanPickerEmpty icon={SearchCode} title="No scan selected" description="Run a scan to check it for common code-quality smells." />
      </PageShell>
    );
  }

  if (loading || !scan || !intel) {
    return <PageShell title="Advanced Static Analysis" subtitle="Loading"><Spinner label="Running static checks..." /></PageShell>;
  }

  const s = intel.code_smells;

  const sections = [
    { title: "Unused Variables", items: s.unused_variables.map((v) => `${v.name} (line ${v.line})`) },
    { title: "Unreachable Code", items: s.unreachable_code.map((v) => `Line ${v.line} is unreachable (after line ${v.after_line} returns/breaks/continues)`) },
    { title: "Shadowed Variables", items: s.shadow_variables.map((v) => `'${v.name}' declared at line ${v.outer_line}, shadowed at line ${v.inner_line}`) },
    { title: "Long Parameter Lists", items: s.long_parameter_lists.map((v) => `${v.function}() has ${v.count} parameters (consider a struct)`) },
    { title: "Large Functions", items: s.large_functions.map((v) => `${v.function}() is ${v.loc} lines long`) },
    { title: "Deep Nesting", items: s.deep_nesting.map((v) => `${v.function}() nests ${v.depth} levels deep`) },
    { title: "Magic Numbers", items: s.magic_numbers.map((v) => `Line ${v.line}: literal ${v.value}`) },
    { title: "Duplicate Code", items: s.duplicate_code.map((v) => `"${v.snippet}" repeated on lines ${v.lines.join(", ")}`) },
    { title: "Not Called Elsewhere in File", items: intel.dead_code },
  ];

  return (
    <PageShell title="Advanced Static Analysis" subtitle={`${scan.filename} — ${s.total_findings} finding(s) across 8 categories`}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {sections.map((sec) => (
          <ChartCard key={sec.title} title={sec.title} subtitle={`${sec.items.length} found`}>
            {sec.items.length === 0 ? (
              <div className="text-xs text-(--status-good) flex items-center gap-1.5"><CheckCircle2 size={13} /> None detected.</div>
            ) : (
              <ul className="space-y-1.5 max-h-56 overflow-y-auto scrollbar-thin">
                {sec.items.map((item, i) => (
                  <li key={i} className="text-xs text-(--text-secondary) mono bg-(--surface-3) rounded-lg px-2.5 py-1.5">{item}</li>
                ))}
              </ul>
            )}
          </ChartCard>
        ))}
      </div>
    </PageShell>
  );
}
