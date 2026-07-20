import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Tooltip as RTooltip } from "recharts";
import { chartTooltipStyle } from "./ChartCard";

// Rough "typical" max values used only to normalise features onto a 0-100
// radar scale for visual comparison -- not a statistical claim.
const NORMALISERS: Record<string, number> = {
  n_pointer_ops: 15, n_loops: 8, n_if_statements: 15, n_function_calls: 15,
  max_depth: 20, nesting_depth: 8, loc: 100, pointer_count: 30, operator_count: 40,
};

interface Props {
  astFeatures: Record<string, number>;
  metricFeatures: Record<string, number>;
}

export default function FeatureRadar({ astFeatures, metricFeatures }: Props) {
  const keys = [
    ["Pointer Ops", astFeatures.n_pointer_ops, "n_pointer_ops"],
    ["Loops", astFeatures.n_loops, "n_loops"],
    ["Conditionals", astFeatures.n_if_statements, "n_if_statements"],
    ["Function Calls", astFeatures.n_function_calls, "n_function_calls"],
    ["AST Depth", astFeatures.max_depth, "max_depth"],
    ["Nesting", metricFeatures.nesting_depth, "nesting_depth"],
    ["Lines of Code", metricFeatures.loc, "loc"],
    ["Operators", metricFeatures.operator_count, "operator_count"],
  ] as [string, number, string][];

  const data = keys.map(([label, value, norm]) => ({
    metric: label,
    value: Math.min(100, Math.round(((value ?? 0) / NORMALISERS[norm]) * 100)),
    raw: value ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} outerRadius={95}>
        <PolarGrid stroke="var(--gridline)" />
        <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
        <Radar dataKey="value" stroke="#3987e5" fill="#3987e5" fillOpacity={0.32} strokeWidth={2} />
        <RTooltip {...chartTooltipStyle} formatter={(_: any, __: any, item: any) => [item.payload.raw, item.payload.metric]} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
