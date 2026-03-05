import { useCallback, useState } from "react";
import { Sparkles, AlertCircle } from "lucide-react";
import { UploadDropzone } from "./UploadDropzone";
import { VideoFileList } from "./VideoFileList";
import { SettingsPanel } from "../settings/SettingsPanel";
import { uploadVideos } from "../../api/upload";
import { startAnalyze } from "../../api/analyze";
import { startPlan } from "../../api/plan";
import { useSessionStore } from "../../store/useSessionStore";
import { useEditorStore } from "../../store/useEditorStore";
import { useUIStore } from "../../store/useUIStore";
import { useSSE } from "../../hooks/useSSE";

export function UploadPage() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const videos = useSessionStore((s) => s.videos);
  const settings = useSessionStore((s) => s.settings);
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const setVideos = useSessionStore((s) => s.setVideos);
  const setPlan = useSessionStore((s) => s.setPlan);
  const setAnalysis = useSessionStore((s) => s.setAnalysis);
  const setClips = useEditorStore((s) => s.setClips);
  const setOverlays = useEditorStore((s) => s.setOverlays);
  const setStep = useUIStore((s) => s.setStep);
  const setLoading = useUIStore((s) => s.setLoading);
  const setUploadProgress = useUIStore((s) => s.setUploadProgress);
  const setError = useUIStore((s) => s.setError);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const error = useUIStore((s) => s.error);
  const loading = useUIStore((s) => s.loading);

  const [analyzeJobId, setAnalyzeJobId] = useState<string | null>(null);
  const [planJobId, setPlanJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "analyzing" | "planning">("idle");

  // Handle analyze SSE completion → start plan
  useSSE(analyzeJobId, useCallback(async (data: string) => {
    try {
      const result = JSON.parse(data);
      setAnalysis(result.analysis);
      setAnalyzeJobId(null);

      // Chain to plan
      setPhase("planning");
      setLoading(true, "Creating editing plan...");
      const { job_id } = await startPlan(sessionId!, settings);
      setPlanJobId(job_id);
    } catch (e) {
      setError(String(e));
    }
  }, [sessionId, settings, setAnalysis, setLoading, setError]));

  // Handle plan SSE completion → go to editor
  useSSE(planJobId, useCallback((data: string) => {
    try {
      const plan = JSON.parse(data);
      setPlan(plan);
      setClips(plan.clips || []);
      setOverlays(plan.text_overlays || []);
      setPlanJobId(null);
      setPhase("idle");
      setStep("edit");
    } catch (e) {
      setError(String(e));
    }
  }, [setPlan, setClips, setOverlays, setStep, setError]));

  const handleFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      setPhase("uploading");
      setLoading(true, "Uploading videos...");
      setUploadProgress(0);
      try {
        const result = await uploadVideos(files, sessionId || undefined, (pct) => {
          setUploadProgress(pct);
        });
        setUploadProgress(null);
        setSessionId(result.session_id);
        setVideos(result.videos);  // API returns full accumulated list
        setLoading(false);
        setPhase("idle");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setPhase("idle");
      }
    },
    [sessionId, setSessionId, setVideos, setLoading, setUploadProgress, setError],
  );

  const handleAnalyzeAndPlan = useCallback(async () => {
    if (!sessionId || !settings.prompt.trim()) return;
    setError(null);
    clearLogs();
    setPhase("analyzing");
    setLoading(true, "Analyzing videos with AI...");
    try {
      const { job_id } = await startAnalyze(sessionId, settings.gemini_model);
      setAnalyzeJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("idle");
    }
  }, [sessionId, settings, clearLogs, setLoading, setError]);

  const canAnalyze = videos.length > 0 && settings.prompt.trim().length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create a Reel</h1>
        <p className="text-sm text-text-muted">
          Upload your videos, set your direction, and let AI generate an editing plan you can customize.
        </p>
      </div>

      <UploadDropzone onFiles={handleFiles} disabled={loading} />
      <VideoFileList videos={videos} />

      {videos.length > 0 && <SettingsPanel />}

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-error/10 p-3 text-sm text-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {videos.length > 0 && (
        <button
          onClick={handleAnalyzeAndPlan}
          disabled={!canAnalyze || loading}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3.5 text-base font-semibold text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Sparkles size={20} />
          {phase === "analyzing"
            ? "Analyzing Videos..."
            : phase === "planning"
              ? "Generating Plan..."
              : "Analyze & Generate Plan"}
        </button>
      )}
    </div>
  );
}
