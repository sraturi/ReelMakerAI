import { apiFetch } from "./client";
import type { CaptionSuggestion } from "../types";

const CACHE_TTL = 60_000; // 60 seconds
const CACHE_MAX = 50;
const cache = new Map<string, { data: { suggestions: CaptionSuggestion[] }; ts: number }>();

function cacheKey(sessionId: string, captionText: string, direction: string): string {
  return `${sessionId}:${captionText}:${direction}`;
}

export async function rewriteCaption(
  sessionId: string,
  captionText: string,
  context: string = "",
  direction: string = "",
): Promise<{ suggestions: CaptionSuggestion[] }> {
  const key = cacheKey(sessionId, captionText, direction);
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  const data = await apiFetch<{ suggestions: CaptionSuggestion[] }>("/api/rewrite-caption", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      caption_text: captionText,
      context,
      direction,
    }),
  });

  // Evict oldest if at capacity
  if (cache.size >= CACHE_MAX) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
  cache.set(key, { data, ts: Date.now() });

  return data;
}
