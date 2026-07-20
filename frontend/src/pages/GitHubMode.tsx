import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  GitFork, GitCommit, Download, FolderGit2, ArrowUpRight, ShieldCheck, ShieldAlert, FileCode2, GitBranch,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import StatCard from "../components/StatCard";
import Gauge from "../components/Gauge";
import { Spinner } from "../components/Loading";
import {
  scanGitHubRepo, getProjectSummary, getGitHubCommits, downloadBatchPdf,
  type ProjectSummary, type GitHubCommit,
} from "../api/client";
import { RISK_HEX, timeAgo } from "../utils/risk";

export default function GitHubMode() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const batchId = params.get("batch");

  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [scanning, setScanning] = useState(false);

  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [commits, setCommits] = useState<GitHubCommit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!batchId) return;
    setError(null);
    Promise.all([getProjectSummary(batchId), getGitHubCommits(batchId)])
      .then(([s, c]) => { setSummary(s); setCommits(c); })
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Failed to load repository scan"));
  }, [batchId]);

  const onScan = async () => {
    if (!url.trim()) { toast.error("Enter a GitHub repository URL"); return; }
    setScanning(true);
    try {
      const r = await scanGitHubRepo(url.trim(), name.trim() || undefined);
      toast.success(`Cloned & scanned ${r.files_scanned} file(s)`);
      navigate(`/github-mode?batch=${r.batch_id}`);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to clone/scan repository");
    } finally {
      setScanning(false);
    }
  };

  if (!batchId) {
    return (
      <PageShell title="GitHub Mode" subtitle="Clone a public repository and scan every file with the same pipeline">
        <ChartCard title="Scan a GitHub Repository" subtitle="The backend clones the repo locally (shallow, last 50 commits), scans it, then deletes the local copy">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <GitFork size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-muted)" />
              <input
                value={url} onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo.git"
                className="w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg pl-9 pr-3 py-2.5 text-sm mono focus-ring outline-none"
              />
            </div>
            <input
              value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Project name (optional)"
              className="md:w-64 bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-sm focus-ring outline-none"
            />
            <button
              onClick={onScan} disabled={scanning}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 disabled:opacity-50"
            >
              <GitFork size={15} /> {scanning ? "Cloning & scanning..." : "Scan Repository"}
            </button>
          </div>
          <div className="text-xs text-(--text-muted) mt-3">Only plain http(s) git URLs are accepted (public repositories). Only text is read — nothing in the repository is ever executed.</div>
        </ChartCard>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell title="GitHub Mode" subtitle="Clone a public repository and scan every file with the same pipeline">
        <div className="card p-4 text-sm text-(--status-critical)">{error}</div>
        <Link to="/github-mode" className="text-xs text-(--accent) mt-3 inline-block">&larr; Try another repository</Link>
      </PageShell>
    );
  }

  if (!summary || !commits) {
    return (
      <PageShell title="GitHub Mode" subtitle="Clone a public repository and scan every file with the same pipeline">
        <Spinner label="Loading repository scan..." />
      </PageShell>
    );
  }

  return (
    <PageShell
      title={summary.project_name}
      subtitle={`GitHub Mode — ${summary.total_files} files · scanned ${timeAgo(summary.created_at)}`}
      actions={
        <>
          <Link to={`/project-scanner?batch=${batchId}`} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <FolderGit2 size={15} /> Full Risk Map
          </Link>
          <Link to={`/dependency-graph?batch=${batchId}`} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <GitBranch size={15} /> Dependency Graph
          </Link>
          <a href={downloadBatchPdf(batchId)} onClick={() => toast.success("Generating repository PDF report...")} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">
            <Download size={15} /> Export PDF
          </a>
        </>
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Files Scanned" value={summary.total_files} icon={FileCode2} accent="var(--series-1)" />
        <StatCard label="Safe Files" value={summary.safe_files} icon={ShieldCheck} accent="var(--status-good)" />
        <StatCard label="Vulnerable Files" value={summary.vulnerable_files} icon={ShieldAlert} accent="var(--status-critical)" />
        <div className="card p-5 flex items-center gap-4">
          <Gauge value={summary.security_score} size={64} color={summary.security_score >= 70 ? "var(--status-good)" : summary.security_score >= 40 ? "var(--status-warning)" : "var(--status-critical)"} />
          <div>
            <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium">Repo Health Score</div>
            <div className="text-xl font-bold tabular mt-0.5">{summary.security_score}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <ChartCard title="Commit History" subtitle={`Last ${commits.length} commit(s) on the default branch`}>
          {commits.length === 0 ? (
            <div className="text-sm text-(--text-muted) py-6 text-center">No commit history available for this clone.</div>
          ) : (
            <div className="space-y-0 max-h-[420px] overflow-y-auto scrollbar-thin pr-1">
              {commits.map((c, i) => (
                <div key={c.hash} className="flex gap-3 relative pb-4">
                  <div className="flex flex-col items-center">
                    <span className="w-2.5 h-2.5 rounded-full bg-(--accent) shrink-0 mt-1" />
                    {i < commits.length - 1 && <span className="w-px flex-1 bg-(--border-hairline)" />}
                  </div>
                  <div className="min-w-0 pb-1">
                    <div className="text-sm text-(--text-primary) truncate">{c.message}</div>
                    <div className="text-xs text-(--text-muted) mt-0.5 flex items-center gap-2">
                      <GitCommit size={11} /> <span className="mono">{c.hash}</span>
                      <span>&middot;</span> {c.author}
                      <span>&middot;</span> {timeAgo(c.date)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>

        <ChartCard title="Risk Map Preview" subtitle="Click any file to open its full analysis — or use Full Risk Map above">
          <div className="grid grid-cols-2 gap-3 max-h-[420px] overflow-y-auto scrollbar-thin pr-1">
            {summary.files.slice(0, 12).map((f) => {
              const color = RISK_HEX[f.risk_level] ?? "#898781";
              return (
                <Link key={f.id} to={`/analysis?scan=${f.id}`} className="rounded-xl p-3 border card-hover transition-transform" style={{ background: `${color}14`, borderColor: `${color}55` }}>
                  <div className="flex items-center justify-between mb-1.5">
                    <FileCode2 size={13} style={{ color }} />
                    <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                  </div>
                  <div className="text-xs font-semibold mono truncate">{f.filename}</div>
                  <div className="text-[10px] mt-0.5" style={{ color }}>{f.risk_level}</div>
                </Link>
              );
            })}
          </div>
          {summary.files.length > 12 && (
            <Link to={`/project-scanner?batch=${batchId}`} className="mt-3 inline-flex items-center gap-1 text-xs text-(--accent) font-semibold">
              View all {summary.files.length} files <ArrowUpRight size={12} />
            </Link>
          )}
        </ChartCard>
      </div>
    </PageShell>
  );
}
