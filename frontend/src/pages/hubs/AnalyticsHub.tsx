import { useSearchParams } from "react-router-dom";
import { LayoutDashboard, Clock, History as HistoryIcon, ShieldHalf, BarChart3, ScanSearch, Trophy, Award } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Dashboard from "../Dashboard";
import Timeline from "../Timeline";
import HistoryPage from "../History";
import SecurityDashboard from "../SecurityDashboard";
import Analytics from "../Analytics";
import VulnSearch from "../VulnSearch";
import Gamification from "../Gamification";
import Scorecard from "../Scorecard";

// Phase 6 (UX consolidation): "Risk Map" (Heatmap.tsx) moved to Analysis
// Center -- it's a per-scan line-level view, not a project-wide analytics
// view, so it belongs with the rest of the per-scan analysis tools rather
// than duplicated here too.
const TABS: ModuleTabDef[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "scorecard", label: "Scorecard", icon: Award },
  { id: "timeline", label: "Timeline", icon: Clock },
  { id: "history", label: "History", icon: HistoryIcon },
  { id: "security-dashboard", label: "Security Dashboard", icon: ShieldHalf },
  { id: "project-analytics", label: "Project Statistics", icon: BarChart3 },
  { id: "search", label: "Vulnerability Search", icon: ScanSearch },
  { id: "gamification", label: "Gamification", icon: Trophy },
];

export default function AnalyticsHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "dashboard";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="Analytics" subtitle="Live posture, scorecard, historical trend, project statistics, search, and achievements" glow>
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "dashboard" && <Dashboard />}
        {tab === "scorecard" && <Scorecard />}
        {tab === "timeline" && <Timeline />}
        {tab === "history" && <HistoryPage />}
        {tab === "security-dashboard" && <SecurityDashboard />}
        {tab === "project-analytics" && <Analytics />}
        {tab === "search" && <VulnSearch />}
        {tab === "gamification" && <Gamification />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
