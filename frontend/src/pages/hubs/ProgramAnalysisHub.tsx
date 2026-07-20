import { useSearchParams } from "react-router-dom";
import { Brain, BrainCircuit, Flame, Network, Waypoints, Workflow, MemoryStick, GitBranch, SearchCode, Share2, Boxes } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Analysis from "../Analysis";
import CodeExplanation from "../CodeExplanation";
import Heatmap from "../Heatmap";
import AttackGraph from "../AttackGraph";
import CallGraphExplorer from "../CallGraphExplorer";
import ExecutionFlow from "../ExecutionFlow";
import MemoryVisualizer from "../MemoryVisualizer";
import DependencyGraphPage from "../DependencyGraph";
import AdvancedAnalysis from "../AdvancedAnalysis";
import KnowledgeGraph from "../KnowledgeGraph";
import Simulator from "../Simulator";

// Phase 6 (UX consolidation): this hub is "Analysis Center" -- every view
// that analyzes a scan or a project, from the AI verdict itself down to
// attack paths, call graphs, control flow, memory, and cross-file data
// flow. AI Analysis and Code Explanation moved here from the AI Assistant
// hub (which is now focused purely on interactive guidance: Copilot,
// Knowledge Base, Recommendations, Auto Patch, Code Diff) -- same
// components, unmodified, just re-homed to the hub that matches their
// actual purpose.
const TABS: ModuleTabDef[] = [
  { id: "analysis", label: "AI Analysis", icon: Brain },
  { id: "explanation", label: "Code Explanation", icon: BrainCircuit },
  { id: "heatmap", label: "Vulnerability Heatmap", icon: Flame },
  { id: "attack-graph", label: "Attack Graph", icon: Network },
  { id: "call-graph", label: "Call Graph", icon: Waypoints },
  { id: "cfg", label: "Execution Flow (CFG)", icon: Workflow },
  { id: "memory", label: "Memory Visualizer", icon: MemoryStick },
  { id: "data-flow", label: "Data Flow", icon: GitBranch },
  { id: "static-analysis", label: "Advanced Static Analysis", icon: SearchCode },
  { id: "knowledge-graph", label: "Knowledge Graph", icon: Share2 },
  { id: "simulator", label: "Exploit Simulator", icon: Boxes },
];

export default function ProgramAnalysisHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "analysis";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="Analysis Center" subtitle="AI verdicts, structural breakdowns, attack paths, call graphs, control flow, memory, and data flow — for a single scan or a whole project">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "analysis" && <Analysis />}
        {tab === "explanation" && <CodeExplanation />}
        {tab === "heatmap" && <Heatmap />}
        {tab === "attack-graph" && <AttackGraph />}
        {tab === "call-graph" && <CallGraphExplorer />}
        {tab === "cfg" && <ExecutionFlow />}
        {tab === "memory" && <MemoryVisualizer />}
        {tab === "data-flow" && <DependencyGraphPage />}
        {tab === "static-analysis" && <AdvancedAnalysis />}
        {tab === "knowledge-graph" && <KnowledgeGraph />}
        {tab === "simulator" && <Simulator />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
