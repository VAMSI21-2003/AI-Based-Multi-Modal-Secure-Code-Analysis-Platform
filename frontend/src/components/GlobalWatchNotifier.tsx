import { useEffect, useRef } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { listWatchSessions, getWatchEvents } from "../api/client";

// Two cadences, not one fixed interval: this component used to poll
// /api/watch/sessions every 4s on EVERY page, forever, even for users who
// have never once started a watch session -- pure wasted background
// traffic for the overwhelmingly common case. IDLE_POLL_MS is the "is
// anything even running?" heartbeat; ACTIVE_POLL_MS (the original cadence)
// only kicks in once a running session is actually confirmed to exist, so
// responsiveness while genuinely watching is unchanged.
const IDLE_POLL_MS = 30_000;
const ACTIVE_POLL_MS = 4_000;

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
    let timeoutId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      let sessions;
      try {
        sessions = await listWatchSessions();
      } catch {
        if (!cancelled) timeoutId = setTimeout(poll, IDLE_POLL_MS);
        return;
      }
      if (cancelled) return;

      const running = sessions.filter((s) => s.status === "running");

      for (const s of running) {
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

      if (!cancelled) timeoutId = setTimeout(poll, running.length > 0 ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };

    poll();
    return () => { cancelled = true; clearTimeout(timeoutId); };
  }, []);

  return null;
}
