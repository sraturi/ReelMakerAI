import { useCallback } from "react";
import { RenderProgress } from "./RenderProgress";
import { useUIStore } from "../../store/useUIStore";
import { useSSE } from "../../hooks/useSSE";

export function RenderPage() {
  const loading = useUIStore((s) => s.loading);
  const error = useUIStore((s) => s.error);
  const activeJobId = useUIStore((s) => s.activeJobId);
  const setActiveJobId = useUIStore((s) => s.setActiveJobId);
  const setRenderOutput = useUIStore((s) => s.setRenderOutput);
  const setStep = useUIStore((s) => s.setStep);
  const setError = useUIStore((s) => s.setError);

  // Listen for render SSE completion
  useSSE(
    activeJobId,
    useCallback(
      (data: string) => {
        try {
          const result = JSON.parse(data);
          setRenderOutput(result.output_url);
          setActiveJobId(null);
          setStep("preview");
        } catch (e) {
          setError(String(e));
        }
      },
      [setRenderOutput, setActiveJobId, setStep, setError],
    ),
  );

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
