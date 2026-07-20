import { useEffect, useRef } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { listWatchSessions, getWatchEvents } from "../api/client";

const POLL_MS = 4000;

/**
 * Cross-page Watch Mode notifications (Phase 4). WatchMode.tsx already polls
 * and renders a live feed while the user is looking at that page, but a
 * running watch session should keep surfacing rescans no matter where in the
 * app the user navigates to next -- this is a silent, App-level sibling
 * poller that only ever calls toast(), it renders nothing itself.
 */
export default function GlobalWatchNotifier() {
  const location = useLocation();
  const [params] = useSearchParams();
  const sinceRef = useRef<Record<string, number>>({});
  const activeSessionRef = useRef<string | null>(null);

  useEffect(() => {
    const onWatchModePage =
      location.pathname === "/watch-mode" ||
      (location.pathname === "/scan-center" && params.get("tab") === "watch-mode");
    activeSessionRef.current = onWatchModePage ? params.get("session") : null;
  }, [location.pathname, params]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      let sessions;
      try {
        sessions = await listWatchSessions();
      } catch {
        return;
      }
      if (cancelled) return;

      for (const s of sessions.filter((s) => s.status === "running")) {
        const since = sinceRef.current[s.session_id];

        // First sighting of a running session: baseline the cursor at its
        // current position instead of toasting the whole event backlog.
        if (since === undefined) {
          try {
            const d = await getWatchEvents(s.session_id, 0);
            if (!cancelled) sinceRef.current[s.session_id] = d.next_since;
          } catch { /* transient -- retried next tick */ }
          continue;
        }

        try {
          const d = await getWatchEvents(s.session_id, since);
          if (cancelled) return;
          sinceRef.current[s.session_id] = d.next_since;

          // WatchMode's own poller already renders + advances this session's
          // feed while the user is looking at it -- keep the cursor in sync
          // but skip the redundant toast.
          if (activeSessionRef.current === s.session_id) continue;

          for (const e of d.events) {
            if (e.type !== "created" && e.type !== "modified") continue;
            const base = e.filename.split(/[\\/]/).pop() || e.filename;
            const toastId = `watch-${s.session_id}-${e.seq}`;
            if (e.verdict === "VULNERABLE") {
              toast.error(`${base} rescanned — VULNERABLE (${(e.vuln_probability ?? 0).toFixed(0)}%)`, { id: toastId });
            } else if (e.verdict) {
              toast.success(`${base} rescanned — safe`, { id: toastId });
            }
          }
        } catch { /* transient -- retried next tick */ }
      }
    };

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return null;
}
