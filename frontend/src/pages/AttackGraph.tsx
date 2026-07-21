import { useEffect, useState } from "react";
import { Network } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import AttackGraphView from "../components/graphs/AttackGraphView";
import { useActiveScan } from "../hooks/useActiveScan";
import { getCodeIntelligence, type CodeIntelligence } from "../api/client";

export default function AttackGraph() {
  const { scanId, scan, loading: scanLoading, error } = useActiveScan();
  const [intel, setIntel] = useState<CodeIntelligence | null>(null);

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    getCodeIntelligence(scanId).then((i) => { if (!cancelled) setIntel(i); });
    return () => { cancelled = true; };
  }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="Interactive Attack Graph" subtitle="File → Functions → Pointers → Dangerous APIs → CWE → Predicted Vulnerability">
        <ScanPickerEmpty icon={Network} title="No scan selected" description="Run a scan to visualise its full attack surface as a graph." />
      </PageShell>
    );
  }

  if (scanLoading || !scan || !intel) {
    return (
      <PageShell title="Interactive Attack Graph" subtitle="Building attack surface graph">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Tracing attack surface..." />}
      </PageShell>
    );
  }

  return (
    <PageShell title="Interactive Attack Graph" subtitle={`${scan.filename} — how risk flows from source to prediction`}>
      <ChartCard title="Attack Surface Graph" subtitle="Drag nodes, scroll to zoom, pan to explore">
        <AttackGraphView scan={scan} intel={intel} />
        <div className="flex flex-wrap gap-4 text-[11px] text-(--text-muted) mt-3">
          <Legend color="#3987e5" label="File" />
          <Legend color="#9085e9" label="Function" />
          <Legend color="#d55181" label="Pointer Usage" />
          <Legend color="#ec835a" label="Dangerous API" />
          <Legend color="#fab219" label="CWE" />
          <Legend color="#d03b3b" label="Predicted Vulnerable" />
          <Legend color="#0ca30c" label="Predicted Safe" />
        </div>
      </ChartCard>
    </PageShell>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: `${color}33`, border: `1.5px solid ${color}` }} /> {label}</span>;
}
