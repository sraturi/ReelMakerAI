import { apiFetch } from "./client";

export async function startAnalyze(
  sessionId: string,
  geminiModel: string = "gemini-2.5-flash",
): Promise<{ job_id: string }> {
  return apiFetch("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, gemini_model: geminiModel }),
  });
}
