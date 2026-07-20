import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Wrench, CheckCircle2, BookOpen, ArrowDown } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import DiffViewer from "../components/DiffViewer";
import { useActiveScan } from "../hooks/useActiveScan";
import { getPatches, type PatchCard, type PatchResponse } from "../api/patches";

export default function AutoPatch() {
  const { scanId, scan, loading: scanLoading, error } = useActiveScan();
  const [patches, setPatches] = useState<PatchResponse | null>(null);

  useEffect(() => {
    if (!scanId) return;
    getPatches(scanId).then(setPatches);
  }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="AI Auto Patch Generator" subtitle="Original code → fixed code → explanation → why it's safer">
        <ScanPickerEmpty icon={Wrench} title="No scan selected" description="Run a scan to generate concrete before/after security patches for its code." />
      </PageShell>
    );
  }

  if (scanLoading || !scan || !patches) {
    return (
      <PageShell title="AI Auto Patch Generator" subtitle="Generating patches">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Scanning for fixable patterns..." />}
      </PageShell>
    );
  }

  return (
    <PageShell title="AI Auto Patch Generator" subtitle={`${scan.filename} — ${patches.detected_count} issue(s) with a concrete generated fix`}>
      {patches.detected.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 text-sm font-semibold mb-3">
            <CheckCircle2 size={15} className="text-(--status-good)" /> Detected in Your Code
          </div>
          <div className="space-y-6">
            {patches.detected.map((p) => <PatchCardView key={p.id} patch={p} />)}
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center gap-2 text-sm font-semibold mb-3">
          <BookOpen size={15} className="text-(--accent)" /> Reference Patterns
        </div>
        <p className="text-xs text-(--text-muted) mb-4">
          These vulnerability classes weren't matched verbatim in this file (or have no safe one-line auto-fix) —
          shown here as canonical before/after examples for reference.
        </p>
        <div className="space-y-6">
          {patches.reference.map((p) => <PatchCardView key={p.id} patch={p} />)}
        </div>
      </div>

      {patches.detected.length === 0 && (
        <div className="card p-4 mt-6 text-sm text-(--status-good)">No auto-fixable patterns detected in this scan — nice.</div>
      )}
    </PageShell>
  );
}

function PatchCardView({ patch }: { patch: PatchCard }) {
  return (
    <ChartCard
      title={patch.title}
      subtitle={
        <span className="flex items-center gap-2">
          {patch.cwe && (
            <Link to={`/knowledge-base?cwe=${patch.cwe}`} className="text-(--accent) hover:underline">{patch.cwe}</Link>
          )}
          {patch.line && <span>Line {patch.line}</span>}
          {!patch.detected && <span className="italic">canonical example</span>}
        </span>
      }
    >
      <DiffViewer original={patch.original_code} modified={patch.fixed_code} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div className="text-xs p-3 rounded-lg bg-(--status-serious)/10 text-(--text-secondary)">
          <span className="font-semibold text-(--status-serious)">What's wrong: </span>{patch.explanation}
        </div>
        <div className="text-xs p-3 rounded-lg bg-(--status-good)/10 text-(--text-secondary)">
          <span className="font-semibold text-(--status-good) flex items-center gap-1"><ArrowDown size={11} /> Why it's safer: </span>{patch.why_safer}
        </div>
      </div>
    </ChartCard>
  );
}
