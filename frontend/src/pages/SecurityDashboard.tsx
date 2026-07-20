import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Legend,
  BarChart, Bar,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import Gauge from "../components/Gauge";
import FeatureRadar from "../components/FeatureRadar";
import { Spinner } from "../components/Loading";
import {
  getDashboardStats, getSecurityTrends, getFeatureRadarAvg, getAnalyticsOverview,
  type DashboardStats, type SecurityTrendPoint,
} from "../api/client";

export default function SecurityDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [trend, setTrend] = useState<SecurityTrendPoint[] | null>(null);
  const [radar, setRadar] = useState<any>(null);
  const [overview, setOverview] = useState<any>(null);

  useEffect(() => {
    getDashboardStats().then(setStats);
    getSecurityTrends(14).then(setTrend);
    getFeatureRadarAvg().then(setRadar);
    getAnalyticsOverview().then(setOverview);
  }, []);

  if (!stats || !trend || !radar || !overview) {
    return <PageShell title="Security Dashboard" subtitle="Advanced analytics & historical trends"><Spinner label="Crunching security trends..." /></PageShell>;
  }

  const half = Math.floor(trend.length / 2) || 1;
  const firstHalf = trend.slice(0, half);
  const secondHalf = trend.slice(half);
  const avg = (arr: SecurityTrendPoint[], key: keyof SecurityTrendPoint) =>
    arr.length ? arr.reduce((a, t) => a + (t[key] as number), 0) / arr.length : 0;
  const riskDelta = avg(secondHalf, "avg_risk") - avg(firstHalf, "avg_risk");

  return (
    <PageShell title="Security Dashboard" subtitle="Advanced analytics, risk & complexity trends, and security KPIs">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5 mb-5">
        <ChartCard title="Avg. Risk" className="flex flex-col items-center"><Gauge value={stats.average_risk_percent} color="var(--status-serious)" /></ChartCard>
        <ChartCard title="Avg. Confidence" className="flex flex-col items-center"><Gauge value={stats.average_confidence_percent} color="var(--series-7)" /></ChartCard>
        <ChartCard title="Total Scans" className="flex flex-col items-center justify-center">
          <div className="text-4xl font-bold tabular">{stats.total_files_scanned}</div>
          <div className="text-xs text-(--text-muted) mt-1">files analysed</div>
        </ChartCard>
        <ChartCard title="Risk Trend (7d vs 7d)" className="flex flex-col items-center justify-center">
          <div className="flex items-center gap-2">
            {riskDelta > 1 ? <TrendingUp className="text-(--status-critical)" size={24} /> : riskDelta < -1 ? <TrendingDown className="text-(--status-good)" size={24} /> : <Minus className="text-(--text-muted)" size={24} />}
            <span className={`text-2xl font-bold tabular ${riskDelta > 1 ? "text-(--status-critical)" : riskDelta < -1 ? "text-(--status-good)" : ""}`}>
              {riskDelta > 0 ? "+" : ""}{riskDelta.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-(--text-muted) mt-1">vs. first half of period</div>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="Risk & Confidence Trend" subtitle="14-day rolling average">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trend} margin={{ left: -20, right: 10, top: 10 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
              <RTooltip {...chartTooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="avg_risk" name="Avg Risk %" stroke="#d03b3b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="avg_confidence" name="Avg Confidence %" stroke="#9085e9" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Complexity & Dangerous API Trend" subtitle="AST depth (avg) and dangerous-API hits per day">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={trend} margin={{ left: -20, right: 10, top: 10 }}>
              <CartesianGrid stroke="var(--gridline)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <RTooltip {...chartTooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="avg_complexity" name="Avg AST Depth" fill="#c98500" radius={[3, 3, 0, 0]} />
              <Bar dataKey="dangerous_apis" name="Dangerous API Hits" fill="#d95926" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <ChartCard title="Aggregate Structural Radar" subtitle={`Average AST & metric profile across ${radar.sample_size ?? 0} scans`}>
          {radar.available ? <FeatureRadar astFeatures={radar.ast_features} metricFeatures={radar.metric_features} /> : <div className="text-xs text-(--text-muted) py-10 text-center">Not enough data yet.</div>}
        </ChartCard>

        <ChartCard title="Top Vulnerabilities" subtitle="Most frequent CWE categories detected">
          {overview.cwe_frequency?.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={overview.cwe_frequency} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid stroke="var(--gridline)" horizontal={false} />
                <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="cwe" width={70} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <RTooltip {...chartTooltipStyle} />
                <Bar dataKey="count" fill="#d03b3b" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="text-xs text-(--text-muted) py-10 text-center">No vulnerabilities recorded yet.</div>}
        </ChartCard>
      </div>
    </PageShell>
  );
}
