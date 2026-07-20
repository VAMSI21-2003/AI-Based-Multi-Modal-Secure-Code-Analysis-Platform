import { api } from "./client";

export interface CopilotResponse {
  answer: string;
  sources: string[];
  suggested: string[];
}

export const askCopilot = (question: string, scanId?: string) =>
  api.post<CopilotResponse>("/copilot/ask", { question, scan_id: scanId }).then((r) => r.data);
