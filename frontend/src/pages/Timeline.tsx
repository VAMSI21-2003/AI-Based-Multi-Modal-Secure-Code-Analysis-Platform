import { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Clock, FileCode2 } from "lucide-react";
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Cell, ZAxis,
} from "recharts";
import PageShell from "../components/PageShell";
import ChartCard, { chartTooltipStyle } from "../components/ChartCard";
import { Spinner, EmptyState } from "../components/Loading";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import { getHistory, type ScanResult } from "../api/client";
import { RISK_HEX } from "../utils/risk";

export default function Timeline() {
  const navigate = useNavigate();
  const [scans, setScans] = useState<ScanResult[] | null>(null);
  const [project, setProject] = useState("");
  const [projects, setProjects] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    getHistory({ limit: 200, sort: "date", order: "desc", project: project || undefined })
      .then((d) => { if (!cancelled) { setScans(d.results); setProjects(d.projects); } });
    return () => { cancelled = true; };
  }, [project]);

  const chartData = useMemo(() => {
    if (!scans) return [];
    return scans.map((s) => ({
      x: new Date(s.created_at).getTime(),
      y: s.vuln_probability,
      id: s.id,
      filename: s.filename,
      risk: s.risk_level,
      verdict: s.verdict,
    }));
  }, [scans]);

  // Explicit evenly-spaced ticks, deduplicated by the day the tickFormatter
  // renders — Recharts' own "nice number" auto-ticks on a numeric/timestamp
  // domain can land a tick right next to dataMax, producing two ticks that
  // format to the same calendar day (e.g. "Jul 20" shown twice).
  const xTicks = useMemo(() => {
    if (chartData.length === 0) return undefined;
    const xs = chartData.map((d) => d.x);
    const min = Math.min(...xs);
    const max = Math.max(...xs);
    if (min === max) return [min];
    const count = 5;
    const raw = Array.from({ length: count }, (_, i) => min + ((max - min) * i) / (count - 1));
    const seenDays = new Set<string>();
    const deduped: number[] = [];
    for (const t of raw) {
      const dayKey = new Date(t).toDateString();
      if (seenDays.has(dayKey)) continue;
      seenDays.add(dayKey);
      deduped.push(t);
    }
    return deduped;
  }, [chartData]);

  const grouped = useMemo(() => {
    if (!scans) return [];
    const groups = new Map<string, ScanResult[]>();
    for (const s of scans) {
      const day = new Date(s.created_at).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
      if (!groups.has(day)) groups.set(day, []);
      groups.get(day)!.push(s);
    }
    return Array.from(groups.entries());
  }, [scans]);

  return (
    <PageShell
      title="Vulnerability Timeline"
      subtitle="Every scan, chronologically — hover or click a point for detail"
      actions={
        <select value={project} onChange={(e) => setProject(e.target.value)} className="bg-(--surface-2) border border-(--border-hairline) rounded-lg px-3 py-2 text-xs focus-ring outline-none">
          <option value="">All Projects</option>
          {projects.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      }
    >
      {!scans ? <Spinner label="Loading timeline..." /> : scans.length === 0 ? (
        <EmptyState icon={Clock} title="No scans yet" description="Run a scan to start building the vulnerability timeline." />
      ) : (
        <>
          <ChartCard title="Risk Over Time" subtitle="Each point is one scan — click to open its analysis" className="mb-5">
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ left: -10, right: 20, top: 10 }}>
                <CartesianGrid stroke="var(--gridline)" />
                <XAxis
                  dataKey="x" type="number" domain={["dataMin", "dataMax"]} ticks={xTicks}
                  tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false}
                />
                <YAxis dataKey="y" domain={[0, 100]} unit="%" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <ZAxis range={[60, 60]} />
                <RTooltip
                  {...chartTooltipStyle}
                  cursor={{ strokeDasharray: "3 3", stroke: "var(--baseline)" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload;
                    return (
                      <div style={chartTooltipStyle.contentStyle}>
                        <div className="font-semibold mono">{p.filename}</div>
                        <div>{p.verdict} &middot; {p.risk}</div>
                        <div>{p.y.toFixed(1)}% probability</div>
                        <div className="text-(--text-muted)">{new Date(p.x).toLocaleString()}</div>
                      </div>
                    );
                  }}
                />
                <Scatter data={chartData} onClick={(p: any) => navigate(`/analysis?scan=${p.id}`)} cursor="pointer">
                  {chartData.map((d, i) => <Cell key={i} fill={RISK_HEX[d.risk] ?? "#898781"} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </ChartCard>

          <div className="space-y-6">
            {grouped.map(([day, items]) => (
              <div key={day}>
                <div className="text-xs font-semibold uppercase tracking-wider text-(--text-muted) mb-2">{day}</div>
                <div className="relative pl-6 border-l-2 border-(--border-hairline) space-y-3">
                  {items.map((s) => (
                    <Link
                      key={s.id}
                      to={`/analysis?scan=${s.id}`}
                      className="relative block card card-hover p-3.5"
                    >
                      <span
                        className="absolute -left-[29px] top-4 w-3 h-3 rounded-full border-2 border-(--surface-0)"
                        style={{ background: RISK_HEX[s.risk_level] ?? "#898781" }}
                      />
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileCode2 size={14} className="text-(--text-muted) shrink-0" />
                          <span className="text-sm font-medium mono truncate">{s.filename}</span>
                          <span className="text-xs text-(--text-muted) shrink-0">{s.project_name}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-xs text-(--text-muted) tabular">{new Date(s.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
                          <RiskBadge level={s.risk_level} size="sm" />
                          <VerdictPill verdict={s.verdict} />
                          <span className="text-xs tabular text-(--text-muted) w-12 text-right">{s.confidence.toFixed(0)}%</span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </PageShell>
  );
}
