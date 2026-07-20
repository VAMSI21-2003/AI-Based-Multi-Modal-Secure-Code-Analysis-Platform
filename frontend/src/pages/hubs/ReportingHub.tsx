import { useSearchParams } from "react-router-dom";
import { FileText, Download } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Reports from "../Reports";
import ExportCenter from "../ExportCenter";

const TABS: ModuleTabDef[] = [
  { id: "reports", label: "Security Reports", icon: FileText },
  { id: "export-center", label: "Export Center", icon: Download },
];

export default function ReportingHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "reports";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="Reports" subtitle="Browse generated reports and export in every supported format">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "reports" && <Reports />}
        {tab === "export-center" && <ExportCenter />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
