import { NavLink, Link } from "react-router-dom";
import {
  ShieldCheck, ChevronsLeft, ChevronsRight, Search,
  Radio, ScanLine, Network, Bot, BarChart3, FlaskConical, FileText, Settings,
} from "lucide-react";
import { useState } from "react";
import clsx from "clsx";

// Phase 6 (UX consolidation, "STOP" pass): the sidebar now shows EXACTLY
// the 8 enterprise modules requested -- nothing else. Every one of the
// ~40 original pages still exists and still works at its original route;
// this only changes what the primary nav surfaces. See SEARCH_INDEX below
// for the full page list (used by the command palette) and each
// pages/hubs/*.tsx file for how pages were distributed into tabs.
export const NAV_GROUPS: { section: string; items: { to: string; label: string; icon: any; end?: boolean }[] }[] = [
  {
    section: "Modules",
    items: [
      { to: "/command-center", label: "Command Center", icon: Radio },
      { to: "/scan-center", label: "Scan Center", icon: ScanLine },
      { to: "/program-analysis", label: "Analysis Center", icon: Network },
      { to: "/ai-assistant", label: "AI Assistant", icon: Bot },
      { to: "/analytics-hub", label: "Analytics", icon: BarChart3 },
      { to: "/ai-engine", label: "AI Engine", icon: FlaskConical },
      { to: "/reporting", label: "Reports", icon: FileText },
      { to: "/platform-hub", label: "Platform", icon: Settings },
    ],
  },
];

// Full page index for the command palette (Ctrl+K) -- every original page
// is reachable here via its hub's deep-link (?tab=...), even though the
// visible sidebar only shows the 8 modules above. Nothing is inaccessible;
// it's one keystroke-search away instead of a permanent nav row.
export const SEARCH_INDEX: { to: string; label: string; icon: any; section: string }[] = [
  ...NAV_GROUPS[0].items.map((i) => ({ ...i, section: "Modules" })),
  { to: "/welcome", label: "Home", icon: Radio, section: "Overview" },
  { to: "/presentation", label: "Presentation Mode", icon: Radio, section: "Overview" },
  { to: "/scan-center?tab=scanner", label: "Code Scanner", icon: ScanLine, section: "Scan Center" },
  { to: "/scan-center?tab=live-ide", label: "Live IDE", icon: ScanLine, section: "Scan Center" },
  { to: "/scan-center?tab=project-scanner", label: "Project Scanner", icon: ScanLine, section: "Scan Center" },
  { to: "/scan-center?tab=file-explorer", label: "File Explorer", icon: ScanLine, section: "Scan Center" },
  { to: "/scan-center?tab=watch-mode", label: "Watch Mode", icon: ScanLine, section: "Scan Center" },
  { to: "/scan-center?tab=github-mode", label: "GitHub Mode", icon: ScanLine, section: "Scan Center" },
  { to: "/program-analysis?tab=analysis", label: "AI Analysis", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=explanation", label: "Code Explanation", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=heatmap", label: "Vulnerability Heatmap", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=attack-graph", label: "Attack Graph", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=call-graph", label: "Call Graph Explorer", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=cfg", label: "Execution Flow (CFG)", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=memory", label: "Memory Visualizer", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=data-flow", label: "Dependency Graph", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=static-analysis", label: "Advanced Static Analysis", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=knowledge-graph", label: "Security Knowledge Graph", icon: Network, section: "Analysis Center" },
  { to: "/program-analysis?tab=simulator", label: "Exploit Simulator", icon: Network, section: "Analysis Center" },
  { to: "/ai-assistant?tab=copilot", label: "Security Copilot", icon: Bot, section: "AI Assistant" },
  { to: "/ai-assistant?tab=knowledge-base", label: "Knowledge Base", icon: Bot, section: "AI Assistant" },
  { to: "/ai-assistant?tab=recommendations", label: "AI Recommendations", icon: Bot, section: "AI Assistant" },
  { to: "/ai-assistant?tab=auto-patch", label: "Auto Patch Generator", icon: Bot, section: "AI Assistant" },
  { to: "/ai-assistant?tab=code-diff", label: "Code Diff Viewer", icon: Bot, section: "AI Assistant" },
  { to: "/analytics-hub?tab=dashboard", label: "Dashboard", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=scorecard", label: "Security Scorecard", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=timeline", label: "Vulnerability Timeline", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=history", label: "Scan History", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=security-dashboard", label: "Security Dashboard", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=project-analytics", label: "Project Analytics", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=search", label: "Vulnerability Search", icon: BarChart3, section: "Analytics" },
  { to: "/analytics-hub?tab=gamification", label: "Security Gamification", icon: BarChart3, section: "Analytics" },
  { to: "/ai-engine?tab=research", label: "Research", icon: FlaskConical, section: "AI Engine" },
  { to: "/ai-engine?tab=comparison", label: "Model Comparison", icon: FlaskConical, section: "AI Engine" },
  { to: "/ai-engine?tab=explainability", label: "Explainability", icon: FlaskConical, section: "AI Engine" },
  { to: "/ai-engine?tab=architecture", label: "Architecture 3D", icon: FlaskConical, section: "AI Engine" },
  { to: "/reporting?tab=reports", label: "Security Reports", icon: FileText, section: "Reports" },
  { to: "/reporting?tab=export-center", label: "Export Center", icon: FileText, section: "Reports" },
  { to: "/platform-hub?tab=system", label: "System Monitor", icon: Settings, section: "Platform" },
  { to: "/platform-hub?tab=docker", label: "Docker", icon: Settings, section: "Platform" },
  { to: "/platform-hub?tab=cicd", label: "CI/CD", icon: Settings, section: "Platform" },
  { to: "/platform-hub?tab=api", label: "REST API", icon: Settings, section: "Platform" },
  { to: "/platform-hub?tab=settings", label: "Settings", icon: Settings, section: "Platform" },
];

const BACKEND_URL = "http://127.0.0.1:8000";

export default function Sidebar({ onOpenPalette }: { onOpenPalette?: () => void }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={clsx(
        "h-screen sticky top-0 shrink-0 flex flex-col border-r border-(--border-hairline) transition-all duration-250 ease-out",
        collapsed ? "w-[76px]" : "w-[240px]"
      )}
      style={{ background: "linear-gradient(180deg, var(--surface-1) 0%, #121216 100%)" }}
    >
      <Link to="/welcome" className="flex items-center gap-2.5 px-4 h-16 border-b border-(--border-hairline) shrink-0 hover:bg-(--surface-2) transition-colors" title="Home">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-(--accent) to-(--series-7) flex items-center justify-center shrink-0 shadow-[0_0_18px_var(--accent-glow)] transition-transform hover:scale-105 hover:rotate-3 duration-300">
          <ShieldCheck size={18} color="white" strokeWidth={2.4} />
        </div>
        {!collapsed && (
          <div className="min-w-0 fade-in-up">
            <div className="text-[13px] font-bold leading-tight truncate">SecureCode AI</div>
            <div className="text-[10px] text-(--text-muted) leading-tight truncate">Secure Code Intelligence Platform</div>
          </div>
        )}
      </Link>

      {!collapsed && (
        <button
          onClick={onOpenPalette}
          className="mx-2.5 mt-2.5 flex items-center gap-2 px-3 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-(--text-muted) hover:text-(--text-primary) hover:border-(--border-hairline-strong) transition-colors text-xs focus-ring shrink-0"
        >
          <Search size={13} />
          <span className="flex-1 text-left">Search all pages...</span>
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-(--surface-3) border border-(--border-hairline) font-mono">Ctrl K</kbd>
        </button>
      )}

      <nav className="flex-1 overflow-y-auto scrollbar-thin py-3 px-2.5">
        {NAV_GROUPS.map((group) => (
          <div key={group.section} className="mb-3">
            <div className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    clsx(
                      "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium relative",
                      "transition-all duration-150 ease-out",
                      isActive
                        ? "text-(--text-primary)"
                        : "text-(--text-secondary) hover:text-(--text-primary) hover:bg-(--surface-2) hover:translate-x-0.5"
                    )
                  }
                  style={({ isActive }) => (isActive ? {
                    background: "linear-gradient(90deg, rgba(57,135,229,0.16), rgba(57,135,229,0.03))",
                    boxShadow: "inset 0 0 0 1px rgba(57,135,229,0.25)",
                  } : undefined)}
                  title={collapsed ? label : undefined}
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-(--accent)" style={{ boxShadow: "0 0 8px var(--accent)" }} />
                      )}
                      <Icon size={17} strokeWidth={2} className={clsx("shrink-0 transition-transform duration-150", isActive && "text-(--accent)", "group-hover:scale-110")} />
                      {!collapsed && <span className="truncate">{label}</span>}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-2.5 border-t border-(--border-hairline) shrink-0 space-y-1">
        <a
          href={`${BACKEND_URL}/docs`}
          target="_blank"
          rel="noreferrer"
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-(--text-muted) hover:text-(--text-primary) hover:bg-(--surface-2) transition-colors text-xs font-medium"
          title="API Docs (Swagger)"
        >
          <FileText size={16} className="shrink-0" />
          {!collapsed && <span className="truncate">API Docs (Swagger)</span>}
        </a>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-(--text-muted) hover:text-(--text-primary) hover:bg-(--surface-2) transition-colors focus-ring"
        >
          {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
