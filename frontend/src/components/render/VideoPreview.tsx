import { Download, Edit3, MessageSquare, Plus } from "lucide-react";
import { useUIStore } from "../../store/useUIStore";
import { useSessionStore } from "../../store/useSessionStore";

export function VideoPreview() {
  const renderOutput = useUIStore((s) => s.renderOutput);
  const setStep = useUIStore((s) => s.setStep);
  const reset = useSessionStore((s) => s.reset);
  const clearLogs = useUIStore((s) => s.clearLogs);
  const setRenderOutput = useUIStore((s) => s.setRenderOutput);

  if (!renderOutput) return null;

  function handleNewProject() {
    reset();
    clearLogs();
    setRenderOutput(null);
    setStep("home");
  }

  return (
    <div className="flex flex-col items-center space-y-6 py-8">
      <h2 className="text-xl font-bold">Your Reel is Ready!</h2>

      <div className="w-full max-w-sm overflow-hidden rounded-xl bg-black shadow-2xl">
        <video
          src={renderOutput}
          controls
          autoPlay
          className="aspect-[9/16] w-full"
        />
      </div>

      <div className="flex w-full max-w-sm flex-col gap-2 sm:w-auto sm:max-w-none sm:flex-row sm:gap-3">
        <a
          href={renderOutput}
          download
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-6 py-2.5 font-semibold text-white hover:bg-primary-hover sm:w-auto"
        >
          <Download size={18} />
          Download
        </a>
        <button
          onClick={() => setStep("prompt")}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-border px-6 py-2.5 font-semibold text-text hover:bg-surface-light sm:w-auto"
        >
          <MessageSquare size={18} />
          Change Prompt
        </button>
        <button
          onClick={() => setStep("edit")}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-border px-6 py-2.5 font-semibold text-text hover:bg-surface-light sm:w-auto"
        >
          <Edit3 size={18} />
          Edit Clips
        </button>
        <button
          onClick={handleNewProject}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-border px-6 py-2.5 font-semibold text-text hover:bg-surface-light sm:w-auto"
        >
          <Plus size={18} />
          New Project
        </button>
      </div>
    </div>
  );
}
