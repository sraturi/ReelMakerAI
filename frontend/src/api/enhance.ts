import { apiFetch } from "./client";
import type { SessionSettings } from "../types";

const CACHE_TTL = 60_000; // 60 seconds
const CACHE_MAX = 50;
const cache = new Map<string, { data: string; ts: number }>();

function cacheKey(prompt: string, style: string, approach: string, duration: number): string {
  return `${prompt}:${style}:${approach}:${duration}`;
}

export async function enhancePrompt(
  prompt: string,
  settings: SessionSettings,
  sessionId?: string,
): Promise<string> {
  const key = cacheKey(prompt, settings.reel_style, settings.reel_approach, settings.target_duration);
  const cached = cache.get(key);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  const data = await apiFetch<{ enhanced_prompt: string }>("/api/enhance-prompt", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      session_id: sessionId,
      reel_style: settings.reel_style,
      reel_approach: settings.reel_approach,
      target_duration: settings.target_duration,
      captions: settings.captions,
      audio_mode: settings.audio_mode,
      transition_style: settings.transition_style,
    }),
  });

  // Evict oldest if at capacity
  if (cache.size >= CACHE_MAX) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
  cache.set(key, { data: data.enhanced_prompt, ts: Date.now() });

  return data.enhanced_prompt;
}
