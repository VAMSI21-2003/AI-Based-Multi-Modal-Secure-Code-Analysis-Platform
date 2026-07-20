import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip as RTooltip, Legend } from "recharts";
import { chartTooltipStyle } from "./ChartCard";
import { RISK_HEX, RISK_ORDER } from "../utils/risk";

interface Props {
  data: Record<string, number>;
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  legendLayout?: "vertical" | "horizontal";
  emptyLabel?: string;
}

/**
 * Shared risk-distribution donut, used by both Dashboard and Command Center
 * (previously two independent copies of the same Recharts config) — a
 * single source of truth so the two homepages' charts can't drift.
 */
export default function RiskDistributionChart({
  data, height = 240, innerRadius = 55, outerRadius = 88, legendLayout = "horizontal", emptyLabel = "No scans yet",
}: Props) {
  const entries = RISK_ORDER.filter((k) => data[k]).map((k) => ({ name: k, value: data[k] }));

  if (entries.length === 0) {
    return <div style={{ height }} className="flex items-center justify-center text-sm text-(--text-muted)">{emptyLabel}</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={entries} dataKey="value" nameKey="name" innerRadius={innerRadius} outerRadius={outerRadius} paddingAngle={2} strokeWidth={2} stroke="var(--surface-2)">
          {entries.map((d) => <Cell key={d.name} fill={RISK_HEX[d.name] ?? "#898781"} />)}
        </Pie>
        <RTooltip {...chartTooltipStyle} />
        {legendLayout === "vertical" ? (
          <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }} />
        ) : (
          <Legend wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }} />
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}
