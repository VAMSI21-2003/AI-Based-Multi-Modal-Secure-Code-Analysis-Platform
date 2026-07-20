import { useEffect, useState } from "react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip as RTooltip } from "recharts";
import { Radio } from "lucide-react";
import { chartTooltipStyle } from "./ChartCard";
import { getCodeHealth, getDashboardStats } from "../api/client";

const POLL_MS = 12000;

interface RadarPoint { axis: string; value: number; }

// Live Threat Radar (Phase 5, priority #4): unlike the static Risk
// Distribution donut on Dashboard, this polls the real backend on an
// interval and re-renders — actually live, not just "computed once on
// page load." Categories are pulled from the code-health aggregate
// (memory/buffer/pointer/leak/dangerous-API counts) and the live risk
// distribution, both real, both already-existing endpoints.
export default function ThreatRadar() {
  const [data, setData] = useState<RadarPoint[] | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      Promise.all([getCodeHealth(), getDashboardStats()]).then(([health, stats]) => {
        if (cancelled) return;
        const critical = stats.risk_distribution["CRITICAL"] ?? 0;
        const highRisk = stats.risk_distribution["HIGH RISK"] ?? 0;
        setData([
          { axis: "Critical Files", value: critical },
          { axis: "High Risk", value: highRisk },
          { axis: "Memory", value: health.available ? health.memory_issues : 0 },
          { axis: "Buffers", value: health.available ? health.buffer_issues : 0 },
          { axis: "Pointers", value: health.available ? health.pointer_issues : 0 },
          { axis: "Leaks", value: health.available ? health.leaks : 0 },
        ]);
        setLastUpdated(new Date());
      }).catch(() => {});
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="text-sm font-semibold">Live Threat Radar</div>
        <span className="flex items-center gap-1.5 text-[10px] text-(--status-good) font-semibold uppercase tracking-wider">
          <Radio size={11} className="animate-pulse-soft" /> Live
        </span>
      </div>
      <div className="text-xs text-(--text-muted) mb-2">Current threat surface shape — refreshes automatically every {POLL_MS / 1000}s</div>
      {!data ? (
        <div className="h-[260px] flex items-center justify-center text-sm text-(--text-muted)">Loading...</div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <RadarChart data={data} outerRadius="75%">
            <PolarGrid stroke="var(--gridline)" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
            <PolarRadiusAxis tick={{ fill: "var(--text-muted)", fontSize: 9 }} allowDecimals={false} />
            <RTooltip {...chartTooltipStyle} />
            <Radar name="Threat Surface" dataKey="value" stroke="#d03b3b" fill="#d03b3b" fillOpacity={0.28} isAnimationActive animationDuration={600} />
          </RadarChart>
        </ResponsiveContainer>
      )}
      {lastUpdated && <div className="text-[10px] text-(--text-muted) text-right mt-1">Updated {lastUpdated.toLocaleTimeString()}</div>}
    </div>
  );
}
