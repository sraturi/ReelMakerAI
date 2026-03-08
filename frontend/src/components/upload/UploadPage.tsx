import { useCallback, useState } from "react";
import { Sparkles, AlertCircle } from "lucide-react";
import { UploadDropzone } from "./UploadDropzone";
import { VideoFileList } from "./VideoFileList";
import { uploadVideos, deleteVideo } from "../../api/upload";
import { startAnalyze } from "../../api/analyze";
import { useSessionStore } from "../../store/useSessionStore";
import { useUIStore } from "../../store/useUIStore";
import { useJobStatus } from "../../hooks/useJobStatus";

export function UploadPage() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const videos = useSessionStore((s) => s.videos);
  const settings = useSessionStore((s) => s.settings);
  const updateSettings = useSessionStore((s) => s.updateSettings);
  const setSessionId = useSessionStore((s) => s.setSessionId);
  const setVideos = useSessionStore((s) => s.setVideos);
  const setAnalysis = useSessionStore((s) => s.setAnalysis);
  const setStep = useUIStore((s) => s.setStep);
  const setLoading = useUIStore((s) => s.setLoading);
  const setUploadProgress = useUIStore((s) => s.setUploadProgress);
  const setError = useUIStore((s) => s.setError);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const error = useUIStore((s) => s.error);
  const loading = useUIStore((s) => s.loading);

  const [analyzeJobId, setAnalyzeJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "analyzing">("idle");

  const handleCancelled = useCallback(() => {
    setAnalyzeJobId(null);
    setPhase("idle");
  }, []);

  const handleAnalyzeDone = useCallback((data: unknown) => {
    try {
      const result = data as { analysis: unknown };
      setAnalysis(result.analysis);
      setAnalyzeJobId(null);
      setPhase("idle");
      setStep("prompt");
    } catch (e) {
      setError(String(e));
    }
  }, [setAnalysis, setStep, setError]);

  const cancel = useJobStatus(analyzeJobId, handleAnalyzeDone, handleCancelled);

  const handleFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      setPhase("uploading");
      setLoading(true, "Uploading videos...");
      setUploadProgress(0);
      try {
        const result = await uploadVideos(files, sessionId || undefined, (pct) => {
          setUploadProgress(pct);
          if (pct >= 100) {
            setLoading(true, "Processing videos...");
            setUploadProgress(null);
          }
        });
        setUploadProgress(null);
        setSessionId(result.session_id);
        setVideos(result.videos);
        setLoading(false);
        setPhase("idle");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setPhase("idle");
      }
    },
    [sessionId, setSessionId, setVideos, setLoading, setUploadProgress, setError],
  );

  const handleCancel = useCallback(() => {
    cancel();
    setAnalyzeJobId(null);
    setPhase("idle");
    setLoading(false);
  }, [cancel, setLoading]);

  const handleRemoveVideo = useCallback(async (index: number) => {
    if (!sessionId) return;
    try {
      const result = await deleteVideo(sessionId, index);
      setVideos(result.videos);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [sessionId, setVideos, setError]);

  const handleAnalyze = useCallback(async () => {
    if (!sessionId) return;
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
  }, [sessionId, settings.gemini_model, clearLogs, setLoading, setError]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold sm:text-2xl">Upload Videos</h1>
        <p className="text-sm text-text-muted">
          Upload your videos and let AI analyze them before you set your creative direction.
        </p>
      </div>

      <UploadDropzone onFiles={handleFiles} disabled={loading} />
      <VideoFileList videos={videos} sessionId={sessionId} onRemove={handleRemoveVideo} />

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-error/10 p-3 text-sm text-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {videos.length > 0 && (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">
              AI Model
            </label>
            <select
              value={settings.gemini_model}
              onChange={(e) => updateSettings({ gemini_model: e.target.value })}
              className="w-full rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none focus:border-primary"
            >
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
            </select>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="gradient-bg flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-base font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Sparkles size={20} />
            {phase === "analyzing" ? "Analyzing Videos..." : "Analyze Videos"}
          </button>
        </div>
      )}
    </div>
  );
}
