import { api } from "./client";
import type { ScanResult } from "./client";

export interface PatchCard {
  id: string;
  category: string;
  cwe: string | null;
  title: string;
  line: number | null;
  original_code: string;
  fixed_code: string;
  explanation: string;
  why_safer: string;
  detected: boolean;
  size_known: boolean;
}

export interface PatchResponse {
  detected: PatchCard[];
  reference: PatchCard[];
  detected_count: number;
}

export const getPatches = (scanId: string) => api.get<PatchResponse>(`/scan/${scanId}/patches`).then((r) => r.data);

// ── Apply-Patch -> Re-Scan loop (docs/APPLY_PATCH_LOOP_DESIGN.md) ──────────

export interface ApplyPatchChange { description: string; occurrences: number }

export interface ApplyPatchResult {
  applied: true;
  patch_id: string | null;
  original_scan_id: string;
  derived_scan_id: string;
  changes: ApplyPatchChange[];
  original: ScanResult;
  derived: ScanResult;
}

// Shape of the FastAPI 422 response body's `detail` when the apply is
// blocked (destination capacity unknown/placeholder) -- see
// routers/patches.py::apply_patch.
export interface ApplyPatchBlocked {
  blocked: true;
  reason: string;
  note: string;
  changes: ApplyPatchChange[];
}

export const applyPatch = (scanId: string, patchId?: string | null) =>
  api.post<ApplyPatchResult>(`/scan/${scanId}/apply-patch`, { patch_id: patchId ?? null }).then((r) => r.data);
