import { useCallback, useEffect, useRef } from "react";
import { RenderProgress } from "./RenderProgress";
import { useUIStore } from "../../store/useUIStore";
import { useJobStatus } from "../../hooks/useJobStatus";

export function RenderPage() {
  const loading = useUIStore((s) => s.loading);
  const error = useUIStore((s) => s.error);
  const activeJobId = useUIStore((s) => s.activeJobId);
  const setActiveJobId = useUIStore((s) => s.setActiveJobId);
  const setRenderOutput = useUIStore((s) => s.setRenderOutput);
  const setStep = useUIStore((s) => s.setStep);
  const setError = useUIStore((s) => s.setError);
  const setLoading = useUIStore((s) => s.setLoading);
  const setCancelJob = useUIStore((s) => s.setCancelJob);

  const handleCancelled = useCallback(() => {
    setActiveJobId(null);
    setStep("edit");
  }, [setActiveJobId, setStep]);

  // Listen for render WebSocket completion
  const cancel = useJobStatus(
    activeJobId,
    useCallback(
      (data: unknown) => {
        try {
          const result = data as { output_url: string };
          setRenderOutput(result.output_url);
          setActiveJobId(null);
          setStep("preview");
        } catch (e) {
          setError(String(e));
        }
      },
      [setRenderOutput, setActiveJobId, setStep, setError],
    ),
    handleCancelled,
  );

  const cancelRef = useRef(cancel);
  cancelRef.current = cancel;

  // Register cancel handler in the LoadingOverlay when render is active
  useEffect(() => {
    if (activeJobId && loading) {
      setCancelJob(() => {
        cancelRef.current();
        setActiveJobId(null);
        setLoading(false);
        setStep("edit");
      });
    }
  }, [activeJobId, loading, setCancelJob, setActiveJobId, setLoading, setStep]);

  return (
    <div>
      {loading && <RenderProgress />}
      {error && (
        <div className="flex flex-col items-center space-y-4 py-12">
          <p className="text-lg font-medium text-error">Render Failed</p>
          <p className="text-sm text-text-muted">{error}</p>
          <button
            onClick={() => useUIStore.getState().setStep("edit")}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white"
          >
            Back to Editor
          </button>
        </div>
      )}
    </div>
  );
}
