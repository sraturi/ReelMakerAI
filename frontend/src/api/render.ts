import { apiFetch } from "./client";
import type { EditingPlan } from "../types";

export async function startRender(
  sessionId: string,
  plan: EditingPlan,
  audioMode: string = "voice",
  transitionStyle: string = "auto",
): Promise<{ job_id: string }> {
  return apiFetch("/api/render", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      plan,
      audio_mode: audioMode,
      transition_style: transitionStyle,
    }),
  });
}
