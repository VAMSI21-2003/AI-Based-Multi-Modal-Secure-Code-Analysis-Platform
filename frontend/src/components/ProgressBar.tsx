import { motion } from "framer-motion";

export default function ProgressBar({
  value, color = "var(--accent)", label, height = 8,
}: { value: number; color?: string; label?: string; height?: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs text-(--text-secondary) mb-1.5">
          <span>{label}</span>
          <span className="tabular font-semibold text-(--text-primary)">{clamped.toFixed(1)}%</span>
        </div>
      )}
      <div className="w-full rounded-full bg-(--surface-3) overflow-hidden" style={{ height }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: color, boxShadow: `0 0 12px ${color}66` }}
        />
      </div>
    </div>
  );
}
