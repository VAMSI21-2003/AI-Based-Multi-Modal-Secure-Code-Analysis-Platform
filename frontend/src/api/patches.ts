import { api } from "./client";

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
}

export interface PatchResponse {
  detected: PatchCard[];
  reference: PatchCard[];
  detected_count: number;
}

export const getPatches = (scanId: string) => api.get<PatchResponse>(`/scan/${scanId}/patches`).then((r) => r.data);
