// =============================================================================
// Dashboard.test.tsx -- real component smoke tests (Phase 3: testing
// foundation). Mocks only the network boundary (api/client's
// getDashboardStats) -- the actual Dashboard component, PageShell, StatCard,
// and chart components all render for real. Verifies:
//   1. The dashboard shows the loading state, then the REAL fetched numbers
//      (not some hardcoded/mock value baked into the component).
//   2. An API failure renders a visible error message, not a silent blank
//      page or fabricated data standing in for a failed request.
// =============================================================================

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import type { DashboardStats } from "../api/client";

vi.mock("../api/client", () => ({
  getDashboardStats: vi.fn(),
}));

import { getDashboardStats } from "../api/client";

const STATS: DashboardStats = {
  total_files_scanned: 42,
  total_vulnerabilities: 17,
  safe_count: 25,
  risk_distribution: { CRITICAL: 2, "HIGH RISK": 5, "MEDIUM RISK": 6, "LOW RISK": 4, SAFE: 25 },
  most_common_vulnerability: "Buffer Overflow",
  average_risk_percent: 38.5,
  average_confidence_percent: 71.2,
  recent_scans: [],
  trend_14d: [],
  models_status: { xgboost: { available: true, path: "models/xgboost.json" } },
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("Dashboard", () => {
  it("renders the real fetched stats, not fabricated data", async () => {
    vi.mocked(getDashboardStats).mockResolvedValueOnce(STATS);
    renderDashboard();

    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("17")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("shows a visible error message when the API call fails, instead of fake data", async () => {
    vi.mocked(getDashboardStats).mockRejectedValueOnce(new Error("network down"));
    renderDashboard();

    await waitFor(() => expect(screen.getByText(/Failed to load dashboard/i)).toBeInTheDocument());
    expect(screen.getByText(/network down/i)).toBeInTheDocument();
    // No stat card should render fabricated numbers in place of the failed real data.
    expect(screen.queryByText("42")).not.toBeInTheDocument();
  });
});
