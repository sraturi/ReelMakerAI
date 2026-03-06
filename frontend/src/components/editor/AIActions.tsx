import { useState, useCallback } from "react";
import { RefreshCw, Loader2 } from "lucide-react";
import { startReplan } from "../../api/plan";
import { useSessionStore } from "../../store/useSessionStore";
import { useEditorStore } from "../../store/useEditorStore";
import { useUIStore } from "../../store/useUIStore";
import { useJobStatus } from "../../hooks/useJobStatus";

export function AIActions() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const settings = useSessionStore((s) => s.settings);
  const setPlan = useSessionStore((s) => s.setPlan);
  const setClips = useEditorStore((s) => s.setClips);
  const setOverlays = useEditorStore((s) => s.setOverlays);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const setLoading = useUIStore((s) => s.setLoading);
  const setError = useUIStore((s) => s.setError);

  const [direction, setDirection] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleCancelled = useCallback(() => {
    setJobId(null);
    setBusy(false);
  }, []);

  const handleReplanDone = useCallback(
    (data: unknown) => {
      try {
        const plan = data as { clips?: unknown[]; text_overlays?: unknown[] };
        setPlan(plan);
        setClips(plan.clips || []);
        setOverlays(plan.text_overlays || []);
        setDirection("");
      } catch (e) {
        setError(String(e));
      }
      setJobId(null);
      setBusy(false);
    },
    [setPlan, setClips, setOverlays, setError],
  );

  const cancel = useJobStatus(jobId, handleReplanDone, handleCancelled);

  const handleCancel = useCallback(() => {
    cancel();
    setJobId(null);
    setBusy(false);
    setLoading(false);
  }, [cancel, setLoading]);

  async function handleReEdit() {
    if (!sessionId || !direction.trim()) return;
    setBusy(true);
    clearLogs();
    setLoading(true, "Re-generating plan...");
    try {
      const { job_id } = await startReplan(sessionId, direction, settings);
      setJobId(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <input
        type="text"
        value={direction}
        onChange={(e) => setDirection(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleReEdit()}
        placeholder="e.g. make it more energetic, shorter clips"
        className="flex-1 rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none placeholder:text-text-muted/50 focus:border-primary"
        disabled={busy}
      />
      <button
        onClick={handleReEdit}
        disabled={busy || !direction.trim()}
        className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50 sm:w-auto"
      >
        {busy ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <RefreshCw size={14} />
        )}
        Re-edit
      </button>
    </div>
  );
}
