import { useSearchParams } from "react-router-dom";
import { FlaskConical, Scale, Lightbulb, Layers3 } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Research from "../Research";
import ModelComparison from "../ModelComparison";
import Explainability from "../Explainability";
import Architecture3D from "../Architecture3D";

const TABS: ModuleTabDef[] = [
  { id: "research", label: "Research", icon: FlaskConical },
  { id: "comparison", label: "Model Comparison", icon: Scale },
  { id: "explainability", label: "Explainability", icon: Lightbulb },
  { id: "architecture", label: "Architecture 3D", icon: Layers3 },
];

export default function AIEngineHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "research";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="AI Engine" subtitle="Model architecture, evaluation curves, feature importance, and cross-model comparison">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "research" && <Research />}
        {tab === "comparison" && <ModelComparison />}
        {tab === "explainability" && <Explainability />}
        {tab === "architecture" && <Architecture3D />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
