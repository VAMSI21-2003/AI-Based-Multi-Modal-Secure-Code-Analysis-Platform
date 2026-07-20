import { motion } from "framer-motion";

interface Props {
  value: number;      // 0-100
  color?: string;
  label?: string;
  size?: number;
}

export default function Gauge({ value, color = "var(--accent)", label, size = 160 }: Props) {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = size / 2 - 12;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference * (1 - clamped / 100);
  const cx = size / 2;
  const cy = size / 2;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 16} viewBox={`0 0 ${size} ${size / 2 + 16}`}>
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={12}
          strokeLinecap="round"
        />
        <motion.path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={12}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        <text x={cx} y={cy - 6} textAnchor="middle" fontSize={size * 0.19} fontWeight={800} fill="var(--text-primary)" className="tabular">
          {clamped.toFixed(0)}%
        </text>
      </svg>
      {label && <div className="text-xs text-(--text-muted) mt-1 uppercase tracking-wider">{label}</div>}
    </div>
  );
}
