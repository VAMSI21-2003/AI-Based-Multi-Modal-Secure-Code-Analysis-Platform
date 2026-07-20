import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  Download, FileText, Users, Code2, Globe, FlaskConical, Table, Braces, FileType2, Presentation as PresentationIcon, Building2,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import {
  getHistory, downloadScanPdf, downloadExecutivePdf, downloadDeveloperPdf, downloadHtmlReport,
  downloadResearchPdf, downloadWordReport, downloadPptxReport, downloadEnterprisePdf, exportHistoryUrl, type ScanResult,
} from "../api/client";

export default function ExportCenter() {
  const [scans, setScans] = useState<ScanResult[] | null>(null);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => { getHistory({ limit: 50, sort: "date", order: "desc" }).then((d) => setScans(d.results)); }, []);

  useEffect(() => { if (scans && scans.length > 0 && !selected) setSelected(scans[0].id); }, [scans, selected]);

  const go = (url: string, label: string) => {
    toast.success(`Generating ${label}...`);
    window.open(url, "_blank");
  };

  const scanFormats = [
    { icon: Building2, title: "Enterprise Report", desc: "Cover page, architecture, findings, AI explanation, recommendations & appendix", action: () => selected && go(downloadEnterprisePdf(selected), "enterprise report") },
    { icon: FileText, title: "Standard PDF Report", desc: "Full technical scan report with charts and recommendations", action: () => selected && go(downloadScanPdf(selected), "PDF report") },
    { icon: Users, title: "Executive PDF", desc: "One-page, non-technical summary for stakeholders", action: () => selected && go(downloadExecutivePdf(selected), "executive report") },
    { icon: Code2, title: "Developer PDF", desc: "Full technical deep-dive: function stats, line findings, recommendations", action: () => selected && go(downloadDeveloperPdf(selected), "developer report") },
    { icon: Globe, title: "HTML Report", desc: "Self-contained, shareable HTML document", action: () => selected && go(downloadHtmlReport(selected), "HTML report") },
    { icon: FileType2, title: "Word Report (.docx)", desc: "Editable technical report for further write-up", action: () => selected && go(downloadWordReport(selected), "Word report") },
    { icon: PresentationIcon, title: "PowerPoint Deck (.pptx)", desc: "4-slide summary deck, ready to present", action: () => selected && go(downloadPptxReport(selected), "PowerPoint deck") },
  ];

  const bulkFormats = [
    { icon: Table, title: "Scan History (CSV)", desc: "All scans, spreadsheet-friendly", action: () => go(exportHistoryUrl("csv"), "CSV export") },
    { icon: Braces, title: "Scan History (JSON)", desc: "All scans, machine-readable", action: () => go(exportHistoryUrl("json"), "JSON export") },
    { icon: FlaskConical, title: "Research Appendix (PDF)", desc: "Model architecture, dataset & evaluation methodology", action: () => go(downloadResearchPdf(), "research appendix") },
  ];

  return (
    <PageShell title="Export Center" subtitle="Every report format, in one place">
      <ChartCard title="Select a Scan" subtitle="Used for the per-scan export formats below" className="mb-5">
        {!scans ? <Spinner label="Loading scans..." /> : scans.length === 0 ? (
          <EmptyState icon={FileText} title="No scans yet" description="Run a scan first to generate per-scan reports." />
        ) : (
          <select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-full max-w-md bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-sm focus-ring outline-none">
            {scans.map((s) => <option key={s.id} value={s.id}>{s.filename} — {s.project_name} ({s.risk_level})</option>)}
          </select>
        )}
      </ChartCard>

      <div className="mb-2 text-sm font-semibold">Per-Scan Reports</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {scanFormats.map((f) => (
          <button key={f.title} onClick={f.action} disabled={!selected} className="card card-hover p-5 text-left disabled:opacity-40 disabled:cursor-not-allowed">
            <f.icon size={20} className="text-(--accent) mb-3" />
            <div className="text-sm font-semibold flex items-center justify-between">{f.title} <Download size={13} className="text-(--text-muted)" /></div>
            <div className="text-xs text-(--text-muted) mt-1">{f.desc}</div>
          </button>
        ))}
      </div>

      <div className="mb-2 text-sm font-semibold">Bulk & Research Exports</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {bulkFormats.map((f) => (
          <button key={f.title} onClick={f.action} className="card card-hover p-5 text-left">
            <f.icon size={20} className="text-(--series-7) mb-3" />
            <div className="text-sm font-semibold flex items-center justify-between">{f.title} <Download size={13} className="text-(--text-muted)" /></div>
            <div className="text-xs text-(--text-muted) mt-1">{f.desc}</div>
          </button>
        ))}
      </div>
    </PageShell>
  );
}
