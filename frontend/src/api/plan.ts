import { apiFetch } from "./client";
import type { SessionSettings } from "../types";

export async function startPlan(
  sessionId: string,
  settings: SessionSettings,
): Promise<{ job_id: string }> {
  return apiFetch("/api/plan", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, ...settings }),
  });
}

export async function startReplan(
  sessionId: string,
  direction: string,
  settings: SessionSettings,
): Promise<{ job_id: string }> {
  return apiFetch("/api/replan", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      direction,
      ...settings,
    }),
  });
}
