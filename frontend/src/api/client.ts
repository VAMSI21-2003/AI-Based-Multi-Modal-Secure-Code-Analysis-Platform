import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

// Scan-triggering calls (single-file, batch/ZIP/folder, GitHub, live) can
// legitimately run for minutes on a large real-world repo, well past the
// 120s default above. Configurable via VITE_SCAN_TIMEOUT_MS so this can be
// tuned per deployment without a code change; defaults to 20 minutes --
// bumped from 10 min after per-function inference
// (docs/PER_FUNCTION_INFERENCE_DESIGN.md) measured a real 200-file GitHub
// scan (curl) at 797.5s server-side, already past the old 10-minute default.
//
// This is a stopgap, not the real fix: a long-running scan is still one
// blocking HTTP request that ties up a connection and gives no progress
// feedback. The proper fix is an async job (submit -> poll status/progress
// -> fetch result when done) instead of one long request -- out of scope
// for this change.
const SCAN_TIMEOUT_MS = Number(import.meta.env.VITE_SCAN_TIMEOUT_MS) || 1_200_000;

// ── Types ────────────────────────────────────────────────────────────────

export interface ScanResult {
  id: string;
  batch_id: string | null;
  project_name: string;
  filename: string;
  source: string;
  verdict: "VULNERABLE" | "NOT VULNERABLE";
  vuln_probability: number;
  safe_probability: number;
  confidence: number;
  risk_level: string;
  risk_tag: string;
  risk_color: string;
  model_used: string;
  is_demo: boolean;
  ast_features: Record<string, number>;
  metric_features: Record<string, number>;
  embedding_dims: number;
  embedding_2d: { x: number; y: number } | null;
  lines: number;
  loc: number;
  is_pinned: boolean;
  tags: string[];
  created_at: string;
  code?: string;
  validation_message?: string;
  evidence_risk?: EvidenceRisk;
}

export interface EvidenceRisk {
  level: string;
  ml_level: string;
  evidence_level: string;
  escalated: boolean;
  max_finding_severity: number;
  reasons: { line: number; reason: string; cwe: string | null }[];
}

export interface LineRisk {
  line: number;
  code: string;
  severity: number;
  reasons: string[];
  cwe: string[];
}

export interface ScanDetail {
  id: string;
  insights: [string, string][];
  ast_tree: { available: boolean; tree: any | null; error?: string };
  line_risks: LineRisk[];
  recommendations: { title: string; tips: string[] }[];
  suggested_rewrite: { rewritten_code: string; changes: { description: string; occurrences: number }[]; changed: boolean; requires_manual_sizing?: boolean };
  contributions: { feature: string; value: number; importance: number; z_score: number; contribution: number; direction: string }[] | null;
  pca_background: { explained_variance_ratio: number[]; points: { x: number; y: number; label: number | null }[] } | null;
}

export interface DashboardStats {
  total_files_scanned: number;
  total_vulnerabilities: number;
  safe_count: number;
  risk_distribution: Record<string, number>;
  most_common_vulnerability: string | null;
  average_risk_percent: number;
  average_confidence_percent: number;
  recent_scans: ScanResult[];
  trend_14d: { date: string; scans: number; vulnerabilities: number }[];
  models_status: Record<string, { available: boolean; path: string }>;
}

export interface BatchResult {
  batch_id: string;
  total_files_submitted: number;
  files_detected: number;
  total_files_scanned: number;
  files_skipped: number;
  skip_reasons: string[];
  vulnerable_count: number;
  safe_count: number;
  results: ScanResult[];
}

export interface KnowledgeEntry {
  id: string;
  name: string;
  aka: string;
  severity: string;
  description: string;
  impact: string;
  vulnerable_example: string;
  secure_example: string;
  mitigation: string[];
  cve_examples: string[];
  cvss?: { score: number | null; vector: string | null };
  real_attacks?: string[];
  mitre_url?: string;
  owasp_url?: string;
}

// ── Calls ────────────────────────────────────────────────────────────────

export const scanCode = (payload: {
  code: string; project_name?: string; filename?: string; model_choice?: string; source?: string;
}) => api.post<ScanResult>("/scan/code", payload, { timeout: SCAN_TIMEOUT_MS }).then((r) => r.data);

export const scanBatch = (files: File[], project_name: string, model_choice: string, onProgress?: (pct: number) => void) => {
  const form = new FormData();
  form.append("project_name", project_name);
  form.append("model_choice", model_choice);
  files.forEach((f) => form.append("files", f, (f as any).webkitRelativePath || f.name));
  return api.post<BatchResult>("/scan/batch", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: SCAN_TIMEOUT_MS,
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
  }).then((r) => r.data);
};

export const getScan = (id: string) => api.get<ScanResult>(`/scan/${id}`).then((r) => r.data);
export const getScanDetail = (id: string) => api.get<ScanDetail>(`/scan/${id}/detail`).then((r) => r.data);
export const deleteScan = (id: string) => api.delete(`/scan/${id}`).then((r) => r.data);
export const rewriteCode = (code: string) =>
  api.post<{ rewritten_code: string; changes: any[]; changed: boolean }>("/scan/rewrite", { code }).then((r) => r.data);

export const getDashboardStats = () => api.get<DashboardStats>("/dashboard/stats").then((r) => r.data);

export const getHistory = (params: Record<string, any>) =>
  api.get("/history", { params }).then((r) => r.data as { total: number; results: ScanResult[]; projects: string[]; tags: string[] });

export const togglePin = (id: string) => api.patch<{ id: string; is_pinned: boolean }>(`/history/${id}/pin`).then((r) => r.data);
export const setScanTags = (id: string, tags: string[]) => api.patch<{ id: string; tags: string[] }>(`/history/${id}/tags`, { tags }).then((r) => r.data);
export const getPinnedScans = () => api.get<{ results: ScanResult[] }>("/history/pinned").then((r) => r.data.results);

export const getAnalyticsOverview = () => api.get("/analytics/overview").then((r) => r.data);
export const getModelPerformance = () => api.get("/analytics/model-performance").then((r) => r.data);
export const getDatasetStats = () => api.get("/analytics/dataset-stats").then((r) => r.data);
export const getPcaBackground = () => api.get("/analytics/pca-background").then((r) => r.data);

export interface SecurityTrendPoint { date: string; avg_risk: number; avg_confidence: number; avg_complexity: number; dangerous_apis: number; scans: number; }
export const getSecurityTrends = (days = 14) => api.get<{ trend: SecurityTrendPoint[] }>("/analytics/trends", { params: { days } }).then((r) => r.data.trend);
export const getFeatureRadarAvg = () => api.get("/analytics/feature-radar").then((r) => r.data as { available: boolean; sample_size?: number; ast_features: Record<string, number>; metric_features: Record<string, number> });

export const getKnowledgeBase = () => api.get<{ entries: KnowledgeEntry[] }>("/knowledge").then((r) => r.data.entries);
export const getKnowledgeEntry = (cwe: string) => api.get<KnowledgeEntry>(`/knowledge/${cwe}`).then((r) => r.data);

// ── Code Intelligence ("AI Code Explanation") ──────────────────────────────

export interface FunctionInfo {
  name: string;
  return_type: string;
  parameters: { name: string; type: string; is_pointer: boolean }[];
  start_line: number;
  loc: number;
  cyclomatic_complexity: number;
  max_nesting: number;
  maintainability_index: number;
  halstead_volume: number;
  loop_count: number;
  pointer_ops: number;
  condition_count: number;
  call_count: number;
  calls: string[];
  is_recursive: boolean;
  dangerous_apis: string[];
  global_refs?: string[];
  summary: string;
}

export interface GraphNode { id: string; label: string; type?: string; kind?: string; line?: number | null; }
export interface GraphEdge { source: string; target: string; label?: string | null; }

export interface CodeIntelligence {
  available: boolean;
  error?: string;
  file_summary: string;
  functions: FunctionInfo[];
  function_count: number;
  global_variables?: string[];
  dangerous_apis: { api: string; line: number; severity: number; cwe: string | null; description: string | null; count: number }[];
  memory: {
    allocations: number; frees: number; balance: number; potential_leak: boolean; potential_double_free_risk: boolean;
    alloc_sites: { api: string; line: number }[]; free_sites: { line: number }[];
    stack_buffers: { name: string; size: number; line: number }[];
    variable_length_arrays: { name: string; expression: string; line: number }[];
    stack_bytes_estimate: number;
  };
  pointers: { pointer_variables: number; dereferences: number; double_pointers: number; null_checks: number; null_check_coverage_pct: number };
  buffers: { name: string; declared_size: string; line: number; nearby_risk_lines: number[] }[];
  loops: { type: string; line: number; nesting_depth: number; condition_preview: string; has_break: boolean; possibly_infinite: boolean }[];
  call_graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  cfg: { function: string | null; available_functions: string[]; nodes: GraphNode[]; edges: GraphEdge[] };
  variables: { total_declared: number; parameters: number; locals: number; by_type: Record<string, number>; most_mutated: { name: string; count: number }[] };
  scores: {
    quality: number; maintainability_index: number; security_score: number; performance_score: number;
    cyclomatic_complexity_total: number; cyclomatic_complexity_avg?: number;
  };
  dead_code: string[];
  critical_nodes: string[];
  code_smells: {
    unused_variables: { name: string; line: number }[];
    unreachable_code: { line: number; after_line: number }[];
    shadow_variables: { name: string; outer_line: number; inner_line: number }[];
    long_parameter_lists: { function: string; count: number }[];
    large_functions: { function: string; loc: number }[];
    deep_nesting: { function: string; depth: number }[];
    magic_numbers: { line: number; value: string }[];
    duplicate_code: { snippet: string; lines: number[] }[];
    total_findings: number;
  };
}

export const getCodeIntelligence = (scanId: string, cfgFunction?: string) =>
  api.get<CodeIntelligence>(`/scan/${scanId}/intelligence`, { params: cfgFunction ? { function: cfgFunction } : {} }).then((r) => r.data);

// ── Optimization Suggestions (heuristic, not ML-derived -- see
// docs/OPTIMIZATION_SUGGESTIONS_DESIGN.md) ─────────────────────────────────

export interface OptimizationFindings {
  available: boolean;
  heuristic_based: boolean;
  error?: string;
  loop_invariant_length_calls: { line: number; loop_type: string; variable: string; expression: string; message: string }[];
  string_growth_in_loop: { line: number; api: string; destination: string; loop_line: number; message: string }[];
  linear_realloc_growth: { line: number; size_expression: string; loop_line: number; message: string }[];
  heap_alloc_in_loop: { loop_line: number; loop_type: string; allocation_count: number; allocations: { api: string; line: number }[]; message: string }[];
  large_struct_by_value: { function: string; parameter: string; struct_name: string; member_count: number; line: number; message: string }[];
  total_findings: number;
}

export const getOptimizationFindings = (scanId: string) =>
  api.get<OptimizationFindings>(`/scan/${scanId}/optimization`).then((r) => r.data);

// ── System Monitor ──────────────────────────────────────────────────────────

export interface SystemStats {
  cpu_percent: number;
  process_cpu_percent: number;
  ram_percent: number;
  ram_used_mb: number;
  ram_total_mb: number;
  process_ram_mb: number;
  model_load_times_sec: Record<string, number>;
  avg_prediction_latency_ms: number | null;
  recent_prediction_latencies_ms: number[];
  prediction_count_tracked: number;
  files_scanned_total: number;
  uptime_sec: number;
}

export const getSystemStats = () => api.get<SystemStats>("/system/stats").then((r) => r.data);

// ── Model Comparison ─────────────────────────────────────────────────────────

export interface ModelComparison {
  available: boolean;
  error?: string;
  xgboost: { available: boolean; verdict?: string; vuln_probability?: number; confidence?: number } | null;
  random_forest: { available: boolean; verdict?: string; vuln_probability?: number; confidence?: number } | null;
  agreement: boolean | null;
  probability_diff: number | null;
}

export const getModelComparison = (scanId: string) =>
  api.get<ModelComparison>(`/scan/${scanId}/model-comparison`).then((r) => r.data);

// ── Project Scanner / Security Risk Map ──────────────────────────────────────

export interface ProjectSummary {
  batch_id: string;
  project_name: string;
  created_at: string;
  total_files: number;
  safe_files: number;
  vulnerable_files: number;
  highest_risk_file: ScanResult | null;
  security_score: number;
  risk_distribution: Record<string, number>;
  function_count?: number;
  most_dangerous_apis?: { api: string; count: number }[];
  most_common_cwe?: { cwe: string; count: number; name: string }[];
  total_loc?: number;
  avg_confidence?: number;
  avg_maintainability?: number | null;
  most_dangerous_folder?: { folder: string; avg_risk: number; worst_risk: string; file_count: number } | null;
  most_dangerous_function?: { name: string; file: string; dangerous_api_count: number; complexity: number } | null;
  finding_severity_counts?: { critical: number; high: number; medium: number; low: number };
  scan_duration_sec?: number;
  files: ScanResult[];
}

export const getProjectSummary = (batchId: string) =>
  api.get<ProjectSummary>(`/project/${batchId}/summary`).then((r) => r.data);

// ── Dependency Graph (Phase 7) ───────────────────────────────────────────────

export interface DependencyFileNode { id: string; label: string; type: "file"; risk_level: string; vuln_probability: number; }
export interface DependencyFileEdge { source: string; target: string; label?: string | null; }
export interface DependencyFunctionNode {
  id: string; label: string; type: string; file: string; kind: "dangerous" | "complex" | "normal"; risk_level: string;
  pointer_ops?: number; global_refs?: string[]; is_recursive?: boolean; loc?: number; dangerous_apis?: string[];
}
export interface DependencyFunctionEdge { source: string; target: string; label?: string | null; cross_file: boolean; }

export interface DependencyGraph {
  batch_id: string;
  project_name: string;
  file_nodes: DependencyFileNode[];
  file_edges: DependencyFileEdge[];
  file_cycles: string[][];
  function_nodes: DependencyFunctionNode[];
  function_edges: DependencyFunctionEdge[];
  function_cycles: string[][];
  stats: { total_files: number; total_functions: number; cross_file_edges: number; file_cycles_detected: number; function_cycles_detected: number };
  note: string;
}

export const getDependencyGraph = (batchId: string) =>
  api.get<DependencyGraph>(`/project/${batchId}/dependency-graph`).then((r) => r.data);

// ── Watch Mode (Phase 4) ──────────────────────────────────────────────────────

export interface WatchEvent {
  type: "initial" | "created" | "modified" | "deleted" | "error";
  filename: string;
  scan_id: string | null;
  verdict: string | null;
  risk_level: string | null;
  vuln_probability: number | null;
  timestamp: string;
  seq: number;
  error?: string;
}

export interface WatchScore { total_files: number; vulnerable_files: number; safe_files: number; security_score: number; total_scans_recorded: number; }

export interface WatchSession {
  session_id: string; path: string; project_name: string; status: "running" | "stopped";
  created_at: string; batch_id: string; score: WatchScore;
}

export interface WatchEventsResponse {
  session_id: string; status: "running" | "stopped"; path: string; project_name: string; batch_id: string;
  events: WatchEvent[]; next_since: number; score: WatchScore;
}

export const startWatch = (path: string, projectName: string) =>
  api.post<{ session_id: string; path: string; project_name: string; initial_files_scanned: number }>("/watch/start", { path, project_name: projectName }).then((r) => r.data);

export const stopWatch = (sessionId: string) =>
  api.post<{ session_id: string; status: string }>(`/watch/${sessionId}/stop`).then((r) => r.data);

export const listWatchSessions = () => api.get<WatchSession[]>("/watch/sessions").then((r) => r.data);

export const getWatchEvents = (sessionId: string, since: number) =>
  api.get<WatchEventsResponse>(`/watch/${sessionId}/events`, { params: { since } }).then((r) => r.data);

export const getWatchDiff = (sessionId: string, filename: string) =>
  api.get<{
    filename: string;
    current: { scan_id: string; code: string; verdict: string; risk_level: string; created_at: string };
    previous: { scan_id: string; code: string; verdict: string; risk_level: string; created_at: string } | null;
  }>(`/watch/${sessionId}/diff/${encodeURIComponent(filename)}`).then((r) => r.data);

// ── GitHub Mode (Phase 6) ─────────────────────────────────────────────────────

export interface GitHubScanResult {
  batch_id: string; repo_url: string; repo_name?: string; project_name: string;
  branch?: string | null; commit_sha?: string | null;
  files_scanned: number; files_found: number; files_detected?: number;
  files_skipped?: number; skip_reasons?: string[]; commits_recorded: number;
}
export interface GitHubCommit { hash: string; author: string; date: string; message: string; }

export const scanGitHubRepo = (repoUrl: string, projectName?: string) =>
  api.post<GitHubScanResult>("/github/scan", { repo_url: repoUrl, project_name: projectName || undefined }, { timeout: SCAN_TIMEOUT_MS }).then((r) => r.data);

export interface GitHubBatchMeta {
  batch_id: string; repo_url: string; repo_name: string; branch: string | null; commit_sha: string | null;
  files_detected: number; files_analyzed: number; files_skipped: number; skip_reasons: string[];
  scanned_at: string | null;
}
export const getGitHubBatchMeta = (batchId: string) =>
  api.get<GitHubBatchMeta>(`/github/${batchId}/meta`).then((r) => r.data);

export const getGitHubCommits = (batchId: string) =>
  api.get<{ batch_id: string; commits: GitHubCommit[] }>(`/github/${batchId}/commits`).then((r) => r.data.commits);

// ── Research page ────────────────────────────────────────────────────────────

export interface EvalCurveModel {
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
  roc_curve: { fpr: number[]; tpr: number[]; auc: number };
  pr_curve: { recall: number[]; precision: number[] };
  feature_importances_top20: { feature: string; importance: number }[];
  ablation?: { config: string; accuracy: number; precision: number; recall: number; f1: number }[];
}

export interface EvalCurves {
  available: boolean;
  xgboost?: EvalCurveModel;
  random_forest?: EvalCurveModel;
  test_set_size?: number;
  test_set_vulnerable?: number;
  test_set_safe?: number;
}

export interface ModelArchitecture {
  codebert: { model_name: string; parameters: number | null; layers: number; hidden_size: number; attention_heads: number; max_sequence_length: number };
  xgboost: { n_estimators: number; max_depth: number | null; learning_rate: number | null; total_trees: number } | null;
  random_forest: { n_estimators: number; max_depth: number | null; total_trees: number; total_nodes: number } | null;
  feature_pipeline: { ast_dimensions: number; metrics_dimensions: number; embedding_dimensions: number; total_dimensions: number };
  training: any;
}

export const getEvalCurves = () => api.get<EvalCurves>("/research/eval-curves").then((r) => r.data);
export const getModelArchitecture = () => api.get<ModelArchitecture>("/research/architecture", { timeout: 60000 }).then((r) => r.data);

export const getBatches = () => api.get("/scan/batches/list").then((r) => r.data as {
  batch_id: string; project_name: string; total_files: number; vulnerable_files: number; created_at: string;
}[]);

export const downloadScanPdf = (id: string) => `/api/report/pdf/${id}`;
export const downloadExecutivePdf = (id: string) => `/api/export/pdf/executive/${id}`;
export const downloadDeveloperPdf = (id: string) => `/api/export/pdf/developer/${id}`;
export const downloadHtmlReport = (id: string) => `/api/export/html/${id}`;
export const downloadResearchPdf = () => `/api/export/pdf/research`;
export const downloadWordReport = (id: string) => `/api/export/docx/${id}`;
export const downloadPptxReport = (id: string) => `/api/export/pptx/${id}`;
export const downloadBatchPdf = (batchId: string) => `/api/report/pdf/batch/${batchId}`;
export const exportHistoryUrl = (format: "csv" | "json", params: Record<string, any> = {}) => {
  const qs = new URLSearchParams({ format, ...params }).toString();
  return `/api/history/export?${qs}`;
};

// ── Security Gamification (Phase 3, #17) ──────────────────────────────────────

export interface GamificationTier { name: string; min_score: number; color: string; }
export interface GamificationBadge { id: string; name: string; description: string; icon: string; earned: boolean; progress: number; target: number; }
export interface GamificationStatus {
  total_scans: number; vulnerable_scans?: number; security_score: number; days_active?: number; clean_streak?: number;
  tier: GamificationTier; next_tier: GamificationTier | null; progress_to_next: number;
  badges: GamificationBadge[]; badges_earned: number; badges_total: number;
}
export const getGamificationStatus = () => api.get<GamificationStatus>("/gamification/status").then((r) => r.data);

// ── Vulnerability Search Engine (Phase 3, #18) ────────────────────────────────

export type SearchCategory = "all" | "cwe" | "api" | "function" | "variable" | "pointer" | "loop" | "risk";
export interface SearchMatch { kind: string; line: number | null; detail: string; cwe: string[]; }
export interface SearchResultItem { scan_id: string; filename: string; project_name: string; risk_level: string; verdict: string; created_at: string; matches: SearchMatch[]; }
export interface SearchResponse { query: string; category: SearchCategory; scanned: number; results: SearchResultItem[]; }
export const searchVulnerabilities = (q: string, category: SearchCategory = "all") =>
  api.get<SearchResponse>("/search", { params: { q, category } }).then((r) => r.data);

// ── Code Health (memory/buffer/pointer/leak dashboard counters) ──────────────

export interface CodeHealth { available: boolean; files_analyzed: number; functions_analyzed: number; memory_issues: number; buffer_issues: number; pointer_issues: number; leaks: number; total_dangerous_apis: number; }
export const getCodeHealth = () => api.get<CodeHealth>("/analytics/code-health").then((r) => r.data);

// ── Enterprise PDF Report ─────────────────────────────────────────────────────

export const downloadEnterprisePdf = (scanId: string) => `/api/export/pdf/enterprise/${scanId}`;
export const downloadEnterpriseProjectPdf = (batchId: string) => `/api/export/pdf/enterprise-project/${batchId}`;

// ── Live Monaco IDE (no-persist live analysis) ────────────────────────────────

export interface LiveScanResult {
  valid: boolean;
  validation_message?: string;
  verdict?: "VULNERABLE" | "NOT VULNERABLE";
  vuln_probability?: number;
  safe_probability?: number;
  confidence?: number;
  risk_level?: string;
  risk_tag?: string;
  risk_color?: string;
  model_used?: string;
  is_demo?: boolean;
  ast_features?: Record<string, number>;
  metric_features?: Record<string, number>;
  insights?: [string, string][];
  line_risks?: LineRisk[];
  intelligence?: CodeIntelligence;
  recommendations?: { title: string; tips: string[] }[];
  suggested_rewrite?: { rewritten_code: string; changed: boolean; changes: { description: string; occurrences: number }[]; requires_manual_sizing?: boolean };
  contributions?: { feature: string; value: number; importance: number; z_score: number; contribution: number; direction: string }[] | null;
}

export const scanLive = (code: string, modelChoice = "XGBoost") =>
  api.post<LiveScanResult>("/scan/live", { code, model_choice: modelChoice }, { timeout: SCAN_TIMEOUT_MS }).then((r) => r.data);

// ── Security Knowledge Graph ──────────────────────────────────────────────────

export type KnowledgeNodeKind = "repository" | "folder" | "file" | "function" | "cwe" | "dangerous_api" | "pointer" | "buffer" | "memory" | "variable" | "prediction";
export interface KnowledgeNode { id: string; label: string; kind: KnowledgeNodeKind; [key: string]: any; }
export interface KnowledgeEdge { source: string; target: string; relation: "contains" | "calls" | "uses" | "reads" | "writes" | "allocates" | "frees" | "causes" | "related_to"; }
export interface KnowledgeGraphResponse {
  batch_id: string; project_name: string; nodes: KnowledgeNode[]; edges: KnowledgeEdge[]; kind_counts: Record<string, number>;
}
export const getKnowledgeGraph = (batchId: string) =>
  api.get<KnowledgeGraphResponse>(`/project/${batchId}/knowledge-graph`).then((r) => r.data);

// ── Platform files (Docker / CI-CD tabs, Phase 5) ─────────────────────────────

export interface PlatformFile { path: string; exists: boolean; content: string | null; }
export const getPlatformFiles = () => api.get<Record<string, PlatformFile>>("/system/platform-files").then((r) => r.data);

// ── Enterprise Security Scorecard ─────────────────────────────────────────────

export interface ScorecardFactor { id: string; label: string; weight: number; score: number; grade: string; }
export interface Scorecard {
  available: boolean; overall_score: number; grade: string; factors: ScorecardFactor[];
  total_scans: number; vulnerable_files?: number; critical_files?: number; generated: string;
}
export const getScorecard = () => api.get<Scorecard>("/analytics/scorecard").then((r) => r.data);
