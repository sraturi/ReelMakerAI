import { useEffect, useState, useRef } from "react";
import {
  Plus,
  Play,
  Trash2,
  Clock,
  Film,
  FileVideo,
  ArrowRight,
  X,
} from "lucide-react";
import { fetchHomeData, deleteProject, startNewProject } from "../../api/project";
import { apiFetch } from "../../api/client";
import { useUIStore } from "../../store/useUIStore";
import { useSessionStore } from "../../store/useSessionStore";
import { useEditorStore } from "../../store/useEditorStore";
import type { CompletedProject, DraftInfo, Step } from "../../types";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function HomePage() {
  const [projects, setProjects] = useState<CompletedProject[]>([]);
  const [draft, setDraft] = useState<DraftInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const setStep = useUIStore((s) => s.setStep);
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const setVideos = useSessionStore((s) => s.setVideos);
  const setAnalysis = useSessionStore((s) => s.setAnalysis);
  const setPlan = useSessionStore((s) => s.setPlan);
  const updateSettings = useSessionStore((s) => s.updateSettings);
  const resetSession = useSessionStore((s) => s.reset);
  const setClips = useEditorStore((s) => s.setClips);
  const setOverlays = useEditorStore((s) => s.setOverlays);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const setRenderOutput = useUIStore((s) => s.setRenderOutput);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const data = await fetchHomeData();
      setProjects(data.projects);
      setDraft(data.draft);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function handleNewProject() {
    try {
      await startNewProject();
    } catch {
      // ignore
    }
    resetSession();
    clearLogs();
    setRenderOutput(null);
    setStep("upload");
  }

  async function handleResumeDraft() {
    if (!draft) return;
    try {
      const session = await apiFetch<{
        session_id: string;
        videos: any[];
        analysis: any;
        plan: any;
        settings: any;
      }>(`/api/session/${draft.session_id}`);

      setSessionId(session.session_id);
      if (session.videos?.length) setVideos(session.videos);
      if (session.analysis) setAnalysis(session.analysis);
      if (session.plan) {
        setPlan(session.plan);
        setClips(session.plan.clips || []);
        setOverlays(session.plan.text_overlays || []);
      }
      if (session.settings) updateSettings(session.settings);

      // Navigate to the furthest step
      let target: Step = "upload";
      if (session.videos?.length) target = "upload";
      if (session.analysis) target = "prompt";
      if (session.plan) target = "edit";
      if (session.settings?.prompt) target = target === "upload" ? "prompt" : target;
      setStep(target);
    } catch {
      // Session expired, clear draft
      setDraft(null);
    }
  }

  async function handleDiscardDraft() {
    if (!confirm("Discard your current draft? This cannot be undone.")) return;
    await handleNewProject();
    await loadData();
  }

  async function handleDeleteProject(projectId: string) {
    if (!confirm("Delete this reel permanently?")) return;
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const isEmpty = projects.length === 0 && !draft;

  return (
    <div className="space-y-8 py-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Your Reels</h1>
        <button
          onClick={handleNewProject}
          className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 font-semibold text-white transition-colors hover:bg-primary-hover"
        >
          <Plus size={18} />
          New Project
        </button>
      </div>

      {/* Draft Card */}
      {draft && draft.video_count > 0 && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/20">
                <FileVideo className="text-primary" size={20} />
              </div>
              <div>
                <h3 className="font-semibold text-text">Draft in Progress</h3>
                <p className="text-sm text-text-muted">
                  {draft.video_count} video{draft.video_count !== 1 ? "s" : ""}
                  {draft.has_analysis && " \u00b7 Analyzed"}
                  {draft.has_plan && " \u00b7 Plan ready"}
                  {draft.prompt && ` \u00b7 "${draft.prompt.slice(0, 40)}${draft.prompt.length > 40 ? "..." : ""}"`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDiscardDraft}
                className="rounded-lg px-4 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-surface-light hover:text-red-400"
              >
                Discard
              </button>
              <button
                onClick={handleResumeDraft}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
              >
                Resume
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-light">
            <Film className="text-text-muted" size={32} />
          </div>
          <h2 className="mb-2 text-lg font-semibold text-text">No reels yet</h2>
          <p className="mb-6 max-w-sm text-text-muted">
            Upload your videos and let AI create an engaging reel for you.
          </p>
          <button
            onClick={handleNewProject}
            className="flex items-center gap-2 rounded-xl bg-primary px-6 py-3 font-semibold text-white transition-colors hover:bg-primary-hover"
          >
            <Plus size={18} />
            Create Your First Reel
          </button>
        </div>
      )}

      {/* Project Grid */}
      {projects.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              onPlay={() =>
                setPlayingId(
                  playingId === project.project_id ? null : project.project_id,
                )
              }
              onDelete={() => handleDeleteProject(project.project_id)}
            />
          ))}
        </div>
      )}

      {/* Video Player Modal */}
      {playingId && (
        <VideoModal
          project={projects.find((p) => p.project_id === playingId)!}
          onClose={() => setPlayingId(null)}
        />
      )}
    </div>
  );
}

function ProjectCard({
  project,
  onPlay,
  onDelete,
}: {
  project: CompletedProject;
  onPlay: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-surface transition-shadow hover:shadow-lg">
      {/* Thumbnail */}
      <div
        className="relative aspect-[9/16] cursor-pointer bg-black"
        onClick={onPlay}
      >
        <img
          src={project.thumbnail_url}
          alt={project.name}
          className="h-full w-full object-cover"
          loading="lazy"
        />
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/90">
            <Play className="text-black" size={20} fill="black" />
          </div>
        </div>
        {/* Duration badge */}
        <div className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white">
          {formatDuration(project.duration)}
        </div>
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="truncate text-sm font-medium text-text" title={project.name}>
          {project.name}
        </p>
        <div className="mt-1 flex items-center justify-between">
          <span className="flex items-center gap-1 text-xs text-text-muted">
            <Clock size={11} />
            {formatDate(project.created_at)}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="rounded p-1 text-text-muted opacity-0 transition-opacity hover:bg-red-500/20 hover:text-red-400 group-hover:opacity-100"
            title="Delete"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function VideoModal({
  project,
  onClose,
}: {
  project: CompletedProject;
  onClose: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="relative w-full max-w-sm">
        <button
          onClick={onClose}
          className="absolute -right-2 -top-10 rounded-full bg-white/10 p-1.5 text-white transition-colors hover:bg-white/20"
        >
          <X size={18} />
        </button>
        <div className="overflow-hidden rounded-xl bg-black shadow-2xl">
          <video
            src={project.output_url}
            controls
            autoPlay
            className="aspect-[9/16] w-full"
          />
        </div>
        <p className="mt-3 text-center text-sm font-medium text-white/80">
          {project.name}
        </p>
      </div>
    </div>
  );
}
