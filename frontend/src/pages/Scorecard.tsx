import { useEffect, useState } from "react";
import { Award, ShieldAlert, Skull, Sparkles, MemoryStick, TrendingUp } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import { getScorecard, type Scorecard as ScorecardType } from "../api/client";

const GRADE_COLOR: Record<string, string> = {
  A: "var(--status-good)", B: "#8bc34a", C: "var(--status-warning)", D: "var(--status-serious)", F: "var(--status-critical)", "N/A": "var(--text-muted)",
};

const FACTOR_ICON: Record<string, any> = {
  vulnerability_density: ShieldAlert, critical_exposure: Skull, code_quality: Sparkles, memory_safety: MemoryStick, remediation_trend: TrendingUp,
};

export default function Scorecard() {
  const [data, setData] = useState<ScorecardType | null>(null);

  useEffect(() => {
    let cancelled = false;
    getScorecard().then((d) => { if (!cancelled) setData(d); });
    return () => { cancelled = true; };
  }, []);

  if (!data) return <PageShell title="Security Scorecard" subtitle="One weighted, audit-style grade for the whole codebase"><Spinner label="Computing scorecard..." /></PageShell>;

  if (!data.available) {
    return (
      <PageShell title="Security Scorecard" subtitle="One weighted, audit-style grade for the whole codebase">
        <div className="card p-10 text-center">
          <Award size={32} className="mx-auto text-(--text-muted) mb-3" />
          <div className="text-sm font-semibold">No scans yet</div>
          <div className="text-xs text-(--text-muted) mt-1">Run a scan to compute the scorecard — every factor is derived from real scan history.</div>
        </div>
      </PageShell>
    );
  }

  const gradeColor = GRADE_COLOR[data.grade] ?? "var(--accent)";

  return (
    <PageShell title="Security Scorecard" subtitle="A weighted, audit-style grade — the way a ratings vendor presents portfolio risk to an executive">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
        <div className="card p-6 flex flex-col items-center justify-center text-center" style={{ boxShadow: `0 0 50px -16px ${gradeColor}` }}>
          <div className="w-24 h-24 rounded-full flex items-center justify-center mb-3 border-2" style={{ borderColor: gradeColor, background: `${gradeColor}1a` }}>
            <span className="text-4xl font-bold" style={{ color: gradeColor }}>{data.grade}</span>
          </div>
          <div className="text-sm font-semibold">Overall Grade</div>
          <div className="text-xs text-(--text-muted) mt-1 tabular">{data.overall_score.toFixed(1)} / 100</div>
        </div>
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <div className="card p-4">
            <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">Scans Evaluated</div>
            <div className="text-2xl font-bold tabular mt-1">{data.total_scans}</div>
          </div>
          <div className="card p-4">
            <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">Vulnerable Files</div>
            <div className="text-2xl font-bold tabular mt-1 text-(--status-critical)">{data.vulnerable_files}</div>
          </div>
          <div className="card p-4 col-span-2">
            <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">Critical Files</div>
            <div className="text-2xl font-bold tabular mt-1" style={{ color: (data.critical_files ?? 0) > 0 ? "var(--status-critical)" : "var(--status-good)" }}>{data.critical_files}</div>
          </div>
        </div>
      </div>

      <ChartCard title="Factor Breakdown" subtitle="Each factor computed independently from real scan data, then weighted into the overall grade">
        <div className="space-y-3">
          {data.factors.map((f) => {
            const Icon = FACTOR_ICON[f.id] ?? Award;
            const color = GRADE_COLOR[f.grade] ?? "var(--accent)";
            return (
              <div key={f.id} className="flex items-center gap-4">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}1f` }}>
                  <Icon size={16} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{f.label}</span>
                    <span className="text-xs text-(--text-muted)">weight {(f.weight * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-(--surface-3) overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${f.score}%`, background: color }} />
                  </div>
                </div>
                <div className="w-16 text-right shrink-0">
                  <span className="text-sm font-bold tabular" style={{ color }}>{f.grade}</span>
                  <div className="text-[10px] text-(--text-muted) tabular">{f.score.toFixed(1)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </ChartCard>
    </PageShell>
  );
}
