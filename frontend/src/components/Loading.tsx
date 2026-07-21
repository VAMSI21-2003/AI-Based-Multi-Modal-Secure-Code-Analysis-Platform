import { ShieldCheck } from "lucide-react";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-(--text-muted)">
      <div className="relative w-12 h-12 flex items-center justify-center">
        <span className="absolute inset-0 rounded-full border-2 border-(--accent)/25" />
        <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-(--accent) animate-spin" />
        <ShieldCheck size={18} className="text-(--accent) animate-pulse-soft" />
      </div>
      {label && <div className="text-sm text-(--text-secondary)">{label}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-lg ${className}`} />;
}

export function CardSkeleton() {
  return (
    <div className="card p-5">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-8 w-16" />
    </div>
  );
}

export function EmptyState({ icon: Icon, title, description, action }: {
  icon: React.ElementType; title: string; description?: string; action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 card border-dashed">
      <div className="w-14 h-14 rounded-full bg-(--surface-3) flex items-center justify-center mb-4 text-(--text-muted)">
        <Icon size={24} />
      </div>
      <div className="text-sm font-semibold text-(--text-primary)">{title}</div>
      {description && <div className="text-xs text-(--text-muted) mt-1.5 max-w-sm">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
