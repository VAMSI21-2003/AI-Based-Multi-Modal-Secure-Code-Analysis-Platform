import { useEffect, useState } from "react";
import { Cpu, MemoryStick, Timer, Gauge as GaugeIcon, FileSearch, Activity } from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import StatCard from "../components/StatCard";
import { Spinner } from "../components/Loading";
import { getSystemStats, type SystemStats } from "../api/client";

const POLL_MS = 4000;

export default function SystemMonitor() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      getSystemStats()
        .then((s) => { if (!cancelled) { setStats(s); setError(null); } })
        .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to load"); });
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!stats) {
    return (
      <PageShell title="System Monitor" subtitle="Live engine telemetry — refreshes automatically">
        {error ? <div className="card p-4 text-sm text-(--status-critical)">{error}</div> : <Spinner label="Connecting to engine..." />}
      </PageShell>
    );
  }

  const latencyChartData = stats.recent_prediction_latencies_ms.map((v, i) => ({ idx: i + 1, ms: v }));

  return (
    <PageShell title="System Monitor" subtitle={`Live engine telemetry — auto-refreshing every ${POLL_MS / 1000}s`}>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-5">
        <StatCard label="CPU Usage" value={stats.cpu_percent} suffix="%" decimals={1} icon={Cpu} accent="var(--series-1)" />
        <StatCard label="RAM Usage" value={stats.ram_percent} suffix="%" decimals={1} icon={MemoryStick} accent="var(--series-6)" />
        <StatCard label="Process RAM" value={stats.process_ram_mb} suffix=" MB" decimals={0} icon={MemoryStick} accent="var(--series-7)" />
        <StatCard label="Avg Latency" value={stats.avg_prediction_latency_ms ?? 0} suffix=" ms" decimals={0} icon={Timer} accent="var(--series-4)" />
        <StatCard label="Files Scanned" value={stats.files_scanned_total} icon={FileSearch} accent="var(--status-good)" />
        <StatCard label="Uptime" value={stats.uptime_sec} suffix=" s" decimals={0} icon={Activity} accent="var(--series-5)" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Model Load Times" subtitle="One-time cost, first request only" className="xl:col-span-1">
          <div className="space-y-2.5">
            {Object.keys(stats.model_load_times_sec).length === 0 && (
              <div className="text-xs text-(--text-muted)">No models loaded yet — run a scan to warm the engine.</div>
            )}
            {Object.entries(stats.model_load_times_sec).map(([name, secs]) => (
              <div key={name} className="flex items-center justify-between p-2.5 rounded-lg bg-(--surface-3)">
                <span className="text-xs font-medium capitalize">{name.replace("_", " ")}</span>
                <span className="text-sm font-bold tabular">{secs.toFixed(2)}s</span>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Prediction Latency" subtitle="Most recent scan durations (ms)" className="xl:col-span-2">
          {latencyChartData.length === 0 ? (
            <div className="h-[180px] flex items-center justify-center text-sm text-(--text-muted)">No predictions recorded yet this session.</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={latencyChartData} margin={{ left: -10, right: 10, top: 10 }}>
                <defs>
                  <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c98500" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#c98500" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--gridline)" vertical={false} />
                <XAxis dataKey="idx" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
                <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} unit="ms" />
                <RTooltip {...chartTooltipStyle} />
                <Area type="monotone" dataKey="ms" name="Latency (ms)" stroke="#c98500" fill="url(#latGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <ChartCard title="Resource Overview" subtitle={<span className="flex items-center gap-1.5"><GaugeIcon size={12} /> System-wide vs. this process</span>}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat label="System RAM Used" value={`${stats.ram_used_mb.toLocaleString("en-US")} MB`} />
          <MiniStat label="System RAM Total" value={`${stats.ram_total_mb.toLocaleString("en-US")} MB`} />
          <MiniStat label="Process CPU" value={`${stats.process_cpu_percent.toFixed(1)}%`} />
          <MiniStat label="Predictions Tracked" value={stats.prediction_count_tracked} />
        </div>
      </ChartCard>
    </PageShell>
  );
}

function MiniStat({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
      <div className="text-base font-bold tabular mt-0.5">{value}</div>
    </div>
  );
}
