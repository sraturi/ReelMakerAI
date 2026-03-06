import { apiFetch } from "./client";
import type { HomeData } from "../types";

export function fetchHomeData(): Promise<HomeData> {
  return apiFetch<HomeData>("/api/projects");
}

export function deleteProject(projectId: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function startNewProject(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/projects/new", {
    method: "POST",
  });
}
