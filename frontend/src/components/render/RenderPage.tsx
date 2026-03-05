import { useCallback } from "react";
import { X } from "lucide-react";
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

  const handleCancel = useCallback(() => {
    cancel();
    setActiveJobId(null);
    setLoading(false);
    setStep("edit");
  }, [cancel, setActiveJobId, setLoading, setStep]);

  return (
    <div>
      {loading && (
        <div className="space-y-4">
          <RenderProgress />
          <button
            onClick={handleCancel}
            className="mx-auto flex items-center gap-2 rounded-lg border border-error/50 bg-error/10 px-4 py-2 text-sm font-medium text-error transition-opacity hover:bg-error/20"
          >
            <X size={16} />
            Cancel Render
          </button>
        </div>
      )}
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
