import { describe, it, expect } from "vitest";
import { RISK_ORDER, RISK_HEX, RISK_COLORS, severityColor, severityLabel, timeAgo } from "./risk";

describe("risk level tables", () => {
  it("every risk level in RISK_ORDER has a hex color and a CSS color", () => {
    for (const level of RISK_ORDER) {
      expect(RISK_HEX[level]).toBeTruthy();
      expect(RISK_COLORS[level]).toBeTruthy();
    }
  });

  it("RISK_ORDER is exactly the 5 platform-wide risk levels, in ascending severity", () => {
    expect(RISK_ORDER).toEqual(["SAFE", "LOW RISK", "MEDIUM RISK", "HIGH RISK", "CRITICAL"]);
  });
});

describe("severityColor / severityLabel", () => {
  it("maps every severity 0-4 to a distinct label", () => {
    const labels = [0, 1, 2, 3, 4].map(severityLabel);
    expect(labels).toEqual(["Clean", "Low", "Medium", "High", "Critical"]);
    expect(new Set(labels).size).toBe(5);
  });

  it("returns the fallback color for an out-of-range severity", () => {
    expect(severityColor(99)).toBe("#2c2c2a");
  });
});

describe("timeAgo", () => {
  it("reports a just-created timestamp as 'just now'", () => {
    expect(timeAgo(new Date().toISOString())).toBe("just now");
  });

  it("reports a timestamp from 90 minutes ago in hours", () => {
    const ninetyMinAgo = new Date(Date.now() - 90 * 60 * 1000).toISOString();
    expect(timeAgo(ninetyMinAgo)).toBe("1h ago");
  });

  it("reports a timestamp from 3 days ago in days", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(threeDaysAgo)).toBe("3d ago");
  });
});
