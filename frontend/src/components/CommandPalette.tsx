import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, CornerDownLeft, ArrowUp, ArrowDown } from "lucide-react";
import { SEARCH_INDEX } from "./Sidebar";

const ALL_ITEMS = SEARCH_INDEX;

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const navigate = useNavigate();

  const results = useMemo(() => {
    if (!query.trim()) return ALL_ITEMS;
    const q = query.toLowerCase();
    return ALL_ITEMS.filter((it) => it.label.toLowerCase().includes(q) || it.section.toLowerCase().includes(q));
  }, [query]);

  useEffect(() => {
    if (open) { setQuery(""); setActive(0); }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(results.length - 1, a + 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
      if (e.key === "Enter") {
        const item = results[active];
        if (item) { navigate(item.to); onClose(); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, active, navigate, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[999] flex items-start justify-center pt-[14vh] px-4"
          style={{ background: "rgba(5,5,7,0.6)", backdropFilter: "blur(4px)" }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="w-full max-w-lg rounded-xl border border-(--border-hairline-strong) overflow-hidden"
            style={{ background: "var(--surface-2)", boxShadow: "0 30px 80px -20px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-(--border-hairline)">
              <Search size={16} className="text-(--text-muted) shrink-0" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Jump to a page..."
                className="flex-1 bg-transparent outline-none text-sm placeholder:text-(--text-muted)"
              />
              <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-(--surface-3) border border-(--border-hairline) font-mono text-(--text-muted)">Esc</kbd>
            </div>
            <div className="max-h-[50vh] overflow-y-auto scrollbar-thin py-1.5">
              {results.length === 0 && (
                <div className="px-4 py-8 text-center text-xs text-(--text-muted)">No pages match "{query}"</div>
              )}
              {results.map((item, i) => (
                <button
                  key={item.to}
                  onClick={() => { navigate(item.to); onClose(); }}
                  onMouseEnter={() => setActive(i)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                  style={{ background: i === active ? "rgba(57,135,229,0.12)" : "transparent" }}
                >
                  <item.icon size={15} className={i === active ? "text-(--accent)" : "text-(--text-muted)"} />
                  <span className={`text-[13px] flex-1 ${i === active ? "text-(--text-primary)" : "text-(--text-secondary)"}`}>{item.label}</span>
                  <span className="text-[10px] text-(--text-muted) uppercase tracking-wide">{item.section}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4 px-4 py-2 border-t border-(--border-hairline) text-[10px] text-(--text-muted)">
              <span className="flex items-center gap-1"><ArrowUp size={11} /><ArrowDown size={11} /> Navigate</span>
              <span className="flex items-center gap-1"><CornerDownLeft size={11} /> Select</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
