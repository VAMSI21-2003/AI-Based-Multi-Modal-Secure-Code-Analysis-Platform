import { useEffect, useState } from "react";
import { FileText, Download, FileCode2, FolderGit2 } from "lucide-react";
import toast from "react-hot-toast";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import { getHistory, getBatches, downloadScanPdf, downloadBatchPdf, type ScanResult } from "../api/client";
import { computeGrade } from "../utils/grade";
import { timeAgo } from "../utils/risk";

export default function Reports() {
  const [scans, setScans] = useState<ScanResult[] | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);

  useEffect(() => {
    getHistory({ limit: 12, sort: "date", order: "desc" }).then((d) => setScans(d.results));
    getBatches().then(setBatches);
  }, []);

  return (
    <PageShell title="Security Reports" subtitle="Generate professional PDF reports for a single function or an entire project scan">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <FolderGit2 size={15} className="text-(--accent)" /> Project Reports (Batch Scans)
      </div>
      {!batches ? <Spinner label="Loading batches..." /> : batches.length === 0 ? (
        <EmptyState icon={FolderGit2} title="No batch scans yet" description="Run a Batch Upload scan in Code Scanner to generate a project-wide PDF report." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
          {batches.map((b) => {
            const pct = b.total_files ? (b.vulnerable_files / b.total_files) * 100 : 0;
            const { grade, color } = computeGrade(100 - pct);
            return (
              <ChartCard key={b.batch_id} title={b.project_name} subtitle={timeAgo(b.created_at)}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-(--text-muted)">{b.total_files} files &middot; {b.vulnerable_files} vulnerable</div>
                    <div className="text-2xl font-bold mt-1" style={{ color }}>{grade}</div>
                  </div>
                  <a href={downloadBatchPdf(b.batch_id)} onClick={() => toast.success("Generating project PDF report...")} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110">
                    <Download size={13} /> PDF
                  </a>
                </div>
              </ChartCard>
            );
          })}
        </div>
      )}

      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <FileCode2 size={15} className="text-(--accent)" /> Individual Scan Reports
      </div>
      {!scans ? <Spinner label="Loading scans..." /> : scans.length === 0 ? (
        <EmptyState icon={FileText} title="No scans yet" description="Scan a function to generate its security report." />
      ) : (
        <div className="card divide-y divide-(--border-hairline)">
          {scans.map((s) => {
            const { grade, color } = computeGrade(100 - s.vuln_probability);
            return (
              <div key={s.id} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium mono truncate">{s.filename}</div>
                  <div className="text-xs text-(--text-muted)">{s.project_name} &middot; {timeAgo(s.created_at)}</div>
                </div>
                <div className="flex items-center gap-4 shrink-0 ml-3">
                  <span className="text-lg font-bold w-6 text-center" style={{ color }}>{grade}</span>
                  <a href={downloadScanPdf(s.id)} onClick={() => toast.success("Generating PDF report...")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-xs font-medium">
                    <Download size={12} /> PDF
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
