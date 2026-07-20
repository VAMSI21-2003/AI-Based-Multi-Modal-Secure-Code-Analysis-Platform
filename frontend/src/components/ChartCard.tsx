export default function ChartCard({
  title, subtitle, actions, children, className = "",
}: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-sm font-semibold text-(--text-primary)">{title}</div>
          {subtitle && <div className="text-xs text-(--text-muted) mt-0.5">{subtitle}</div>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}

export const chartTooltipStyle = {
  contentStyle: {
    background: "#1a1a1f",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 10,
    fontSize: 12,
    padding: "8px 12px",
    boxShadow: "0 10px 30px -10px rgba(0,0,0,0.6)",
  },
  labelStyle: { color: "#c3c2b7", marginBottom: 4, fontWeight: 600 },
  itemStyle: { color: "#ffffff" },
};
