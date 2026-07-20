const RISK_STYLES: Record<string, { bg: string; fg: string; dot: string }> = {
  SAFE: { bg: "rgba(12,163,12,0.14)", fg: "#3ddc3d", dot: "var(--status-good)" },
  "LOW RISK": { bg: "rgba(25,158,112,0.14)", fg: "#3fd6a8", dot: "var(--status-low)" },
  "MEDIUM RISK": { bg: "rgba(250,178,25,0.14)", fg: "#fbc44d", dot: "var(--status-warning)" },
  "HIGH RISK": { bg: "rgba(236,131,90,0.16)", fg: "#f2a583", dot: "var(--status-serious)" },
  CRITICAL: { bg: "rgba(208,59,59,0.16)", fg: "#f27b7b", dot: "var(--status-critical)" },
};

export default function RiskBadge({ level, size = "md" }: { level: string; size?: "sm" | "md" }) {
  const style = RISK_STYLES[level] ?? RISK_STYLES.SAFE;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${
        size === "sm" ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"
      }`}
      style={{ background: style.bg, color: style.fg }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: style.dot }} />
      {level}
    </span>
  );
}

export function VerdictPill({ verdict }: { verdict: string }) {
  const vulnerable = verdict === "VULNERABLE";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold tracking-wide"
      style={{
        background: vulnerable ? "rgba(208,59,59,0.16)" : "rgba(12,163,12,0.14)",
        color: vulnerable ? "#f27b7b" : "#3ddc3d",
      }}
    >
      {verdict}
    </span>
  );
}
