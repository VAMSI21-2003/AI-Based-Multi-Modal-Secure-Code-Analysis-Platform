import { Link } from "react-router-dom";
import {
  FileSearch, ShieldAlert, ShieldCheck, Gauge as GaugeIcon, Percent, AlertTriangle, ScanLine, ArrowUpRight,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Legend,
} from "recharts";
import PageShell from "../components/PageShell";
import StatCard from "../components/StatCard";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import RiskDistributionChart from "../components/RiskDistributionChart";
import { CardSkeleton, EmptyState } from "../components/Loading";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import { getDashboardStats } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { timeAgo } from "../utils/risk";

export default function Dashboard() {
  const { data, loading, error } = useFetch(getDashboardStats);

  return (
    <PageShell
      title="Dashboard"
      subtitle="Real-time overview of your codebase security posture"
      glow
      actions={
        <Link
          to="/scanner"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 transition shadow-[0_0_20px_var(--accent-glow)]"
        >
          <ScanLine size={15} /> New Scan
        </Link>
      }
    >
      {error && (
        <div className="card p-4 mb-4 border-(--status-critical) text-sm text-(--status-critical)">
          Failed to load dashboard: {error}
        </div>
      )}

      {loading || !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <StatCard label="Files Scanned" value={data.total_files_scanned} icon={FileSearch} accent="var(--series-1)" delay={0} />
            <StatCard label="Vulnerabilities" value={data.total_vulnerabilities} icon={ShieldAlert} accent="var(--status-critical)" delay={0.03} />
            <StatCard label="Safe Files" value={data.safe_count} icon={ShieldCheck} accent="var(--status-good)" delay={0.06} />
            <StatCard label="Avg. Risk" value={data.average_risk_percent} suffix="%" decimals={1} icon={GaugeIcon} accent="var(--status-warning)" delay={0.09} />
            <StatCard label="Avg. Confidence" value={data.average_confidence_percent} suffix="%" decimals={1} icon={Percent} accent="var(--series-7)" delay={0.12} />
            <div className="card card-hover p-5 flex flex-col justify-between">
              <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium flex items-center gap-1.5">
                <AlertTriangle size={12} /> Top Vulnerability
              </div>
              <div className="mt-2 text-2xl font-bold text-(--text-primary)">
                {data.most_common_vulnerability ?? "—"}
              </div>
              <div className="text-xs text-(--text-muted) mt-1">
                {data.most_common_vulnerability ? "Most frequent CWE this period" : "No vulnerabilities recorded yet"}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            <ChartCard title="Scan Activity" subtitle="Last 14 days" className="xl:col-span-2">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={data.trend_14d} margin={{ left: -20, right: 10, top: 10 }}>
                  <defs>
                    <linearGradient id="scansGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3987e5" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#3987e5" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="vulnGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#d03b3b" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#d03b3b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--gridline)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => d.slice(5)}
                    tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                    axisLine={{ stroke: "var(--baseline)" }}
                    tickLine={false}
                  />
                  <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <RTooltip {...chartTooltipStyle} />
                  <Area type="monotone" dataKey="scans" name="Scans" stroke="#3987e5" fill="url(#scansGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="vulnerabilities" name="Vulnerabilities" stroke="#d03b3b" fill="url(#vulnGrad)" strokeWidth={2} />
                  <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Risk Distribution" subtitle="Across all scanned files">
              <RiskDistributionChart data={data.risk_distribution} height={260} innerRadius={58} outerRadius={90} legendLayout="vertical" />
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            <ChartCard title="Recent Scans" subtitle="Latest activity across all projects" className="xl:col-span-2">
              {data.recent_scans.length === 0 ? (
                <EmptyState icon={ScanLine} title="No scans yet" description="Run your first scan to see results here." action={
                  <Link to="/scanner" className="text-xs font-semibold text-(--accent) inline-flex items-center gap-1">
                    Go to Code Scanner <ArrowUpRight size={13} />
                  </Link>
                } />
              ) : (
                <div className="divide-y divide-(--border-hairline)">
                  {data.recent_scans.map((s) => (
                    <Link
                      key={s.id}
                      to={`/analysis?scan=${s.id}`}
                      className="flex items-center justify-between py-3 px-1 hover:bg-(--surface-3) rounded-lg transition-colors -mx-1"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-(--text-primary) truncate mono">{s.filename}</div>
                        <div className="text-xs text-(--text-muted) mt-0.5">{s.project_name} &middot; {timeAgo(s.created_at)}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        <RiskBadge level={s.risk_level} size="sm" />
                        <VerdictPill verdict={s.verdict} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </ChartCard>

            <ChartCard title="Model Status" subtitle="Detection engine health">
              <div className="space-y-3">
                {Object.entries(data.models_status).map(([name, status]) => (
                  <div key={name} className="flex items-center justify-between p-3 rounded-lg bg-(--surface-3)">
                    <div className="text-sm font-medium capitalize">{name.replace("_", " ")}</div>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${status.available ? "text-(--status-good)" : "text-(--status-critical)"}`}
                      style={{ background: status.available ? "rgba(12,163,12,0.14)" : "rgba(208,59,59,0.14)" }}>
                      {status.available ? "Loaded" : "Missing"}
                    </span>
                  </div>
                ))}
                <div className="text-xs text-(--text-muted) pt-2 border-t border-(--border-hairline)">
                  Pipeline: AST (11) + Metrics (13) + CodeBERT (768) &rarr; 792-dim fused vector &rarr; XGBoost / Random Forest.
                </div>
              </div>
            </ChartCard>
          </div>
        </>
      )}
    </PageShell>
  );
}
