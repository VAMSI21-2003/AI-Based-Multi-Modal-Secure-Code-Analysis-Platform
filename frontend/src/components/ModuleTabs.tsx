import clsx from "clsx";

export interface ModuleTabDef { id: string; label: string; icon: any; }

export default function ModuleTabs({ tabs, active, onChange }: { tabs: ModuleTabDef[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-(--border-hairline) pb-0 mb-6 -mt-1">
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={clsx(
              "flex items-center gap-1.5 px-3.5 py-2.5 text-[13px] font-medium border-b-2 -mb-px transition-colors",
              isActive
                ? "text-(--text-primary) border-(--accent)"
                : "text-(--text-muted) border-transparent hover:text-(--text-secondary) hover:border-(--border-hairline-strong)"
            )}
          >
            <t.icon size={14} className={isActive ? "text-(--accent)" : ""} />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
