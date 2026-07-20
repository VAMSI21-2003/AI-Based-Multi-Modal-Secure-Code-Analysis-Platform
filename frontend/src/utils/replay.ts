import { SCENARIOS } from "../data/simulatorScenarios";

// Maps a line-risk finding's CWE to one of Vulnerability Simulator's real
// scenario ids -- CWEs with no matching animated walkthrough (integer
// overflow, format string, command injection) are simply omitted, not
// guessed at. Shared by every "Findings" surface (Heatmap, Live IDE) so a
// CWE always replays the same scenario everywhere.
const CWE_TO_SCENARIO: Record<string, string> = {
  "CWE-120": "buffer-overflow", "CWE-242": "buffer-overflow", "CWE-125": "buffer-overflow", "CWE-170": "buffer-overflow",
  "CWE-416": "use-after-free", "CWE-476": "null-deref", "CWE-770": "memory-leak",
};

export function replayScenarioFor(cwe: string): string | null {
  const id = CWE_TO_SCENARIO[cwe];
  return id && SCENARIOS.some((s) => s.id === id) ? id : null;
}

export function replayUrl(cwe: string): string | null {
  const scenario = replayScenarioFor(cwe);
  return scenario ? `/program-analysis?tab=simulator&scenario=${scenario}&autoplay=1` : null;
}
