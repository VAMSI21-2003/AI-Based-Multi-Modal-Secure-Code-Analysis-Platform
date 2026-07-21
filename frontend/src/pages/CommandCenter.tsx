import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  ShieldAlert, ShieldCheck, Skull, Radio, FileWarning, ArrowUpRight, MemoryStick, Bug, PenTool, Droplet, MonitorPlay, Sparkles,
  Cpu, Server, Zap, FolderGit2, ScanLine, FolderOpen, X, Loader2, CheckCircle2,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import Gauge from "../components/Gauge";
import { CardSkeleton } from "../components/Loading";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import RiskDistributionChart from "../components/RiskDistributionChart";
import {
  getDashboardStats, getHistory, getCodeHealth, getSystemStats, getBatches, scanCode,
  type DashboardStats, type ScanResult, type CodeHealth, type SystemStats,
} from "../api/client";
import { timeAgo } from "../utils/risk";
import ThreatRadar from "../components/ThreatRadar";

const LIVE_POLL_MS = 8000;

export default function CommandCenter() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [topDangerous, setTopDangerous] = useState<ScanResult[] | null>(null);
  const [health, setHealth] = useState<CodeHealth | null>(null);
  const [system, setSystem] = useState<SystemStats | null>(null);
  const [projects, setProjects] = useState<Awaited<ReturnType<typeof getBatches>> | null>(null);
  const [quickScanOpen, setQuickScanOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getHistory({ sort: "risk", order: "desc", limit: 10 }).then((d) => { if (!cancelled) setTopDangerous(d.results); });
    getCodeHealth().then((h) => { if (!cancelled) setHealth(h); });
    getBatches().then((b) => { if (!cancelled) setProjects(b.slice(0, 6)); });
    return () => { cancelled = true; };
  }, []);

  // Everything else on this SOC-style homepage updates automatically --
  // security posture, system telemetry, and the live scan feed all poll on
  // the same cadence rather than requiring a manual refresh.
  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      getDashboardStats().then((s) => { if (!cancelled) setStats(s); }).catch(() => {});
      getSystemStats().then((s) => { if (!cancelled) setSystem(s); }).catch(() => {});
    };
    poll();
    const id = setInterval(poll, LIVE_POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const securityScore = stats ? Math.max(0, Math.round(100 - stats.average_risk_percent)) : 0;
  const critical = stats?.risk_distribution["CRITICAL"] ?? 0;

  return (
    <PageShell
      title="AI Security Command Center"
      subtitle="Real-time SOC-style overview of your codebase security posture"
      glow
      actions={
        <>
          <button onClick={() => setQuickScanOpen(true)} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110">
            <ScanLine size={13} /> Quick Scan
          </button>
          <Link to="/scan-center?tab=project-scanner" className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-semibold hover:bg-(--surface-3)">
            <FolderGit2 size={13} /> Quick Repository Scan
          </Link>
          <Link to="/welcome" className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-semibold hover:bg-(--surface-3)">
            <Sparkles size={13} /> Home
          </Link>
          <Link to="/presentation" className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-xs font-semibold hover:bg-(--surface-3)">
            <MonitorPlay size={13} /> Presentation Mode
          </Link>
        </>
      }
    >
      {!stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-5">
            <div className="card p-6 flex flex-col items-center relative overflow-hidden" style={{ boxShadow: "0 0 40px -12px rgba(57,135,229,0.25)" }}>
              <div className="text-xs uppercase tracking-wider text-(--text-muted) mb-2 flex items-center gap-1.5"><Radio size={12} className="text-(--status-good) animate-pulse-soft" /> Security Score</div>
              <Gauge value={securityScore} color={securityScore >= 70 ? "var(--status-good)" : securityScore >= 40 ? "var(--status-warning)" : "var(--status-critical)"} size={150} />
            </div>
            <div className="card p-6 flex flex-col items-center">
              <div className="text-xs uppercase tracking-wider text-(--text-muted) mb-2">Overall Risk Meter</div>
              <Gauge value={stats.average_risk_percent} color="var(--status-serious)" size={150} />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <MiniStat icon={Skull} label="Critical Files" value={critical} color="var(--status-critical)" />
              <MiniStat icon={ShieldAlert} label="Vulnerable Files" value={stats.total_vulnerabilities} color="var(--status-serious)" />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <MiniStat icon={ShieldCheck} label="Safe Files" value={stats.safe_count} color="var(--status-good)" />
              <MiniStat icon={FileWarning} label="Total Scanned" value={stats.total_files_scanned} color="var(--series-1)" />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
            {health?.available && (
              <ChartCard title="Code Health" subtitle={`Aggregated across the ${health.files_analyzed} most recently scanned files (${health.functions_analyzed} functions)`} className="xl:col-span-2">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <MiniStat icon={MemoryStick} label="Memory Issues" value={health.memory_issues} color="var(--series-6)" />
                  <MiniStat icon={Bug} label="Buffer Issues" value={health.buffer_issues} color="var(--status-critical)" />
                  <MiniStat icon={PenTool} label="Pointer Issues" value={health.pointer_issues} color="var(--series-7)" />
                  <MiniStat icon={Droplet} label="Leaks" value={health.leaks} color="var(--status-warning)" />
                </div>
              </ChartCard>
            )}
            <ThreatRadar />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
            <ChartCard title="Threat Activity" subtitle="Scans vs. vulnerabilities, last 14 days" className="xl:col-span-2">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={stats.trend_14d} margin={{ left: -20, right: 10, top: 10 }}>
                  <defs>
                    <linearGradient id="ccScans" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3987e5" stopOpacity={0.35} /><stop offset="100%" stopColor="#3987e5" stopOpacity={0} /></linearGradient>
                    <linearGradient id="ccVuln" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d03b3b" stopOpacity={0.4} /><stop offset="100%" stopColor="#d03b3b" stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--gridline)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <RTooltip {...chartTooltipStyle} />
                  <Area type="monotone" dataKey="scans" name="Scans" stroke="#3987e5" fill="url(#ccScans)" strokeWidth={2} />
                  <Area type="monotone" dataKey="vulnerabilities" name="Vulnerabilities" stroke="#d03b3b" fill="url(#ccVuln)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Risk Distribution">
              <RiskDistributionChart data={stats.risk_distribution} height={240} />
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <ChartCard title="Top 10 Most Dangerous Files" subtitle="Ranked by vulnerability probability">
              {!topDangerous || topDangerous.length === 0 ? (
                <div className="text-xs text-(--text-muted) py-6 text-center">No scans yet.</div>
              ) : (
                <div className="space-y-1.5">
                  {topDangerous.map((f, i) => (
                    <Link key={f.id} to={`/analysis?scan=${f.id}`} className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-(--surface-3) transition-colors">
                      <span className={`w-6 h-6 rounded-md flex items-center justify-center text-[11px] font-bold shrink-0 ${i < 3 ? "bg-(--status-critical)/20 text-(--status-critical)" : "bg-(--surface-3) text-(--text-muted)"}`}>{i + 1}</span>
                      <span className="text-xs mono truncate flex-1">{f.filename}</span>
                      <RiskBadge level={f.risk_level} size="sm" />
                      <span className="text-xs tabular text-(--text-muted) w-12 text-right">{f.vuln_probability.toFixed(1)}%</span>
                    </Link>
                  ))}
                </div>
              )}
            </ChartCard>

            <ChartCard title="Recent Scans" subtitle="Latest activity, live">
              {stats.recent_scans.length === 0 ? (
                <div className="text-xs text-(--text-muted) py-6 text-center">No scans yet.</div>
              ) : (
                <div className="divide-y divide-(--border-hairline)">
                  {stats.recent_scans.map((s) => (
                    <Link key={s.id} to={`/analysis?scan=${s.id}`} className="flex items-center justify-between py-2.5 hover:bg-(--surface-3) transition-colors -mx-1 px-1 rounded-lg">
                      <div className="min-w-0">
                        <div className="text-xs font-medium mono truncate">{s.filename}</div>
                        <div className="text-[10px] text-(--text-muted)">{timeAgo(s.created_at)}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <VerdictPill verdict={s.verdict} />
                        <ArrowUpRight size={12} className="text-(--text-muted)" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mt-5">
            <ChartCard title="System & Model Status" subtitle={system ? `Uptime ${fmtUptime(system.uptime_sec)} · ${system.files_scanned_total} files scanned this session` : "Loading telemetry..."}>
              {!system ? (
                <div className="text-xs text-(--text-muted) py-6 text-center">Loading...</div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <MiniStat icon={Cpu} label="CPU" value={Math.round(system.cpu_percent)} suffix="%" color={system.cpu_percent >= 80 ? "var(--status-critical)" : "var(--series-1)"} />
                  <MiniStat icon={Server} label="RAM" value={Math.round(system.ram_percent)} suffix="%" color={system.ram_percent >= 80 ? "var(--status-critical)" : "var(--series-5)"} />
                  <MiniStat icon={Zap} label="Avg Latency" value={system.avg_prediction_latency_ms !== null ? Math.round(system.avg_prediction_latency_ms) : 0} suffix="ms" color="var(--series-7)" />
                  <MiniStat icon={CheckCircle2} label="Models Loaded" value={Object.keys(system.model_load_times_sec).length} color="var(--status-good)" />
                  <div className="col-span-2 md:col-span-4 pt-2 border-t border-(--border-hairline) flex flex-wrap gap-1.5">
                    {Object.keys(system.model_load_times_sec).length === 0 ? (
                      <span className="text-[11px] text-(--text-muted)">No model load telemetry recorded yet.</span>
                    ) : (
                      Object.entries(system.model_load_times_sec).map(([name, secs]) => (
                        <span key={name} className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-(--status-good)/12 text-(--status-good)">
                          <CheckCircle2 size={11} /> {name} &middot; {secs.toFixed(2)}s load
                        </span>
                      ))
                    )}
                  </div>
                </div>
              )}
            </ChartCard>

            <ChartCard title="Recent Projects" subtitle="Latest repository / batch scans" actions={<Link to="/scan-center?tab=project-scanner" className="text-xs text-(--accent) hover:underline flex items-center gap-1">View all <ArrowUpRight size={11} /></Link>}>
              {!projects || projects.length === 0 ? (
                <div className="text-xs text-(--text-muted) py-6 text-center flex flex-col items-center gap-2">
                  <FolderOpen size={20} className="text-(--text-muted)" />
                  No repository scans yet.
                </div>
              ) : (
                <div className="space-y-1.5">
                  {projects.map((p) => (
                    <Link key={p.batch_id} to={`/project-scanner?batch=${p.batch_id}`} className="flex items-center justify-between px-2.5 py-2 rounded-lg hover:bg-(--surface-3) transition-colors">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold truncate">{p.project_name}</div>
                        <div className="text-[10px] text-(--text-muted)">{p.total_files} files &middot; {timeAgo(p.created_at)}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {p.vulnerable_files > 0 && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-(--status-critical)/15 text-(--status-critical)">{p.vulnerable_files} vulnerable</span>}
                        <ArrowUpRight size={12} className="text-(--text-muted)" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </ChartCard>
          </div>
        </>
      )}

      {quickScanOpen && <QuickScanModal onClose={() => setQuickScanOpen(false)} />}
    </PageShell>
  );
}

function fmtUptime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${Math.round(sec)}s`;
}

function QuickScanModal({ onClose }: { onClose: () => void }) {
  const [code, setCode] = useState("");
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);

  const run = async () => {
    if (!code.trim()) { toast.error("Paste some C/C++ code first"); return; }
    setScanning(true);
    setResult(null);
    try {
      const r = await scanCode({ code, project_name: "Command Center Quick Scan", filename: "quick_scan.c", model_choice: "XGBoost", source: "paste" });
      setResult(r);
      toast.success(`Scan complete — ${r.verdict}`);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[900] flex items-center justify-center p-6" style={{ background: "rgba(5,5,7,0.7)", backdropFilter: "blur(4px)" }} onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border border-(--border-hairline-strong) bg-(--surface-2) p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold flex items-center gap-1.5"><ScanLine size={15} className="text-(--accent)" /> Quick Scan</div>
          <button onClick={onClose} className="text-(--text-muted) hover:text-(--text-primary)"><X size={18} /></button>
        </div>
        <textarea
          value={code} onChange={(e) => setCode(e.target.value)}
          placeholder="Paste a C/C++ snippet to scan immediately..."
          className="w-full h-40 bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-xs mono focus-ring outline-none resize-none"
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-[11px] text-(--text-muted)">For a full folder/zip, use Quick Repository Scan instead.</span>
          <button onClick={run} disabled={scanning} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-xs font-semibold hover:brightness-110 disabled:opacity-50">
            {scanning ? <Loader2 size={13} className="animate-spin" /> : <ScanLine size={13} />} {scanning ? "Scanning..." : "Scan Now"}
          </button>
        </div>

        {result && (
          <div className="mt-4 pt-4 border-t border-(--border-hairline) flex items-center justify-between">
            <div className="flex items-center gap-2">
              <VerdictPill verdict={result.verdict} />
              <span className="text-xs text-(--text-muted)">{result.vuln_probability.toFixed(1)}% risk &middot; {result.confidence.toFixed(1)}% confidence</span>
            </div>
            <Link to={`/analysis?scan=${result.id}`} onClick={onClose} className="text-xs text-(--accent) hover:underline flex items-center gap-1">Open full analysis <ArrowUpRight size={11} /></Link>
          </div>
        )}
      </div>
    </div>
  );
}

function MiniStat({ icon: Icon, label, value, color, suffix = "" }: { icon: any; label: string; value: number; color: string; suffix?: string }) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}1f`, color }}>
        <Icon size={16} />
      </div>
      <div className="min-w-0">
        <div className="text-lg font-bold tabular">{value}{suffix}</div>
        <div className="text-[10px] uppercase tracking-wider text-(--text-muted) truncate">{label}</div>
      </div>
    </div>
  );
}
