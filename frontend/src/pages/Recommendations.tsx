import { Wand2, ShieldCheck, Lightbulb, CheckCircle2 } from "lucide-react";
import PageShell from "../components/PageShell";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import ChartCard from "../components/ChartCard";
import { useActiveScan } from "../hooks/useActiveScan";

const GENERAL_TIPS = [
  { title: "Buffer Overflow Prevention", tips: [
    "Prefer bounds-checked functions (strncpy, snprintf, strncat) over unbounded ones.",
    "Always validate lengths BEFORE copying, not after.",
    "Compile with -fstack-protector-strong and _FORTIFY_SOURCE=2.",
  ]},
  { title: "Null Pointer Checks", tips: [
    "Check the return value of every malloc/calloc/realloc/fopen call before use.",
    "Reset freed pointers to NULL immediately after free().",
  ]},
  { title: "Memory Safety", tips: [
    "Pair every malloc()/free() so ownership is unambiguous.",
    "Run AddressSanitizer in CI to catch UAF, double-free, and overflows automatically.",
  ]},
  { title: "Input Validation", tips: [
    "Validate size/range of all external values before using them in arithmetic or allocation.",
    "Treat all network/file/CLI input as untrusted until validated.",
  ]},
];

export default function Recommendations() {
  const { scanId, scan, detail, loading, error } = useActiveScan();

  if (!scanId) {
    return (
      <PageShell title="AI Recommendation Panel" subtitle="Secure coding guidance and auto-suggested fixes">
        <ScanPickerEmpty icon={Wand2} title="No scan selected" description="Run a scan to get tailored secure-coding recommendations and an auto-suggested secure rewrite." />
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {GENERAL_TIPS.map((p) => <TipCard key={p.title} panel={p} />)}
        </div>
      </PageShell>
    );
  }

  if (loading || !scan || !detail) {
    return (
      <PageShell title="AI Recommendation Panel" subtitle="Secure coding guidance">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Generating recommendations..." />}
      </PageShell>
    );
  }

  return (
    <PageShell title="AI Recommendation Panel" subtitle={`Tailored guidance for ${scan.filename}`}>
      {detail.suggested_rewrite.changed ? (
        <ChartCard title="Suggested Secure Rewrite" subtitle="Rule-based auto-fix — review before applying" className="mb-5">
          {detail.suggested_rewrite.requires_manual_sizing && (
            <div className="mb-3 text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2">
              One or more fixes below use a <code className="mono">dest_size</code> placeholder, not a real number — this destination's actual
              buffer capacity could not be determined from this code (it's likely a pointer parameter, not a stack array). Fill in the real
              capacity before using this rewrite.
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-(--status-critical) font-semibold mb-1.5">Original</div>
              <pre className="mono text-[11px] bg-(--surface-3) rounded-lg p-3 overflow-x-auto max-h-80 border-l-2 border-(--status-critical)">{scan.code}</pre>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-(--status-good) font-semibold mb-1.5">Suggested</div>
              <pre className="mono text-[11px] bg-(--surface-3) rounded-lg p-3 overflow-x-auto max-h-80 border-l-2 border-(--status-good)">{detail.suggested_rewrite.rewritten_code}</pre>
            </div>
          </div>
          <div className="mt-3 space-y-1.5">
            {detail.suggested_rewrite.changes.map((c, i) => (
              <div key={i} className="text-xs text-(--text-secondary) flex items-center gap-2">
                <CheckCircle2 size={12} className="text-(--status-good)" /> {c.description} ({c.occurrences}&times;)
              </div>
            ))}
          </div>
          <div className="mt-3 text-[11px] text-(--text-muted) border-t border-(--border-hairline) pt-2">
            Automated, pattern-based suggestion — always compile and test before adopting.
          </div>
        </ChartCard>
      ) : (
        <div className="card p-4 mb-5 flex items-center gap-3 text-sm text-(--status-good)">
          <ShieldCheck size={18} /> No automatic rewrite pattern matched — no unbounded copy/format calls detected.
        </div>
      )}

      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Lightbulb size={15} className="text-(--status-warning)" /> Relevant Best Practices
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {detail.recommendations.map((p) => <TipCard key={p.title} panel={p} />)}
      </div>

      <div className="mb-2 text-sm font-semibold text-(--text-muted)">General Reference</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {GENERAL_TIPS.filter((g) => !detail.recommendations.some((r) => r.title === g.title)).map((p) => (
          <TipCard key={p.title} panel={p} muted />
        ))}
      </div>
    </PageShell>
  );
}

function TipCard({ panel, muted = false }: { panel: { title: string; tips: string[] }; muted?: boolean }) {
  return (
    <div className={`card p-4 ${muted ? "opacity-70" : ""}`}>
      <div className="text-sm font-semibold mb-2.5">{panel.title}</div>
      <ul className="space-y-1.5">
        {panel.tips.map((t, i) => (
          <li key={i} className="text-xs text-(--text-secondary) flex gap-2"><span className="text-(--accent) shrink-0">&bull;</span>{t}</li>
        ))}
      </ul>
    </div>
  );
}
