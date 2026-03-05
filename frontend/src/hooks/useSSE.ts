import { useEffect, useRef } from "react";
import { connectSSE } from "../api/sse";
import { useUIStore } from "../store/useUIStore";

export function useSSE(
  jobId: string | null,
  onDone?: (data: string) => void,
) {
  const addLog = useUIStore((s) => s.addLog);
  const setError = useUIStore((s) => s.setError);
  const setLoading = useUIStore((s) => s.setLoading);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!jobId) return;

    cleanupRef.current = connectSSE(jobId, {
      onLog: (msg) => addLog(msg),
      onDone: (data) => {
        setLoading(false);
        onDone?.(data);
      },
      onError: (err) => {
        setError(err);
      },
    });

    return () => {
      cleanupRef.current?.();
    };
  }, [jobId, onDone, addLog, setError, setLoading]);
}
