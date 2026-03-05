import type { VideoInfo } from "../types";

export async function uploadVideos(
  files: File[],
  sessionId?: string,
): Promise<{ session_id: string; videos: VideoInfo[] }> {
  const form = new FormData();
  for (const f of files) {
    form.append("videos", f);
  }
  if (sessionId) {
    form.append("session_id", sessionId);
  }
  const res = await fetch("/api/upload", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}
