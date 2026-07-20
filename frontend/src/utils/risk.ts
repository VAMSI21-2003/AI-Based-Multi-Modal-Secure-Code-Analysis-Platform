export const RISK_ORDER = ["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"];

export const RISK_COLORS: Record<string, string> = {
  SAFE: "var(--status-good)",
  "LOW RISK": "var(--status-low)",
  "MEDIUM RISK": "var(--status-warning)",
  "HIGH RISK": "var(--status-serious)",
  CRITICAL: "var(--status-critical)",
};

export const RISK_HEX: Record<string, string> = {
  SAFE: "#0ca30c",
  "LOW RISK": "#199e70",
  "MEDIUM RISK": "#fab219",
  "HIGH RISK": "#ec835a",
  CRITICAL: "#d03b3b",
};

export function severityColor(sev: number): string {
  // 0 clean .. 4 critical
  return ["#2c2c2a", "#199e70", "#fab219", "#ec835a", "#d03b3b"][sev] ?? "#2c2c2a";
}

export function severityLabel(sev: number): string {
  return ["Clean", "Low", "Medium", "High", "Critical"][sev] ?? "Clean";
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}
