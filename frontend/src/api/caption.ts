import { apiFetch } from "./client";
import type { CaptionSuggestion } from "../types";

export async function rewriteCaption(
  sessionId: string,
  captionText: string,
  context: string = "",
  direction: string = "",
): Promise<{ suggestions: CaptionSuggestion[] }> {
  return apiFetch("/api/rewrite-caption", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      caption_text: captionText,
      context,
      direction,
    }),
  });
}
