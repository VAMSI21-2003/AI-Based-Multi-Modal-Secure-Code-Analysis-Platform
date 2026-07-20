import { useSearchParams } from "react-router-dom";
import { ScanLine, Code2, FolderGit2, Folder, Eye, GitFork } from "lucide-react";
import PageShell, { EmbeddedContext } from "../../components/PageShell";
import ModuleTabs, { type ModuleTabDef } from "../../components/ModuleTabs";
import Scanner from "../Scanner";
import LiveIDE from "../LiveIDE";
import ProjectScanner from "../ProjectScanner";
import FileExplorer from "../FileExplorer";
import WatchMode from "../WatchMode";
import GitHubMode from "../GitHubMode";

const TABS: ModuleTabDef[] = [
  { id: "scanner", label: "Code Scanner", icon: ScanLine },
  { id: "live-ide", label: "Live IDE", icon: Code2 },
  { id: "project-scanner", label: "Project Scanner", icon: FolderGit2 },
  { id: "file-explorer", label: "File Explorer", icon: Folder },
  { id: "watch-mode", label: "Watch Mode", icon: Eye },
  { id: "github-mode", label: "GitHub Mode", icon: GitFork },
];

export default function ScanCenterHub() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "scanner";
  const setTab = (id: string) => setParams((prev) => { const n = new URLSearchParams(prev); n.set("tab", id); return n; }, { replace: true });

  return (
    <PageShell title="Scan Center" subtitle="Every way to scan code — paste, live-edit, batch upload, watch a folder, or clone a repo">
      <ModuleTabs tabs={TABS} active={tab} onChange={setTab} />
      <EmbeddedContext.Provider value={true}>
        {tab === "scanner" && <Scanner />}
        {tab === "live-ide" && <LiveIDE />}
        {tab === "project-scanner" && <ProjectScanner />}
        {tab === "file-explorer" && <FileExplorer />}
        {tab === "watch-mode" && <WatchMode />}
        {tab === "github-mode" && <GitHubMode />}
      </EmbeddedContext.Provider>
    </PageShell>
  );
}
