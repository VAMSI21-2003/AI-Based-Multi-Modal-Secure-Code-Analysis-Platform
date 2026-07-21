import { useEffect, useState } from "react";
import { GitCompare, RefreshCw } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import CodeEditor from "../components/CodeEditor";
import DiffViewer from "../components/DiffViewer";
import { Spinner } from "../components/Loading";
import { useActiveScan } from "../hooks/useActiveScan";

const SAMPLE_ORIGINAL = `void copy_user_data(char *user_input) {
    char buffer[64];
    strcpy(buffer, user_input);
    process_data(buffer);
}`;
const SAMPLE_FIXED = `void copy_user_data(char *user_input) {
    char buffer[64];
    strncpy(buffer, user_input, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
    process_data(buffer);
}`;

export default function CodeDiff() {
  const { scanId, scan, detail, loading } = useActiveScan();
  const [original, setOriginal] = useState(SAMPLE_ORIGINAL);
  const [modified, setModified] = useState(SAMPLE_FIXED);
  const [loadedFromScan, setLoadedFromScan] = useState(false);

  useEffect(() => {
    if (scan && detail?.suggested_rewrite.changed && !loadedFromScan) {
      setOriginal(scan.code ?? "");
      setModified(detail.suggested_rewrite.rewritten_code);
      setLoadedFromScan(true);
    }
  }, [scan, detail, loadedFromScan]);

  return (
    <PageShell
      title="Code Difference Viewer"
      subtitle="Compare original code against a fixed / secure version, side by side"
      actions={
        scanId && detail?.suggested_rewrite.changed ? (
          <button
            onClick={() => { setOriginal(scan!.code ?? ""); setModified(detail!.suggested_rewrite.rewritten_code); setLoadedFromScan(true); }}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-medium hover:bg-(--surface-3)"
          >
            <RefreshCw size={13} /> Load current scan's auto-fix
          </button>
        ) : undefined
      }
    >
      {scanId && loading && <Spinner label="Loading scan..." />}

      {loadedFromScan && detail?.suggested_rewrite.requires_manual_sizing && (
        <div className="mb-4 text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2.5">
          This auto-fix contains one or more <code className="mono">dest_size</code> placeholders — the real buffer capacity could not be
          determined from the scanned code (likely a pointer parameter, not a stack array). Fill in the real capacity before treating this as final.
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <div>
          <div className="text-xs font-semibold text-(--status-critical) mb-1.5">Original Code</div>
          <CodeEditor value={original} onChange={setOriginal} height={260} />
        </div>
        <div>
          <div className="text-xs font-semibold text-(--status-good) mb-1.5">Fixed / Secure Version</div>
          <CodeEditor value={modified} onChange={setModified} height={260} />
        </div>
      </div>

      <ChartCard title="Difference" subtitle={<span className="flex items-center gap-1.5"><GitCompare size={12} /> Line-level diff — red removed, green added</span>}>
        <DiffViewer original={original} modified={modified} />
      </ChartCard>
    </PageShell>
  );
}
