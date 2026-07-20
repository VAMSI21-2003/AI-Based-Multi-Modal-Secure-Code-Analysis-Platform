import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ReferenceLine, Cell } from "recharts";
import { chartTooltipStyle } from "./ChartCard";

interface Contribution { feature: string; value: number; contribution: number; direction: string; }

export default function ContributionBars({ contributions }: { contributions: Contribution[] }) {
  const data = [...contributions].sort((a, b) => a.contribution - b.contribution).map((c) => ({
    ...c,
    name: c.feature.startsWith("embed_") ? `emb[${c.feature.split("_")[1]}]` : c.feature,
  }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 26)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20 }}>
          <CartesianGrid stroke="var(--gridline)" horizontal={false} />
          <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
          <YAxis type="category" dataKey="name" width={90} tick={{ fill: "var(--text-secondary)", fontSize: 11 }} axisLine={false} tickLine={false} className="mono" />
          <ReferenceLine x={0} stroke="var(--baseline)" />
          <RTooltip {...chartTooltipStyle} formatter={(v: any, _n: any, item: any) => [
            `${Number(v).toFixed(4)} (value=${item.payload.value})`, item.payload.direction === "vulnerable" ? "Pushes toward Vulnerable" : "Pushes toward Safe",
          ]} />
          <Bar dataKey="contribution" radius={4}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.direction === "vulnerable" ? "#d03b3b" : "#0ca30c"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="text-[10px] text-(--text-muted) text-center -mt-2">
        Approximate contribution = global feature importance &times; how unusual this value is vs. the training set. Not a SHAP value.
      </div>
    </div>
  );
}
