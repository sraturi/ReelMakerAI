import type { VideoInfo } from "../types";

export async function uploadVideos(
  files: File[],
  sessionId?: string,
  onProgress?: (pct: number) => void,
): Promise<{ session_id: string; videos: VideoInfo[] }> {
  const form = new FormData();
  for (const f of files) {
    form.append("videos", f);
  }
  if (sessionId) {
    form.append("session_id", sessionId);
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 400) {
          reject(new Error(data.error || `HTTP ${xhr.status}`));
        } else {
          resolve(data);
        }
      } catch {
        reject(new Error(`HTTP ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(form);
  });
}
