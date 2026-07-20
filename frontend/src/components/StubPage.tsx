import PageShell from "./PageShell";
import { EmptyState } from "./Loading";
import type { LucideIcon } from "lucide-react";

export default function StubPage({
  title, subtitle, icon, description,
}: { title: string; subtitle: string; icon: LucideIcon; description: string }) {
  return (
    <PageShell title={title} subtitle={subtitle}>
      <EmptyState icon={icon} title="Module under construction" description={description} />
    </PageShell>
  );
}
