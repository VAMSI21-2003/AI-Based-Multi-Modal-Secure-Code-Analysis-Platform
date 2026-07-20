import { Activity } from "lucide-react";

export default function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div
      className="sticky top-0 z-10 flex items-center justify-between px-8 h-16 border-b border-(--border-hairline) bg-(--surface-0)/75 backdrop-blur-xl relative"
    >
      <div
        className="absolute bottom-0 left-0 right-0 h-px pointer-events-none"
        style={{ background: "linear-gradient(90deg, transparent, rgba(57,135,229,0.35), transparent)" }}
      />
      <div className="fade-in-up">
        <h1 className="text-[17px] font-semibold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-(--text-muted) mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-(--surface-2) border border-(--border-hairline) text-xs text-(--text-secondary) shadow-[0_0_16px_-6px_var(--accent-glow)]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-(--status-good) opacity-60" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-(--status-good)" />
        </span>
        Engine Online
        <Activity size={13} className="text-(--text-muted)" />
      </div>
    </div>
  );
}
