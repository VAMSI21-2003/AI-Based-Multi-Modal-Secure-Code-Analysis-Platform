import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { useCountUp } from "../hooks/useCountUp";

interface Props {
  label: string;
  value: number;
  suffix?: string;
  decimals?: number;
  icon: LucideIcon;
  accent?: string;
  delay?: number;
  trend?: { value: number; positive: boolean } | null;
}

export default function StatCard({ label, value, suffix = "", decimals = 0, icon: Icon, accent = "var(--accent)", delay = 0, trend }: Props) {
  const animated = useCountUp(value);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      className="card card-hover group p-5 relative overflow-hidden"
    >
      <div
        className="absolute -top-8 -right-8 w-28 h-28 rounded-full opacity-20 group-hover:opacity-35 blur-2xl pointer-events-none transition-opacity duration-300"
        style={{ background: accent }}
      />
      <div className="flex items-start justify-between relative">
        <div>
          <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium">{label}</div>
          <div className="mt-2 text-3xl font-bold tabular text-(--text-primary)">
            {animated.toFixed(decimals)}
            <span className="text-lg text-(--text-secondary) ml-0.5">{suffix}</span>
          </div>
          {trend && (
            <div className={`mt-1.5 text-xs font-medium ${trend.positive ? "text-(--status-good)" : "text-(--status-critical)"}`}>
              {trend.positive ? "▲" : "▼"} {Math.abs(trend.value)}% vs last period
            </div>
          )}
        </div>
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-transform duration-300 group-hover:scale-110"
          style={{ background: `${accent}1f`, color: accent }}
        >
          <Icon size={20} strokeWidth={2} />
        </div>
      </div>
    </motion.div>
  );
}
