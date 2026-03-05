import { apiFetch } from "./client";
import type { ClipSuggestion, EditingPlan } from "../types";

export async function suggestClip(
  sessionId: string,
  clipIndex: number,
  currentPlan: EditingPlan,
  direction: string = "",
): Promise<{ suggestions: ClipSuggestion[] }> {
  return apiFetch("/api/suggest-clip", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      clip_index: clipIndex,
      current_plan: currentPlan,
      direction,
    }),
  });
}
