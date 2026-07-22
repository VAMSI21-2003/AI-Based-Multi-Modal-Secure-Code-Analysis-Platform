import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Wrench, CheckCircle2, BookOpen, ArrowDown, Wand2, AlertTriangle, TrendingDown, TrendingUp, Minus } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import DiffViewer from "../components/DiffViewer";
import ProgressBar from "../components/ProgressBar";
import { VerdictPill } from "../components/RiskBadge";
import { useActiveScan } from "../hooks/useActiveScan";
import type { ScanResult } from "../api/client";
import { getPatches, applyPatch, type PatchCard, type PatchResponse, type ApplyPatchResult, type ApplyPatchBlocked } from "../api/patches";

export default function AutoPatch() {
  const { scanId, scan, loading: scanLoading, error } = useActiveScan();
  const [patches, setPatches] = useState<PatchResponse | null>(null);
  // Applied results, keyed by patch id -- lets multiple cards on the same
  // page each carry their own independent apply/before-after state.
  const [applied, setApplied] = useState<Record<string, ApplyPatchResult>>({});

  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    setPatches(null);
    setApplied({});
    getPatches(scanId).then((p) => { if (!cancelled) setPatches(p); });
    return () => { cancelled = true; };
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
            {patches.detected.map((p) => (
              <PatchCardView
                key={p.id}
                scanId={scanId}
                patch={p}
                appliedResult={applied[p.id]}
                onApplied={(result) => setApplied((prev) => ({ ...prev, [p.id]: result }))}
              />
            ))}
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
          {patches.reference.map((p) => <PatchCardView key={p.id} scanId={scanId} patch={p} />)}
        </div>
      </div>

      {patches.detected.length === 0 && (
        <div className="card p-4 mt-6 text-sm text-(--status-good)">No auto-fixable patterns detected in this scan — nice.</div>
      )}
    </PageShell>
  );
}

function PatchCardView({
  scanId, patch, appliedResult, onApplied,
}: {
  scanId: string;
  patch: PatchCard;
  appliedResult?: ApplyPatchResult;
  onApplied?: (result: ApplyPatchResult) => void;
}) {
  const [applying, setApplying] = useState(false);
  const [blocked, setBlocked] = useState<ApplyPatchBlocked | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  // Per the design (docs/APPLY_PATCH_LOOP_DESIGN.md §2): only a detected
  // (not reference) card with a known, real destination size offers apply
  // at all -- a placeholder fix is not valid, compilable C to feed back
  // through the model. The backend re-validates this itself against the
  // WHOLE file's rewrite (not just this one card's line), so a card that
  // looks safe here can still come back blocked if a DIFFERENT occurrence
  // elsewhere in the same file is unknown -- handled honestly below via
  // the `blocked` state, not hidden.
  const canApply = patch.detected && patch.size_known;

  const handleApply = async () => {
    setApplying(true);
    setBlocked(null);
    setApplyError(null);
    try {
      const result = await applyPatch(scanId, patch.id);
      onApplied?.(result);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (detail && typeof detail === "object" && detail.blocked) {
        setBlocked(detail as ApplyPatchBlocked);
      } else {
        setApplyError(typeof detail === "string" ? detail : e.message || "Failed to apply patch");
      }
    } finally {
      setApplying(false);
    }
  };

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
      {patch.detected && !patch.size_known && (
        <div className="text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2 mb-3">
          This destination's real buffer capacity could not be determined from the scanned code (likely a pointer parameter,
          not a stack array) — the fix below uses a placeholder, not a fabricated size. Fill in the real capacity before using it.
          Apply &amp; Re-scan is unavailable for this fix.
        </div>
      )}
      <DiffViewer original={patch.original_code} modified={patch.fixed_code} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div className="text-xs p-3 rounded-lg bg-(--status-serious)/10 text-(--text-secondary)">
          <span className="font-semibold text-(--status-serious)">What's wrong: </span>{patch.explanation}
        </div>
        <div className="text-xs p-3 rounded-lg bg-(--status-good)/10 text-(--text-secondary)">
          <span className="font-semibold text-(--status-good) flex items-center gap-1"><ArrowDown size={11} /> Why it's safer: </span>{patch.why_safer}
        </div>
      </div>

      {canApply && !appliedResult && (
        <div className="mt-4 pt-4 border-t border-(--border-hairline)">
          <button
            onClick={handleApply}
            disabled={applying}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Wand2 size={13} /> {applying ? "Applying & re-scanning..." : "Apply & Re-scan"}
          </button>
          <div className="text-[11px] text-(--text-muted) mt-2">
            Creates a new, separate scan from the rewritten code and re-runs real inference on it — the original scan is never modified.
          </div>
        </div>
      )}

      {blocked && (
        <div className="mt-4 pt-4 border-t border-(--border-hairline)">
          <div className="text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-3 flex gap-2">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold mb-1">Apply blocked — not a real fix yet</div>
              <div>{blocked.reason}</div>
              <div className="mt-1 text-(--text-muted)">{blocked.note}</div>
            </div>
          </div>
        </div>
      )}

      {applyError && (
        <div className="mt-4 pt-4 border-t border-(--border-hairline) text-xs text-(--status-critical)">{applyError}</div>
      )}

      {appliedResult && <BeforeAfterComparison result={appliedResult} />}
    </ChartCard>
  );
}

function BeforeAfterComparison({ result }: { result: ApplyPatchResult }) {
  const { original, derived } = result;
  const probDelta = derived.vuln_probability - original.vuln_probability;
  const verdictChanged = original.verdict !== derived.verdict;
  const improved = probDelta < 0;

  return (
    <div className="mt-4 pt-4 border-t border-(--border-hairline)">
      <div className="flex items-center gap-2 text-sm font-semibold mb-3">
        <CheckCircle2 size={15} className="text-(--status-good)" /> Applied — Before / After
      </div>

      {/* Re-scan can find new/different issues -- the model's score is not
          guaranteed to move in the "expected" direction just because the
          targeted pattern was fixed (see docs/CI_CD.md §4 for a real
          example). Shown plainly either way, not framed as "success". */}
      <div className="card p-4 mb-4 flex items-center gap-3">
        {verdictChanged ? (
          improved ? <TrendingDown className="text-(--status-good) shrink-0" size={20} /> : <TrendingUp className="text-(--status-warning) shrink-0" size={20} />
        ) : (
          <Minus className="text-(--text-muted) shrink-0" size={20} />
        )}
        <div>
          <div className="text-sm font-semibold">
            {verdictChanged ? `Verdict changed: ${original.verdict} → ${derived.verdict}` : `Verdict unchanged: ${derived.verdict}`}
          </div>
          <div className="text-xs text-(--text-muted)">
            Vulnerability probability {probDelta <= 0 ? "decreased" : "increased"} by {Math.abs(probDelta).toFixed(1)} points
            ({original.vuln_probability.toFixed(1)}% → {derived.vuln_probability.toFixed(1)}%).
            {!improved && " The rewrite did not lower the model's score for this function -- reported honestly, not hidden."}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <ScanScoreCard label="Original" accent="var(--series-5)" result={original} />
        <ScanScoreCard label="Patched" accent="var(--series-1)" result={derived} />
      </div>

      <div className="text-xs font-semibold mb-2">Code Diff (whole file)</div>
      <DiffViewer original={original.code || ""} modified={derived.code || ""} />

      <Link to={`/auto-patch?scan=${result.derived_scan_id}`} className="text-[11px] text-(--accent) hover:underline mt-3 inline-block">
        View the derived scan's own patches →
      </Link>
    </div>
  );
}

function ScanScoreCard({ label, accent, result }: { label: string; accent: string; result: ScanResult }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold" style={{ color: accent }}>{label}</div>
        <VerdictPill verdict={result.verdict} />
      </div>
      <div className="space-y-3">
        <ProgressBar value={result.vuln_probability} color={accent} label="Vulnerability Probability" />
        <ProgressBar value={result.confidence} color="var(--series-7)" label="Confidence" />
      </div>
    </div>
  );
}
