export function computeGrade(safetyScore: number): { grade: string; color: string } {
  if (safetyScore >= 90) return { grade: "A", color: "var(--status-good)" };
  if (safetyScore >= 80) return { grade: "B", color: "var(--status-good)" };
  if (safetyScore >= 70) return { grade: "C", color: "var(--status-warning)" };
  if (safetyScore >= 60) return { grade: "D", color: "var(--status-serious)" };
  return { grade: "F", color: "var(--status-critical)" };
}
