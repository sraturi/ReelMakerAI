import { apiFetch } from "./client";
import type { ClipSuggestion, EditingPlan } from "../types";

const CACHE_TTL = 60_000; // 60 seconds
const CACHE_MAX = 50;
const cache = new Map<string, { data: { suggestions: ClipSuggestion[] }; ts: number }>();

function cacheKey(sessionId: string, clipIndex: number, direction: string): string {
  return `${sessionId}:${clipIndex}:${direction}`;
}

export async function suggestClip(
  sessionId: string,
  clipIndex: number,
  currentPlan: EditingPlan,
  direction: string = "",
): Promise<{ suggestions: ClipSuggestion[] }> {
  const key = cacheKey(sessionId, clipIndex, direction);
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  const data = await apiFetch<{ suggestions: ClipSuggestion[] }>("/api/suggest-clip", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      clip_index: clipIndex,
      current_plan: currentPlan,
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
