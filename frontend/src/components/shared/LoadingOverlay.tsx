import { Loader2 } from "lucide-react";
import { useUIStore } from "../../store/useUIStore";

export function LoadingOverlay() {
  const loading = useUIStore((s) => s.loading);
  const message = useUIStore((s) => s.loadingMessage);
  const logs = useUIStore((s) => s.logs);

  if (!loading) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl bg-surface p-6 shadow-2xl">
        <div className="mb-4 flex items-center gap-3">
          <Loader2 className="animate-spin text-primary" size={24} />
          <span className="text-lg font-medium">{message || "Processing..."}</span>
        </div>
        {logs.length > 0 && (
          <div className="max-h-48 overflow-y-auto rounded-lg bg-black/40 p-3 font-mono text-xs text-text-muted">
            {logs.slice(-20).map((log, i) => (
              <div key={i} className="py-0.5">
                {log}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
