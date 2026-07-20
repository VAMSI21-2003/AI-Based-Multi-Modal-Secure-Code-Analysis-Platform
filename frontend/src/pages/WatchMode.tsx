import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  Radio, Play, Square, FolderOpen, FileCode2, ShieldAlert, ShieldCheck, GaugeCircle,
  Plus, Pencil, Trash2, AlertCircle, X, GitCompare,
} from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import StatCard from "../components/StatCard";
import Gauge from "../components/Gauge";
import DiffViewer from "../components/DiffViewer";
import { EmptyState, Spinner } from "../components/Loading";
import {
  startWatch, stopWatch, listWatchSessions, getWatchEvents, getWatchDiff,
  type WatchEvent, type WatchSession,
} from "../api/client";
import { timeAgo } from "../utils/risk";

const POLL_MS = 2000;

const EVENT_ICON: Record<string, any> = { initial: FileCode2, created: Plus, modified: Pencil, deleted: Trash2, error: AlertCircle };
const EVENT_COLOR: Record<string, string> = {
  initial: "var(--text-muted)", created: "var(--status-good)", modified: "var(--accent)",
  deleted: "var(--status-critical)", error: "var(--status-critical)",
};

export default function WatchMode() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sessionId = params.get("session");

  const [sessions, setSessions] = useState<WatchSession[] | null>(null);
  const [pathInput, setPathInput] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [starting, setStarting] = useState(false);

  const [live, setLive] = useState<WatchSession | null>(null);
  const [events, setEvents] = useState<WatchEvent[]>([]);
  const sinceRef = useRef(0);
  const [diffFor, setDiffFor] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      listWatchSessions().then(setSessions).catch(() => setSessions([]));
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    sinceRef.current = 0;
    setEvents([]);
    let cancelled = false;

    const poll = () => {
      getWatchEvents(sessionId, sinceRef.current)
        .then((d) => {
          if (cancelled) return;
          sinceRef.current = d.next_since;
          setLive({
            session_id: d.session_id, path: d.path, project_name: d.project_name,
            status: d.status, created_at: "", batch_id: d.batch_id, score: d.score,
          });
          if (d.events.length > 0) setEvents((prev) => [...d.events].reverse().concat(prev));
        })
        .catch(() => {});
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [sessionId]);

  const onStart = async () => {
    if (!pathInput.trim()) { toast.error("Enter a folder path to watch"); return; }
    setStarting(true);
    try {
      const r = await startWatch(pathInput.trim(), nameInput.trim() || "Watched Project");
      toast.success(`Watching started — ${r.initial_files_scanned} file(s) scanned`);
      navigate(`/watch-mode?session=${r.session_id}`);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to start watching");
    } finally {
      setStarting(false);
    }
  };

  const onStop = async () => {
    if (!sessionId) return;
    try {
      await stopWatch(sessionId);
      toast.success("Watch session stopped");
      setLive((l) => (l ? { ...l, status: "stopped" } : l));
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e.message || "Failed to stop");
    }
  };

  if (!sessionId) {
    return (
      <PageShell title="Watch Mode" subtitle="Automatically rescan a local folder whenever a file changes">
        <ChartCard title="Start Watching a Folder" subtitle="The backend process must have filesystem access to this path" className="mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            <input
              value={pathInput} onChange={(e) => setPathInput(e.target.value)}
              placeholder="C:\path\to\project"
              className="flex-1 bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-sm mono focus-ring outline-none"
            />
            <input
              value={nameInput} onChange={(e) => setNameInput(e.target.value)}
              placeholder="Project name (optional)"
              className="md:w-64 bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-sm focus-ring outline-none"
            />
            <button
              onClick={onStart} disabled={starting}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 disabled:opacity-50"
            >
              <Play size={15} /> {starting ? "Starting..." : "Start Watching"}
            </button>
          </div>
        </ChartCard>

        {sessions === null ? <Spinner label="Loading sessions..." /> : sessions.length === 0 ? (
          <EmptyState icon={Radio} title="No watch sessions yet" description="Start watching a folder above to see live rescans as files change." />
        ) : (
          <>
            <div className="mb-2 text-sm font-semibold">Watch Sessions</div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {sessions.map((s) => (
                <button key={s.session_id} onClick={() => navigate(`/watch-mode?session=${s.session_id}`)} className="card card-hover p-5 text-left">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-semibold truncate">{s.project_name}</div>
                    <span className={`w-2 h-2 rounded-full ${s.status === "running" ? "bg-(--status-good) animate-pulse-soft" : "bg-(--text-muted)"}`} />
                  </div>
                  <div className="text-xs mono text-(--text-muted) truncate">{s.path}</div>
                  <div className="text-xs text-(--text-muted) mt-2">{s.score.total_files} files &middot; {s.score.vulnerable_files} vulnerable &middot; score {s.score.security_score}</div>
                </button>
              ))}
            </div>
          </>
        )}
      </PageShell>
    );
  }

  return (
    <PageShell
      title={live?.project_name || "Watch Mode"}
      subtitle={live?.path}
      actions={
        live?.status === "running" ? (
          <button onClick={onStop} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--status-critical)/15 border border-(--status-critical)/40 text-(--status-critical) text-sm font-semibold hover:bg-(--status-critical)/25">
            <Square size={14} /> Stop Watching
          </button>
        ) : (
          <Link to="/watch-mode" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <FolderOpen size={14} /> Watch Another Folder
          </Link>
        )
      }
    >
      <div className="flex items-center gap-2 mb-4">
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${live?.status === "running" ? "bg-(--status-good)/15 text-(--status-good)" : "bg-(--surface-3) text-(--text-muted)"}`}>
          <Radio size={11} className={live?.status === "running" ? "animate-pulse-soft" : ""} /> {live?.status === "running" ? "Live — watching for changes" : "Stopped"}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Files Tracked" value={live?.score.total_files ?? 0} icon={FileCode2} accent="var(--series-1)" />
        <StatCard label="Vulnerable" value={live?.score.vulnerable_files ?? 0} icon={ShieldAlert} accent="var(--status-critical)" />
        <StatCard label="Safe" value={live?.score.safe_files ?? 0} icon={ShieldCheck} accent="var(--status-good)" />
        <div className="card p-5 flex items-center gap-4">
          <Gauge value={live?.score.security_score ?? 0} size={64} color={(live?.score.security_score ?? 0) >= 70 ? "var(--status-good)" : (live?.score.security_score ?? 0) >= 40 ? "var(--status-warning)" : "var(--status-critical)"} />
          <div>
            <div className="text-xs uppercase tracking-wider text-(--text-muted) font-medium flex items-center gap-1"><GaugeCircle size={12} /> Live Score</div>
            <div className="text-xl font-bold tabular mt-0.5">{live?.score.security_score ?? 0}</div>
          </div>
        </div>
      </div>

      <ChartCard title="Live Event Feed" subtitle="Every create / modify / delete is rescanned automatically as it happens">
        {events.length === 0 ? (
          <div className="py-10 text-center text-sm text-(--text-muted)">Watching for changes... edit a file in the watched folder to see it appear here.</div>
        ) : (
          <div className="divide-y divide-(--border-hairline)">
            {events.map((e) => {
              const Icon = EVENT_ICON[e.type] ?? FileCode2;
              const color = EVENT_COLOR[e.type] ?? "var(--text-muted)";
              const clickable = e.type !== "deleted" && e.type !== "error";
              return (
                <div
                  key={e.seq}
                  onClick={() => clickable && setDiffFor(e.filename)}
                  className={`flex items-center justify-between py-2.5 px-1 -mx-1 rounded-lg ${clickable ? "cursor-pointer hover:bg-(--surface-3)" : ""} transition-colors`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon size={15} style={{ color }} className="shrink-0" />
                    <div className="min-w-0">
                      <div className="text-sm mono truncate">{e.filename}</div>
                      <div className="text-[11px] text-(--text-muted) capitalize">{e.type}{e.error ? ` — ${e.error}` : ""}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {e.verdict && (
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${e.verdict === "VULNERABLE" ? "text-(--status-critical) bg-(--status-critical)/12" : "text-(--status-good) bg-(--status-good)/12"}`}>
                        {e.verdict}
                      </span>
                    )}
                    <span className="text-xs text-(--text-muted) w-16 text-right">{timeAgo(e.timestamp)}</span>
                    {clickable && <GitCompare size={13} className="text-(--text-muted)" />}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </ChartCard>

      {diffFor && sessionId && <DiffModal sessionId={sessionId} filename={diffFor} onClose={() => setDiffFor(null)} />}
    </PageShell>
  );
}

function DiffModal({ sessionId, filename, onClose }: { sessionId: string; filename: string; onClose: () => void }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof getWatchDiff>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWatchDiff(sessionId, filename).then(setData).catch((e) => setError(e?.response?.data?.detail || e.message));
  }, [sessionId, filename]);

  return (
    <div className="fixed inset-0 z-[900] flex items-center justify-center p-6" style={{ background: "rgba(5,5,7,0.7)", backdropFilter: "blur(4px)" }} onClick={onClose}>
      <div className="w-full max-w-4xl max-h-[85vh] overflow-auto rounded-xl border border-(--border-hairline-strong) bg-(--surface-2) p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-semibold mono">{filename}</div>
          <button onClick={onClose} className="text-(--text-muted) hover:text-(--text-primary)"><X size={18} /></button>
        </div>
        {error ? <div className="text-sm text-(--status-critical)">{error}</div> : !data ? <Spinner label="Loading diff..." /> : !data.previous ? (
          <div className="text-sm text-(--text-muted) py-8 text-center">This is the first recorded scan of this file in this session — nothing to diff against yet.</div>
        ) : (
          <DiffViewer original={data.previous.code} modified={data.current.code} />
        )}
      </div>
    </div>
  );
}
