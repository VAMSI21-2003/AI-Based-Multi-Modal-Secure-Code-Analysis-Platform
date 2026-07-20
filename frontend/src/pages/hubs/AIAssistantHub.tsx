import { useSearchParams } from "react-router-dom";
import { Bot, BookOpen, Wand2, Wrench, GitCompare } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Copilot from "../Copilot";
import KnowledgeBase from "../KnowledgeBase";
import Recommendations from "../Recommendations";
import AutoPatch from "../AutoPatch";
import CodeDiff from "../CodeDiff";

// Phase 6 (UX consolidation): focused purely on interactive guidance now --
// AI Analysis and Code Explanation moved to Analysis Center, where they sit
// alongside the rest of the per-scan/per-project analysis views.
const TABS: ModuleTabDef[] = [
  { id: "copilot", label: "Security Copilot", icon: Bot },
  { id: "knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { id: "recommendations", label: "Recommendations", icon: Wand2 },
  { id: "auto-patch", label: "Auto Patch", icon: Wrench },
  { id: "code-diff", label: "Code Diff", icon: GitCompare },
];

export default function AIAssistantHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "copilot";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="AI Assistant" subtitle="Deterministic Q&A, reference knowledge, guided recommendations, and automatic fixes">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "copilot" && <Copilot />}
        {tab === "knowledge-base" && <KnowledgeBase />}
        {tab === "recommendations" && <Recommendations />}
        {tab === "auto-patch" && <AutoPatch />}
        {tab === "code-diff" && <CodeDiff />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
