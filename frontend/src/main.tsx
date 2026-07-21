import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import ErrorBoundary from "./components/ErrorBoundary";
import { Spinner } from "./components/Loading";

// Every page is its own lazily-loaded chunk instead of one ~1.5MB bundle --
// each route's code (and its own heavy imports, e.g. recharts/@xyflow/react
// on graph-heavy pages) only downloads when that route is actually visited.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Scanner = lazy(() => import("./pages/Scanner"));
const Analysis = lazy(() => import("./pages/Analysis"));
const CodeExplanation = lazy(() => import("./pages/CodeExplanation"));
const Heatmap = lazy(() => import("./pages/Heatmap"));
const Explainability = lazy(() => import("./pages/Explainability"));
const Reports = lazy(() => import("./pages/Reports"));
const KnowledgeBase = lazy(() => import("./pages/KnowledgeBase"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Analytics = lazy(() => import("./pages/Analytics"));
const HistoryPage = lazy(() => import("./pages/History"));
const SystemMonitor = lazy(() => import("./pages/SystemMonitor"));
const ModelComparison = lazy(() => import("./pages/ModelComparison"));
const ProjectScanner = lazy(() => import("./pages/ProjectScanner"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Research = lazy(() => import("./pages/Research"));
const Landing = lazy(() => import("./pages/Landing"));
const CommandCenter = lazy(() => import("./pages/CommandCenter"));
const AttackGraph = lazy(() => import("./pages/AttackGraph"));
const Copilot = lazy(() => import("./pages/Copilot"));
const CodeDiff = lazy(() => import("./pages/CodeDiff"));
const AutoPatch = lazy(() => import("./pages/AutoPatch"));
const Simulator = lazy(() => import("./pages/Simulator"));
const FileExplorer = lazy(() => import("./pages/FileExplorer"));
const ExecutionFlow = lazy(() => import("./pages/ExecutionFlow"));
const MemoryVisualizer = lazy(() => import("./pages/MemoryVisualizer"));
const AdvancedAnalysis = lazy(() => import("./pages/AdvancedAnalysis"));
const ExportCenter = lazy(() => import("./pages/ExportCenter"));
const SecurityDashboard = lazy(() => import("./pages/SecurityDashboard"));
const Presentation = lazy(() => import("./pages/Presentation"));
const DependencyGraphPage = lazy(() => import("./pages/DependencyGraph"));
const WatchMode = lazy(() => import("./pages/WatchMode"));
const GitHubMode = lazy(() => import("./pages/GitHubMode"));
const Gamification = lazy(() => import("./pages/Gamification"));
const VulnSearch = lazy(() => import("./pages/VulnSearch"));
const Architecture3D = lazy(() => import("./pages/Architecture3D"));
const CallGraphExplorer = lazy(() => import("./pages/CallGraphExplorer"));
const LiveIDE = lazy(() => import("./pages/LiveIDE"));
const KnowledgeGraph = lazy(() => import("./pages/KnowledgeGraph"));
const ScanCenterHub = lazy(() => import("./pages/hubs/ScanCenterHub"));
const ProgramAnalysisHub = lazy(() => import("./pages/hubs/ProgramAnalysisHub"));
const AIAssistantHub = lazy(() => import("./pages/hubs/AIAssistantHub"));
const AIEngineHub = lazy(() => import("./pages/hubs/AIEngineHub"));
const AnalyticsHub = lazy(() => import("./pages/hubs/AnalyticsHub"));
const ReportingHub = lazy(() => import("./pages/hubs/ReportingHub"));
const PlatformHub = lazy(() => import("./pages/hubs/PlatformHub"));
const Scorecard = lazy(() => import("./pages/Scorecard"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteFallback() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Spinner label="Loading page..." />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
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
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
