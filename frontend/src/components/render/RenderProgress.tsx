import { Loader2 } from "lucide-react";
import { useUIStore } from "../../store/useUIStore";

export function RenderProgress() {
  const logs = useUIStore((s) => s.logs);

  return (
    <div className="flex flex-col items-center space-y-6 py-12">
      <div className="rounded-full bg-primary/10 p-6">
        <Loader2 className="animate-spin text-primary" size={48} />
      </div>
      <div>
        <h2 className="text-center text-xl font-bold">Rendering Your Reel</h2>
        <p className="text-center text-sm text-text-muted">
          FFmpeg is assembling your clips, transitions, and captions...
        </p>
      </div>
      {logs.length > 0 && (
        <div className="w-full max-w-lg rounded-xl bg-surface p-4">
          <div className="max-h-48 overflow-y-auto font-mono text-xs text-text-muted">
            {logs.slice(-15).map((log, i) => (
              <div key={i} className="py-0.5">
                {log}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
