import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud, FolderOpen, FileArchive, ScanLine, Sparkles, Loader2,
  CheckCircle2, XCircle, ArrowRight, FileCode2, X, Download, FolderGit2, Code2,
} from "lucide-react";
import clsx from "clsx";
import toast from "react-hot-toast";
import PageShell from "../components/PageShell";
import CodeEditor from "../components/CodeEditor";
import RiskBadge, { VerdictPill } from "../components/RiskBadge";
import ProgressBar from "../components/ProgressBar";
import { EXAMPLES } from "../data/examples";
import { scanCode, scanBatch, downloadBatchPdf, type ScanResult, type BatchResult } from "../api/client";
import { getDefaultModel } from "../utils/settings";

type Mode = "paste" | "batch" | "examples";

const DEFAULT_CODE = `void process(char *input) {
    char buf[64];
    strcpy(buf, input);  // potential buffer overflow
}`;

export default function Scanner() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("paste");
  const [code, setCode] = useState(DEFAULT_CODE);
  const [projectName, setProjectName] = useState("Untitled Project");
  const [filename, setFilename] = useState("pasted_code.c");
  const [modelChoice, setModelChoice] = useState<string>(getDefaultModel);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [batchProgress, setBatchProgress] = useState(0);
  const [batchScanning, setBatchScanning] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const runSingleScan = async () => {
    setScanning(true);
    setError(null);
    setResult(null);
    try {
      const r = await scanCode({ code, project_name: projectName, filename, model_choice: modelChoice, source: mode === "examples" ? "example" : "paste" });
      setResult(r);
      toast.success(`${r.verdict === "VULNERABLE" ? "Vulnerability detected" : "Scan complete — looks safe"} (${r.risk_level})`);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || "Scan failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setScanning(false);
    }
  };

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    setFiles((prev) => [...prev, ...arr]);
    setBatchResult(null);
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const runBatchScan = async () => {
    if (!files.length) return;
    setBatchScanning(true);
    setBatchProgress(0);
    setBatchResult(null);
    setError(null);
    try {
      const r = await scanBatch(files, projectName, modelChoice, setBatchProgress);
      setBatchResult(r);
      toast.success(`Scanned ${r.total_files_scanned} file(s) — ${r.vulnerable_count} vulnerable`);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || "Batch scan failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setBatchScanning(false);
    }
  };

  return (
    <PageShell title="Code Scanner" subtitle="Analyse individual functions or scan entire projects for vulnerabilities">
      <div className="flex gap-2 mb-5">
        {([
          { id: "paste", label: "Paste / Edit Code", icon: FileCode2 },
          { id: "batch", label: "Batch Upload", icon: UploadCloud },
          { id: "examples", label: "Load Example", icon: Sparkles },
        ] as { id: Mode; label: string; icon: any }[]).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setMode(id)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors border",
              mode === id
                ? "bg-(--surface-3) border-(--border-hairline-strong) text-(--text-primary)"
                : "border-(--border-hairline) text-(--text-muted) hover:text-(--text-primary) hover:bg-(--surface-2)"
            )}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {error && (
        <div className="card p-4 mb-4 border-(--status-critical) text-sm text-(--status-critical)">{error}</div>
      )}

      {(mode === "paste" || mode === "examples") && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2 space-y-4">
            {mode === "examples" && (
              <div className="card p-4">
                <div className="text-sm font-semibold mb-3">Choose a built-in example</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {EXAMPLES.map((ex) => (
                    <button
                      key={ex.name}
                      onClick={() => { setCode(ex.code); setFilename(ex.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase() + ".c"); }}
                      className={clsx(
                        "text-left px-3 py-2.5 rounded-lg border text-xs transition-colors",
                        code === ex.code ? "border-(--accent) bg-(--surface-3)" : "border-(--border-hairline) hover:bg-(--surface-2)"
                      )}
                    >
                      <div className="flex items-center gap-1.5 font-medium text-(--text-primary)">
                        {ex.vulnerable ? <XCircle size={12} className="text-(--status-critical)" /> : <CheckCircle2 size={12} className="text-(--status-good)" />}
                        {ex.name}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <CodeEditor value={code} onChange={setCode} height={420} />

            <div className="flex items-center justify-between">
              <div className="text-xs text-(--text-muted)">{code.split("\n").length} lines &middot; {code.length} characters</div>
              <button
                onClick={runSingleScan}
                disabled={scanning || !code.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_20px_var(--accent-glow)]"
              >
                {scanning ? <Loader2 size={15} className="animate-spin" /> : <ScanLine size={15} />}
                {scanning ? "Analysing with CodeBERT..." : "Analyse Code"}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="card p-4 space-y-3">
              <div className="text-sm font-semibold">Scan Configuration</div>
              <div>
                <label className="text-xs text-(--text-muted)">Project Name</label>
                <input value={projectName} onChange={(e) => setProjectName(e.target.value)}
                  className="mt-1 w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2 text-sm focus-ring outline-none" />
              </div>
              <div>
                <label className="text-xs text-(--text-muted)">Filename</label>
                <input value={filename} onChange={(e) => setFilename(e.target.value)}
                  className="mt-1 w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2 text-sm mono focus-ring outline-none" />
              </div>
              <div>
                <label className="text-xs text-(--text-muted)">Classifier Model</label>
                <select value={modelChoice} onChange={(e) => setModelChoice(e.target.value)}
                  className="mt-1 w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2 text-sm focus-ring outline-none">
                  <option>XGBoost</option>
                  <option>Random Forest</option>
                </select>
              </div>
            </div>

            {result && (
              <div className="card p-4 space-y-3 fade-in-up">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">Result</div>
                  <VerdictPill verdict={result.verdict} />
                </div>
                <RiskBadge level={result.risk_level} />
                <ProgressBar value={result.vuln_probability} color={result.risk_color} label="Vulnerability Probability" />
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Confidence</div>
                    <div className="text-base font-bold tabular">{result.confidence.toFixed(1)}%</div>
                  </div>
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Model</div>
                    <div className="text-sm font-semibold truncate">{result.model_used}</div>
                  </div>
                </div>
                {result.is_demo && (
                  <div className="text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2">
                    Demo mode: trained models not found — this used the heuristic fallback.
                  </div>
                )}
                <button
                  onClick={() => navigate(`/scan-center?tab=live-ide&scan=${result.id}`)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-sm font-medium transition"
                >
                  <Code2 size={14} /> Open in Live IDE
                </button>
                <button
                  onClick={() => navigate(`/analysis?scan=${result.id}`)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-sm font-medium transition"
                >
                  View Full Analysis <ArrowRight size={14} />
                </button>
                <button
                  onClick={() => navigate(`/explanation?scan=${result.id}`)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-sm font-medium transition"
                >
                  AI Code Explanation <ArrowRight size={14} />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {mode === "batch" && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2 space-y-4">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={clsx(
                "card border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center transition-colors",
                dragOver ? "border-(--accent) bg-(--surface-3)" : "border-(--border-hairline)"
              )}
            >
              <UploadCloud size={32} className="text-(--text-muted) mb-3" />
              <div className="text-sm font-medium">Drag & drop .c / .cpp / .h files, folders, or a .zip archive</div>
              <div className="text-xs text-(--text-muted) mt-1">or use the buttons below</div>
              <div className="flex gap-2 mt-4">
                <button onClick={() => fileInputRef.current?.click()} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-xs font-medium">
                  <FileCode2 size={13} /> Choose Files
                </button>
                <button onClick={() => folderInputRef.current?.click()} className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-3) hover:bg-(--surface-2) border border-(--border-hairline) text-xs font-medium">
                  <FolderOpen size={13} /> Choose Folder
                </button>
                <span className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-(--surface-3)/50 border border-(--border-hairline) text-xs font-medium text-(--text-muted)">
                  <FileArchive size={13} /> .zip supported via Files
                </span>
              </div>
              <input ref={fileInputRef} type="file" multiple accept=".c,.cpp,.h,.cc,.cxx,.hpp,.zip" className="hidden"
                onChange={(e) => e.target.files && addFiles(e.target.files)} />
              <input ref={folderInputRef} type="file" multiple {...{ webkitdirectory: "true", directory: "true" } as any} className="hidden"
                onChange={(e) => e.target.files && addFiles(e.target.files)} />
            </div>

            {files.length > 0 && (
              <div className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-semibold">{files.length} file{files.length !== 1 && "s"} queued</div>
                  <button onClick={() => setFiles([])} className="text-xs text-(--text-muted) hover:text-(--status-critical)">Clear all</button>
                </div>
                <div className="max-h-56 overflow-y-auto scrollbar-thin space-y-1">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-xs px-2.5 py-1.5 rounded-lg bg-(--surface-3)">
                      <span className="mono truncate">{(f as any).webkitRelativePath || f.name}</span>
                      <button onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))} className="text-(--text-muted) hover:text-(--status-critical)">
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>

                {batchScanning && <div className="mt-4"><ProgressBar value={batchProgress} label="Uploading & scanning" /></div>}

                <button
                  onClick={runBatchScan}
                  disabled={batchScanning}
                  className="mt-4 w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 transition disabled:opacity-40"
                >
                  {batchScanning ? <Loader2 size={15} className="animate-spin" /> : <ScanLine size={15} />}
                  {batchScanning ? "Scanning..." : `Scan ${files.length} File${files.length !== 1 ? "s" : ""}`}
                </button>
              </div>
            )}

            {batchResult && (
              <div className="card p-4 fade-in-up">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-semibold">Batch Results</div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => navigate(`/project-scanner?batch=${batchResult.batch_id}`)}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-(--accent) hover:underline"
                    >
                      <FolderGit2 size={13} /> Project Dashboard
                    </button>
                    <a href={downloadBatchPdf(batchResult.batch_id)} className="inline-flex items-center gap-1.5 text-xs font-medium text-(--accent) hover:underline">
                      <Download size={13} /> Download Project PDF
                    </a>
                  </div>
                </div>
                <div className="max-h-96 overflow-y-auto scrollbar-thin divide-y divide-(--border-hairline)">
                  {batchResult.results.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => navigate(`/analysis?scan=${r.id}`)}
                      className="w-full flex items-center justify-between py-2.5 px-1 hover:bg-(--surface-3) rounded-lg transition-colors text-left"
                    >
                      <span className="text-xs mono truncate">{r.filename}</span>
                      <span className="flex items-center gap-2 shrink-0 ml-2">
                        <RiskBadge level={r.risk_level} size="sm" />
                        <VerdictPill verdict={r.verdict} />
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className="card p-4 space-y-3">
              <div className="text-sm font-semibold">Batch Configuration</div>
              <div>
                <label className="text-xs text-(--text-muted)">Project Name</label>
                <input value={projectName} onChange={(e) => setProjectName(e.target.value)}
                  className="mt-1 w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2 text-sm focus-ring outline-none" />
              </div>
              <div>
                <label className="text-xs text-(--text-muted)">Classifier Model</label>
                <select value={modelChoice} onChange={(e) => setModelChoice(e.target.value)}
                  className="mt-1 w-full bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2 text-sm focus-ring outline-none">
                  <option>XGBoost</option>
                  <option>Random Forest</option>
                </select>
              </div>
            </div>
            {batchResult && (
              <div className="card p-4 space-y-3">
                <div className="text-sm font-semibold">Summary</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Detected</div>
                    <div className="text-lg font-bold tabular">{batchResult.files_detected}</div>
                  </div>
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Scanned</div>
                    <div className="text-lg font-bold tabular">{batchResult.total_files_scanned}</div>
                  </div>
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Skipped</div>
                    <div className="text-lg font-bold tabular">{batchResult.files_skipped}</div>
                  </div>
                  <div className="bg-(--surface-3) rounded-lg p-2.5">
                    <div className="text-(--text-muted)">Vulnerable</div>
                    <div className="text-lg font-bold tabular text-(--status-critical)">{batchResult.vulnerable_count}</div>
                  </div>
                </div>
                {batchResult.skip_reasons.length > 0 && (
                  <div className="text-[11px] text-(--status-warning) bg-(--status-warning)/10 rounded-lg p-2">
                    {batchResult.skip_reasons.join("; ")}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}
