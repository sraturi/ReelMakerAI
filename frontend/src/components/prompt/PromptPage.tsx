import { useCallback, useState } from "react";
import { Sparkles, AlertCircle, Film, Zap } from "lucide-react";
import { SettingsPanel } from "../settings/SettingsPanel";
import { startPlan } from "../../api/plan";
import { useSessionStore } from "../../store/useSessionStore";
import { useEditorStore } from "../../store/useEditorStore";
import { useUIStore } from "../../store/useUIStore";
import { useJobStatus } from "../../hooks/useJobStatus";

export function PromptPage() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const analysis = useSessionStore((s) => s.analysis);
  const settings = useSessionStore((s) => s.settings);
  const setPlan = useSessionStore((s) => s.setPlan);
  const setClips = useEditorStore((s) => s.setClips);
  const setOverlays = useEditorStore((s) => s.setOverlays);
  const setStep = useUIStore((s) => s.setStep);
  const setLoading = useUIStore((s) => s.setLoading);
  const setError = useUIStore((s) => s.setError);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const setCancelJob = useUIStore((s) => s.setCancelJob);
  const error = useUIStore((s) => s.error);
  const loading = useUIStore((s) => s.loading);

  const [planJobId, setPlanJobId] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);

  const handleCancelled = useCallback(() => {
    setPlanJobId(null);
    setPlanning(false);
  }, []);

  // Handle plan WebSocket completion → go to editor
  const cancel = useJobStatus(planJobId, useCallback((data: unknown) => {
    try {
      const plan = data as { clips?: unknown[]; text_overlays?: unknown[] };
      setPlan(plan);
      setClips(plan.clips || []);
      setOverlays(plan.text_overlays || []);
      setPlanJobId(null);
      setPlanning(false);
      setStep("edit");
    } catch (e) {
      setError(String(e));
    }
  }, [setPlan, setClips, setOverlays, setStep, setError]), handleCancelled);

  const handleCancel = useCallback(() => {
    cancel();
    setPlanJobId(null);
    setPlanning(false);
    setLoading(false);
  }, [cancel, setLoading]);

  const handleGeneratePlan = useCallback(async () => {
    if (!sessionId || !settings.prompt.trim()) return;
    setError(null);
    clearLogs();
    setPlanning(true);
    setLoading(true, "Creating editing plan...");
    setCancelJob(handleCancel);
    try {
      const { job_id } = await startPlan(sessionId, settings);
      setPlanJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPlanning(false);
    }
  }, [sessionId, settings, clearLogs, setLoading, setCancelJob, handleCancel, setError]);

  // Compute analysis summary
  const totalScenes = analysis?.videos.reduce((sum: number, v: { scenes: unknown[] }) => sum + v.scenes.length, 0) ?? 0;
  const peakMoments = analysis?.videos.reduce(
    (sum: number, v: { scenes: { is_peak_moment: boolean }[] }) => sum + v.scenes.filter((s) => s.is_peak_moment).length,
    0,
  ) ?? 0;
  const totalDuration = analysis?.videos.reduce((sum: number, v: { duration: number }) => sum + v.duration, 0) ?? 0;

  const canGenerate = settings.prompt.trim().length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Creative Direction</h1>
        <p className="text-sm text-text-muted">
          Your videos have been analyzed. Set your prompt and preferences, then generate a plan.
        </p>
      </div>

      {/* Analysis summary */}
      {analysis && (
        <div className="grid grid-cols-3 gap-3">
          <div className="flex items-center gap-3 rounded-xl bg-surface p-4">
            <Film size={20} className="text-primary" />
            <div>
              <p className="text-lg font-bold">{totalScenes}</p>
              <p className="text-xs text-text-muted">Scenes Found</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl bg-surface p-4">
            <Zap size={20} className="text-warning" />
            <div>
              <p className="text-lg font-bold">{peakMoments}</p>
              <p className="text-xs text-text-muted">Peak Moments</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl bg-surface p-4">
            <Film size={20} className="text-success" />
            <div>
              <p className="text-lg font-bold">{Math.round(totalDuration)}s</p>
              <p className="text-xs text-text-muted">Total Footage</p>
            </div>
          </div>
        </div>
      )}

      {/* Video summaries */}
      {analysis && analysis.videos.length > 0 && (
        <div className="space-y-2 rounded-xl bg-surface p-4">
          <h3 className="text-sm font-semibold">Video Summaries</h3>
          {analysis.videos.map((v: { filename: string; summary: string }, i: number) => (
            <div key={i} className="text-sm text-text-muted">
              <span className="font-medium text-text">{v.filename}:</span>{" "}
              {v.summary}
            </div>
          ))}
        </div>
      )}

      <SettingsPanel sessionId={sessionId} />

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-error/10 p-3 text-sm text-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <button
        onClick={handleGeneratePlan}
        disabled={!canGenerate || loading}
        className="gradient-bg flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-base font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Sparkles size={20} />
        {planning ? "Generating Plan..." : "Generate Plan"}
      </button>
    </div>
  );
}
