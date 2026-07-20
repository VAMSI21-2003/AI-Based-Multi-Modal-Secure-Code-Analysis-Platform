import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import ErrorBoundary from "./components/ErrorBoundary";

import Dashboard from "./pages/Dashboard";
import Scanner from "./pages/Scanner";
import Analysis from "./pages/Analysis";
import CodeExplanation from "./pages/CodeExplanation";
import Heatmap from "./pages/Heatmap";
import Explainability from "./pages/Explainability";
import Reports from "./pages/Reports";
import KnowledgeBase from "./pages/KnowledgeBase";
import Recommendations from "./pages/Recommendations";
import Analytics from "./pages/Analytics";
import HistoryPage from "./pages/History";
import SystemMonitor from "./pages/SystemMonitor";
import ModelComparison from "./pages/ModelComparison";
import ProjectScanner from "./pages/ProjectScanner";
import Timeline from "./pages/Timeline";
import Research from "./pages/Research";
import Landing from "./pages/Landing";
import CommandCenter from "./pages/CommandCenter";
import AttackGraph from "./pages/AttackGraph";
import Copilot from "./pages/Copilot";
import CodeDiff from "./pages/CodeDiff";
import AutoPatch from "./pages/AutoPatch";
import Simulator from "./pages/Simulator";
import FileExplorer from "./pages/FileExplorer";
import ExecutionFlow from "./pages/ExecutionFlow";
import MemoryVisualizer from "./pages/MemoryVisualizer";
import AdvancedAnalysis from "./pages/AdvancedAnalysis";
import ExportCenter from "./pages/ExportCenter";
import SecurityDashboard from "./pages/SecurityDashboard";
import Presentation from "./pages/Presentation";
import DependencyGraphPage from "./pages/DependencyGraph";
import WatchMode from "./pages/WatchMode";
import GitHubMode from "./pages/GitHubMode";
import Gamification from "./pages/Gamification";
import VulnSearch from "./pages/VulnSearch";
import Architecture3D from "./pages/Architecture3D";
import CallGraphExplorer from "./pages/CallGraphExplorer";
import LiveIDE from "./pages/LiveIDE";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import ScanCenterHub from "./pages/hubs/ScanCenterHub";
import ProgramAnalysisHub from "./pages/hubs/ProgramAnalysisHub";
import AIAssistantHub from "./pages/hubs/AIAssistantHub";
import AIEngineHub from "./pages/hubs/AIEngineHub";
import AnalyticsHub from "./pages/hubs/AnalyticsHub";
import ReportingHub from "./pages/hubs/ReportingHub";
import PlatformHub from "./pages/hubs/PlatformHub";
import Scorecard from "./pages/Scorecard";
import NotFound from "./pages/NotFound";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/welcome" element={<Landing />} />
          <Route path="/presentation" element={<Presentation />} />
          <Route element={<App />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/scanner" element={<Scanner />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/explanation" element={<CodeExplanation />} />
            <Route path="/heatmap" element={<Heatmap />} />
            <Route path="/explainability" element={<Explainability />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/knowledge-base" element={<KnowledgeBase />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/system" element={<SystemMonitor />} />
            <Route path="/comparison" element={<ModelComparison />} />
            <Route path="/project-scanner" element={<ProjectScanner />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/research" element={<Research />} />
            <Route path="/command-center" element={<CommandCenter />} />
            <Route path="/attack-graph" element={<AttackGraph />} />
            <Route path="/copilot" element={<Copilot />} />
            <Route path="/code-diff" element={<CodeDiff />} />
            <Route path="/auto-patch" element={<AutoPatch />} />
            <Route path="/simulator" element={<Simulator />} />
            <Route path="/file-explorer" element={<FileExplorer />} />
            <Route path="/execution-flow" element={<ExecutionFlow />} />
            <Route path="/memory-visualizer" element={<MemoryVisualizer />} />
            <Route path="/advanced-analysis" element={<AdvancedAnalysis />} />
            <Route path="/export-center" element={<ExportCenter />} />
            <Route path="/security-dashboard" element={<SecurityDashboard />} />
            <Route path="/dependency-graph" element={<DependencyGraphPage />} />
            <Route path="/watch-mode" element={<WatchMode />} />
            <Route path="/github-mode" element={<GitHubMode />} />
            <Route path="/gamification" element={<Gamification />} />
            <Route path="/vuln-search" element={<VulnSearch />} />
            <Route path="/architecture-3d" element={<Architecture3D />} />
            <Route path="/call-graph-explorer" element={<CallGraphExplorer />} />
            <Route path="/live-ide" element={<LiveIDE />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
            <Route path="/scan-center" element={<ScanCenterHub />} />
            <Route path="/program-analysis" element={<ProgramAnalysisHub />} />
            <Route path="/ai-assistant" element={<AIAssistantHub />} />
            <Route path="/ai-engine" element={<AIEngineHub />} />
            <Route path="/analytics-hub" element={<AnalyticsHub />} />
            <Route path="/reporting" element={<ReportingHub />} />
            <Route path="/platform-hub" element={<PlatformHub />} />
            <Route path="/scorecard" element={<Scorecard />} />
            <Route path="*" element={<NotFound />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
