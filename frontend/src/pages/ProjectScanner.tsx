import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import {
  FolderGit2, FileCode2, ShieldAlert, ShieldCheck, AlertTriangle, Download, ScanLine, ArrowUpRight, GitBranch, Zap, BookOpen, Code2,
  FileText, Percent, Gauge as GaugeIcon, Clock, FolderTree, Workflow, Skull, Flame, AlertCircle, Info,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import StatCard from "../components/StatCard";
import RiskDistributionChart from "../components/RiskDistributionChart";
import Gauge from "../components/Gauge";
import { Spinner, EmptyState } from "../components/Loading";
import { getProjectSummary, getBatches, downloadBatchPdf, downloadEnterpriseProjectPdf, type ProjectSummary } from "../api/client";
import toast from "react-hot-toast";
import { RISK_HEX, timeAgo } from "../utils/risk";

export default function ProjectScanner() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");
  const [data, setData] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batches, setBatches] = useState<any[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!batchId) {
      getBatches().then((b) => { if (!cancelled) setBatches(b); });
      return () => { cancelled = true; };
    }
    setLoading(true);
    setError(null);
    getProjectSummary(batchId)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to load project"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    // Without this guard, quickly switching batches (e.g. clicking two
    // project cards in a row) could let an earlier, slower request for a
    // DIFFERENT batch resolve after the current one and overwrite this
    // page with the wrong project's numbers -- reproduced while auditing
    // this page (stat tiles briefly showed 0 / mismatched values after
    // fast navigation between batches).
    return () => { cancelled = true; };
  }, [batchId]);

  if (!batchId) {
    return (
      <PageShell
        title="Project Scanner"
        subtitle="Multi-file / folder / zip project-wide security dashboard"
        actions={
          <Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">
            <ScanLine size={15} /> Scan a Project
          </Link>
        }
      >
        {!batches ? <Spinner label="Loading projects..." /> : batches.length === 0 ? (
          <EmptyState
            icon={FolderGit2}
            title="No projects scanned yet"
            description="Use Code Scanner → Batch Upload to scan a folder or zip archive. It will appear here as a project dashboard."
            action={<Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110"><ScanLine size={15} /> Go to Code Scanner</Link>}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {batches.map((b) => (
              <button
                key={b.batch_id}
                onClick={() => navigate(`/project-scanner?batch=${b.batch_id}`)}
                className="card card-hover p-5 text-left"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-semibold">{b.project_name}</div>
                  <ArrowUpRight size={14} className="text-(--text-muted)" />
                </div>
                <div className="text-xs text-(--text-muted)">{b.total_files} files &middot; {b.vulnerable_files} vulnerable &middot; {timeAgo(b.created_at)}</div>
              </button>
            ))}
          </div>
        )}
      </PageShell>
    );
  }

  if (loading || !data) {
    return (
      <PageShell title="Project Scanner" subtitle="Project-wide security dashboard">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Aggregating project results..." />}
      </PageShell>
    );
  }

  return (
    <PageShell
      title={data.project_name}
      subtitle={`Project Scanner · ${data.total_files} files · scanned ${timeAgo(data.created_at)}`}
      actions={
        <>
          <Link to={`/dependency-graph?batch=${data.batch_id}`} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <GitBranch size={15} /> Dependency Graph
          </Link>
          <a href={downloadBatchPdf(data.batch_id)} onClick={() => toast.success("Generating quick project PDF...")} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <Download size={15} /> Quick PDF
          </a>
          <a href={downloadEnterpriseProjectPdf(data.batch_id)} onClick={() => toast.success("Generating executive repository report...")} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">
            <Download size={15} /> Executive Report
          </a>
        </>
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <StatCard label="Total Files" value={data.total_files} icon={FileCode2} accent="var(--series-1)" />
        <StatCard label="Functions" value={data.function_count ?? 0} icon={FileCode2} accent="var(--series-5)" />
        <StatCard label="Safe Files" value={data.safe_files} icon={ShieldCheck} accent="var(--status-good)" />
        <StatCard label="Vulnerable Files" value={data.vulnerable_files} icon={ShieldAlert} accent="var(--status-critical)" />
        <div className="card card-hover p-5">
          <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium flex items-center gap-1.5 mb-1">
            <AlertTriangle size={12} /> Highest Risk File
          </div>
          {data.highest_risk_file ? (
            <Link to={`/analysis?scan=${data.highest_risk_file.id}`} className="block hover:text-(--accent) transition-colors">
              <div className="text-sm font-semibold mono truncate">{data.highest_risk_file.filename}</div>
              <div className="text-xs text-(--text-muted)">{data.highest_risk_file.vuln_probability.toFixed(1)}% vulnerability probability</div>
            </Link>
          ) : <div className="text-xs text-(--text-muted)">N/A</div>}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Lines of Code" value={data.total_loc ?? 0} icon={FileText} accent="var(--series-4)" />
        <StatCard label="Avg. Confidence" value={data.avg_confidence ?? 0} suffix="%" decimals={1} icon={Percent} accent="var(--series-6)" />
        <StatCard label="Avg. Maintainability" value={data.avg_maintainability ?? 0} decimals={1} icon={GaugeIcon} accent="var(--series-2)" />
        <StatCard label="Scan Duration" value={data.scan_duration_sec ?? 0} suffix="s" decimals={1} icon={Clock} accent="var(--series-3)" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        <div className="card card-hover p-5">
          <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium flex items-center gap-1.5 mb-1">
            <FolderTree size={12} /> Most Dangerous Folder
          </div>
          {data.most_dangerous_folder ? (
            <div>
              <div className="text-sm font-semibold mono truncate">{data.most_dangerous_folder.folder}/</div>
              <div className="text-xs text-(--text-muted)">{data.most_dangerous_folder.avg_risk.toFixed(1)}% avg. risk &middot; {data.most_dangerous_folder.worst_risk} &middot; {data.most_dangerous_folder.file_count} file(s)</div>
            </div>
          ) : <div className="text-xs text-(--text-muted)">No nested folders in this project.</div>}
        </div>
        <div className="card card-hover p-5">
          <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium flex items-center gap-1.5 mb-1">
            <Workflow size={12} /> Most Dangerous Function
          </div>
          {data.most_dangerous_function ? (
            <div>
              <div className="text-sm font-semibold mono truncate">{data.most_dangerous_function.name}()</div>
              <div className="text-xs text-(--text-muted)">{data.most_dangerous_function.file} &middot; {data.most_dangerous_function.dangerous_api_count} dangerous call(s) &middot; complexity {data.most_dangerous_function.complexity}</div>
            </div>
          ) : <div className="text-xs text-(--text-muted)">No dangerous API calls found in any function.</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Overall Project Security Score" className="flex flex-col items-center justify-center">
          <Gauge value={data.security_score} color={data.security_score >= 70 ? "var(--status-good)" : data.security_score >= 40 ? "var(--status-warning)" : "var(--status-critical)"} />
        </ChartCard>
        <ChartCard title="Risk Distribution" className="xl:col-span-2">
          <RiskDistributionChart data={data.risk_distribution} height={220} />
        </ChartCard>
      </div>

      {data.finding_severity_counts && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
          <StatCard label="Critical Findings" value={data.finding_severity_counts.critical} icon={Skull} accent="var(--status-critical)" />
          <StatCard label="High Findings" value={data.finding_severity_counts.high} icon={Flame} accent="var(--status-serious)" />
          <StatCard label="Medium Findings" value={data.finding_severity_counts.medium} icon={AlertCircle} accent="var(--status-warning)" />
          <StatCard label="Low Findings" value={data.finding_severity_counts.low} icon={Info} accent="var(--series-1)" />
        </div>
      )}

      {((data.most_dangerous_apis?.length ?? 0) > 0 || (data.most_common_cwe?.length ?? 0) > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
          <ChartCard title="Most Dangerous APIs" subtitle="Aggregated across every file in this project">
            {!data.most_dangerous_apis?.length ? (
              <div className="text-xs text-(--text-muted) py-6 text-center">None detected.</div>
            ) : (
              <div className="space-y-1.5">
                {data.most_dangerous_apis.map((d) => (
                  <div key={d.api} className="flex items-center justify-between text-xs bg-(--surface-3) rounded-lg p-2.5">
                    <span className="flex items-center gap-1.5 mono"><Zap size={12} className="text-(--status-critical)" /> {d.api}()</span>
                    <span className="tabular text-(--text-muted)">&times;{d.count}</span>
                  </div>
                ))}
              </div>
            )}
          </ChartCard>
          <ChartCard title="Most Common CWE" subtitle="Weakness categories found across every file in this project">
            {!data.most_common_cwe?.length ? (
              <div className="text-xs text-(--text-muted) py-6 text-center">None detected.</div>
            ) : (
              <div className="space-y-1.5">
                {data.most_common_cwe.map((d) => (
                  <div key={d.cwe} className="flex items-center justify-between text-xs bg-(--surface-3) rounded-lg p-2.5">
                    <span className="flex items-center gap-1.5"><BookOpen size={12} className="text-(--series-4)" /> <span className="mono">{d.cwe}</span> {d.name}</span>
                    <span className="tabular text-(--text-muted)">&times;{d.count}</span>
                  </div>
                ))}
              </div>
            )}
          </ChartCard>
        </div>
      )}

      <ChartCard title="Security Risk Map" subtitle="Every scanned file, colour-coded by risk — click to open its full analysis, or jump straight into Live IDE">
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {data.files.map((f) => {
            const color = RISK_HEX[f.risk_level] ?? "#898781";
            return (
              <div
                key={f.id}
                className="relative rounded-xl p-4 border card-hover transition-transform group"
                style={{ background: `${color}14`, borderColor: `${color}55` }}
              >
                <Link to={`/analysis?scan=${f.id}`} className="absolute inset-0 rounded-xl" aria-label={`Open full analysis for ${f.filename}`} />
                <Link
                  to={`/scan-center?tab=live-ide&scan=${f.id}`}
                  className="absolute top-3 right-3 z-10 p-1 rounded-md bg-(--surface-2)/80 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-(--accent) hover:text-white"
                  title="Open in Live IDE"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Code2 size={11} />
                </Link>
                <div className="flex items-center justify-between mb-2">
                  <FileCode2 size={15} style={{ color }} />
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
                </div>
                <div className="text-xs font-semibold mono truncate">{f.filename}</div>
                <div className="text-[11px] mt-1" style={{ color }}>{f.risk_level}</div>
                <div className="text-[10px] text-(--text-muted) mt-0.5">{f.vuln_probability.toFixed(1)}% risk</div>
              </div>
            );
          })}
        </div>
      </ChartCard>
    </PageShell>
  );
}
