import { apiFetch } from "./client";
import type { SessionSettings } from "../types";

export async function enhancePrompt(
  prompt: string,
  settings: SessionSettings,
): Promise<string> {
  const data = await apiFetch<{ enhanced_prompt: string }>("/api/enhance-prompt", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      reel_style: settings.reel_style,
      reel_approach: settings.reel_approach,
      target_duration: settings.target_duration,
      captions: settings.captions,
      audio_mode: settings.audio_mode,
      transition_style: settings.transition_style,
    }),
  });
  return data.enhanced_prompt;
}
