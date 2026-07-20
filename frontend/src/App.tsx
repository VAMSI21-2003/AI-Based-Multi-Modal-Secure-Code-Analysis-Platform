import { useEffect, useState, useCallback } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { AnimatePresence, motion } from "framer-motion";
import Sidebar from "./components/Sidebar";
import CommandPalette from "./components/CommandPalette";
import GlobalWatchNotifier from "./components/GlobalWatchNotifier";

export default function App() {
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);

  const openPalette = useCallback(() => setPaletteOpen(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-screen">
      <Sidebar onOpenPalette={openPalette} />
      <main className="flex-1 min-w-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <GlobalWatchNotifier />
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "#1a1a1f",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.12)",
            fontSize: "13px",
            borderRadius: "10px",
            boxShadow: "0 10px 30px -10px rgba(0,0,0,0.6)",
          },
          success: { iconTheme: { primary: "#0ca30c", secondary: "#1a1a1f" } },
          error: { iconTheme: { primary: "#d03b3b", secondary: "#1a1a1f" } },
        }}
      />
    </div>
  );
}
