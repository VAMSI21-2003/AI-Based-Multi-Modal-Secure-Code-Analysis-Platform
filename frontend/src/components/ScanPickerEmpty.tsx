import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ScanLine, ArrowUpRight, FileCode2 } from "lucide-react";
import { getHistory } from "../api/client";
import RiskBadge from "./RiskBadge";
import type { LucideIcon } from "lucide-react";

export default function ScanPickerEmpty({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  const [recent, setRecent] = useState<any[]>([]);

  useEffect(() => {
    getHistory({ limit: 6 }).then((d) => setRecent(d.results)).catch(() => {});
  }, []);

  return (
    <div className="card border-dashed p-10 flex flex-col items-center text-center">
      <div className="w-14 h-14 rounded-full bg-(--surface-3) flex items-center justify-center mb-4 text-(--text-muted)">
        <Icon size={24} />
      </div>
      <div className="text-sm font-semibold">{title}</div>
      <div className="text-xs text-(--text-muted) mt-1.5 max-w-sm">{description}</div>
      <Link to="/scanner" className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 transition">
        <ScanLine size={15} /> Run a New Scan
      </Link>

      {recent.length > 0 && (
        <div className="w-full max-w-md mt-8 text-left">
          <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium mb-2">Or pick a recent scan</div>
          <div className="space-y-1.5">
            {recent.map((r) => (
              <Link
                key={r.id}
                to={`?scan=${r.id}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) transition-colors text-xs"
              >
                <span className="flex items-center gap-2 mono truncate">
                  <FileCode2 size={12} className="text-(--text-muted) shrink-0" /> {r.filename}
                </span>
                <span className="flex items-center gap-2 shrink-0 ml-2">
                  <RiskBadge level={r.risk_level} size="sm" />
                  <ArrowUpRight size={12} className="text-(--text-muted)" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
