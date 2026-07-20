import { createContext, useContext } from "react";
import Topbar from "./Topbar";
import CyberBackground from "./CyberBackground";

// Phase 5: lets an existing page component be reused UNMODIFIED as a tab
// inside a module hub page (see pages/hubs/*.tsx). When a hub renders a tab
// wrapped in <EmbeddedContext.Provider value={true}>, that page's own
// PageShell call detects it and skips its Topbar/outer chrome -- the hub
// already provides page-level chrome, so this avoids a doubled header
// without touching any of the ~34 existing page files that call PageShell.
// Default (no provider, i.e. every page's normal standalone route) is
// unchanged from before this context existed.
export const EmbeddedContext = createContext(false);

export default function PageShell({
  title, subtitle, actions, children, glow,
}: { title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode; glow?: boolean }) {
  const embedded = useContext(EmbeddedContext);

  if (embedded) {
    return (
      <div>
        {actions && <div className="flex justify-end gap-2 mb-4">{actions}</div>}
        {children}
      </div>
    );
  }

  return (
    <div className="relative">
      {glow && (
        <div className="absolute top-0 left-0 right-0 h-[380px] overflow-hidden pointer-events-none opacity-60">
          <CyberBackground />
        </div>
      )}
      <div className="relative">
        <Topbar title={title} subtitle={subtitle} />
        <div className="px-8 py-6 max-w-[1500px]">
          {actions && <div className="flex justify-end gap-2 mb-4">{actions}</div>}
          {children}
        </div>
      </div>
    </div>
  );
}
