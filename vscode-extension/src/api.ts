// =============================================================================
// api.ts -- thin client over the EXISTING SecureCode AI FastAPI backend.
// Uses the same endpoints as the web frontend (backend/routers/*.py) --
// nothing new is added on the backend for the extension to work. Requires
// the backend process to be running (see backend/main.py) and reachable at
// the configured `securecodeAi.backendUrl`.
// =============================================================================

import * as vscode from "vscode";

export interface LineRisk {
  line: number;
  code: string;
  severity: number; // 0-4
  reasons: string[];
  cwe: string[];
}

export interface ScanResult {
  id: string;
  filename: string;
  verdict: "VULNERABLE" | "NOT VULNERABLE";
  vuln_probability: number;
  confidence: number;
  risk_level: string;
  risk_tag: string;
  model_used: string;
}

export interface ScanDetail {
  id: string;
  line_risks: LineRisk[];
  suggested_rewrite: { rewritten_code: string; changed: boolean; changes: { description: string; occurrences: number }[] };
}

function backendUrl(): string {
  return vscode.workspace.getConfiguration("securecodeAi").get<string>("backendUrl", "http://127.0.0.1:8000").replace(/\/+$/, "");
}

export function frontendUrl(): string {
  return vscode.workspace.getConfiguration("securecodeAi").get<string>("frontendUrl", "http://localhost:5173").replace(/\/+$/, "");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${backendUrl()}${path}`;
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    throw new Error(
      `Could not reach the SecureCode AI backend at ${backendUrl()}. Is it running? ` +
      `(uvicorn main:app --port 8000, from the backend/ directory). ${e instanceof Error ? e.message : String(e)}`,
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Backend returned ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export async function scanCode(code: string, filename: string, projectName: string): Promise<ScanResult> {
  return request<ScanResult>("/api/scan/code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, filename, project_name: projectName, model_choice: "XGBoost", source: "vscode-extension" }),
  });
}

export async function getScanDetail(scanId: string): Promise<ScanDetail> {
  return request<ScanDetail>(`/api/scan/${scanId}/detail`);
}

export async function scanProjectFolder(files: { name: string; content: string }[], projectName: string) {
  const form = new FormData();
  form.set("project_name", projectName);
  form.set("model_choice", "XGBoost");
  for (const f of files) {
    form.append("files", new Blob([f.content], { type: "text/plain" }), f.name);
  }
  const url = `${backendUrl()}/api/scan/batch`;
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Backend returned ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json() as Promise<{ batch_id: string; total_files_scanned: number; vulnerable_count: number; safe_count: number }>;
}

export function developerPdfUrl(scanId: string): string {
  return `${backendUrl()}/api/export/pdf/developer/${scanId}`;
}
