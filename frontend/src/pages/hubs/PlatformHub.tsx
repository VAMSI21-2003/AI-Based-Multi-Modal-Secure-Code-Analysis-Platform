import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { Cpu, Container, Workflow, Plug, Settings as SettingsIcon, Copy, Check, ExternalLink } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import ChartCard from "../../components/ChartCard";
import { Spinner } from "../../components/Loading";
import SystemMonitor from "../SystemMonitor";
import { getPlatformFiles, type PlatformFile } from "../../api/client";
import { getDefaultModel, setDefaultModel, type ModelChoice } from "../../utils/settings";

const TABS: ModuleTabDef[] = [
  { id: "system", label: "System Monitor", icon: Cpu },
  { id: "docker", label: "Docker", icon: Container },
  { id: "cicd", label: "CI/CD", icon: Workflow },
  { id: "api", label: "REST API", icon: Plug },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

const BACKEND_URL = "http://127.0.0.1:8000";

export default function PlatformHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "system";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="Platform" subtitle="System telemetry, deployment, CI/CD, the REST API, and local preferences">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      {tab === "system" && (
        <EmbeddedContext.Provider value={true}><SystemMonitor /></EmbeddedContext.Provider>
      )}
      {tab === "docker" && <DockerTab />}
      {tab === "cicd" && <CiCdTab />}
      {tab === "api" && <RestApiTab />}
      {tab === "settings" && <SettingsTab />}
    </PageShell>
  );
}

function CodeBlock({ label, path, content }: { label: string; path: string; content: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      toast.success(`${label} copied`);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div className="rounded-lg border border-(--border-hairline) overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-(--surface-3) border-b border-(--border-hairline)">
        <span className="text-xs mono text-(--text-muted)">{path}</span>
        <button onClick={copy} className="flex items-center gap-1 text-[11px] text-(--text-muted) hover:text-(--text-primary) px-2 py-1 rounded hover:bg-(--surface-2)">
          {copied ? <Check size={12} className="text-(--status-good)" /> : <Copy size={12} />} {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="text-[11px] mono p-4 overflow-x-auto max-h-[360px] overflow-y-auto text-(--text-secondary) bg-(--surface-2)">{content}</pre>
    </div>
  );
}

function usePlatformFiles() {
  const [files, setFiles] = useState<Record<string, PlatformFile> | null>(null);
  useEffect(() => { getPlatformFiles().then(setFiles).catch(() => setFiles({})); }, []);
  return files;
}

function DockerTab() {
  const files = usePlatformFiles();
  if (!files) return <Spinner label="Loading platform files..." />;
  return (
    <div className="space-y-5">
      <ChartCard title="Run the whole platform" subtitle="One command brings up backend + frontend + a persisted database">
        <CodeBlock label="Command" path="terminal" content="docker compose up --build" />
      </ChartCard>
      {files.docker_compose?.exists && <ChartCard title="docker-compose.yml"><CodeBlock label="docker-compose.yml" path={files.docker_compose.path} content={files.docker_compose.content!} /></ChartCard>}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {files.backend_dockerfile?.exists && <ChartCard title="Backend Dockerfile"><CodeBlock label="backend/Dockerfile" path={files.backend_dockerfile.path} content={files.backend_dockerfile.content!} /></ChartCard>}
        {files.frontend_dockerfile?.exists && <ChartCard title="Frontend Dockerfile"><CodeBlock label="frontend/Dockerfile" path={files.frontend_dockerfile.path} content={files.frontend_dockerfile.content!} /></ChartCard>}
      </div>
    </div>
  );
}

function CiCdTab() {
  const files = usePlatformFiles();
  if (!files) return <Spinner label="Loading platform files..." />;
  return (
    <div className="space-y-5">
      <ChartCard title="GitHub Actions" subtitle="Installs dependencies, scans every .c/.cpp/.h file with the real pipeline, uploads the report as a workflow artifact">
        {files.github_workflow?.exists && <CodeBlock label="security_scan.yml" path={files.github_workflow.path} content={files.github_workflow.content!} />}
      </ChartCard>
      <ChartCard title="Run it locally (no CI needed)" subtitle="The same script the workflow calls">
        <CodeBlock label="Command" path="terminal" content="cd backend && python ci_scan.py --path .. --output ../security-report" />
      </ChartCard>
      {files.ci_scan_script?.exists && <ChartCard title="ci_scan.py"><CodeBlock label="ci_scan.py" path={files.ci_scan_script.path} content={files.ci_scan_script.content!} /></ChartCard>}
    </div>
  );
}

function RestApiTab() {
  const [pathCount, setPathCount] = useState<number | null>(null);
  useEffect(() => {
    fetch(`${BACKEND_URL}/openapi.json`).then((r) => r.json()).then((d) => setPathCount(Object.keys(d.paths || {}).length)).catch(() => setPathCount(null));
  }, []);
  return (
    <div className="space-y-5">
      <ChartCard title="Interactive API Documentation" subtitle={pathCount != null ? `${pathCount} documented endpoints, auto-generated by FastAPI` : "Loading..."}>
        <a href={`${BACKEND_URL}/docs`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">
          Open Swagger UI <ExternalLink size={14} />
        </a>
        <a href={`${BACKEND_URL}/redoc`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3) ml-3">
          Open ReDoc <ExternalLink size={14} />
        </a>
      </ChartCard>
      <ChartCard title="Core Endpoints" subtitle="A representative subset — see Swagger for the full list">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs mono">
          {[
            "POST /api/scan/code", "POST /api/scan/live", "POST /api/scan/batch",
            "GET /api/scan/{id}/detail", "GET /api/scan/{id}/intelligence",
            "GET /api/history", "GET /api/project/{batch_id}/summary",
            "GET /api/project/{batch_id}/dependency-graph", "GET /api/project/{batch_id}/knowledge-graph",
            "POST /api/copilot/ask", "POST /api/github/scan", "POST /api/watch/start",
            "GET /api/export/pdf/enterprise/{id}", "GET /api/gamification/status", "GET /api/search",
          ].map((ep) => (
            <div key={ep} className="px-3 py-2 rounded-lg bg-(--surface-3) text-(--text-secondary)">{ep}</div>
          ))}
        </div>
      </ChartCard>
    </div>
  );
}

function SettingsTab() {
  const [model, setModel] = useState<ModelChoice>(getDefaultModel());
  const change = (m: ModelChoice) => {
    setModel(m);
    setDefaultModel(m);
    toast.success(`Default model set to ${m}`);
  };
  return (
    <div className="space-y-5">
      <ChartCard title="Default Detection Model" subtitle="Used as the initial selection in Code Scanner and Live IDE (stored locally in this browser)">
        <div className="flex gap-2">
          {(["XGBoost", "Random Forest"] as ModelChoice[]).map((m) => (
            <button
              key={m}
              onClick={() => change(m)}
              className={`px-4 py-2.5 rounded-lg text-sm font-semibold border transition-colors ${model === m ? "bg-(--accent)/15 border-(--accent)/40 text-(--accent)" : "bg-(--surface-2) border-(--border-hairline) text-(--text-secondary) hover:bg-(--surface-3)"}`}
            >
              {m}
            </button>
          ))}
        </div>
      </ChartCard>
    </div>
  );
}
