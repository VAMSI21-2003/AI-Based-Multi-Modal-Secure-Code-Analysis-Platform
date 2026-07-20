import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip as RTooltip, Cell } from "recharts";
import { chartTooltipStyle } from "./ChartCard";

interface Props {
  background: { x: number; y: number; label: number | null }[];
  current: { x: number; y: number } | null;
  explainedVariance?: number[];
}

export default function EmbeddingScatter({ background, current, explainedVariance }: Props) {
  const safePoints = background.filter((p) => p.label === 0);
  const vulnPoints = background.filter((p) => p.label === 1);

  return (
    <div>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ left: -10, right: 20, top: 10, bottom: 0 }}>
          <CartesianGrid stroke="var(--gridline)" />
          <XAxis type="number" dataKey="x" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} name="PC1" />
          <YAxis type="number" dataKey="y" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} name="PC2" />
          <ZAxis range={[14, 14]} />
          <RTooltip {...chartTooltipStyle} cursor={{ strokeDasharray: "3 3", stroke: "var(--baseline)" }} />
          <Scatter data={safePoints} fill="#0ca30c" fillOpacity={0.35} name="Training set: Safe" />
          <Scatter data={vulnPoints} fill="#d03b3b" fillOpacity={0.35} name="Training set: Vulnerable" />
          {current && (
            <Scatter data={[current]} name="This function" shape="star">
              <Cell fill="#3987e5" stroke="#ffffff" strokeWidth={1.5} />
            </Scatter>
          )}
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 text-[11px] text-(--text-muted) -mt-2">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#0ca30c]" /> Training: Safe</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#d03b3b]" /> Training: Vulnerable</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-(--accent)" /> This function</span>
      </div>
      {explainedVariance && (
        <div className="text-center text-[10px] text-(--text-muted) mt-1">
          PC1 explains {(explainedVariance[0] * 100).toFixed(1)}% of variance, PC2 explains {(explainedVariance[1] * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
