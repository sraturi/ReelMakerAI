import { useEffect, useRef, useCallback } from "react";
import { connectWS, type WSConnection } from "../api/ws";
import { useUIStore } from "../store/useUIStore";

export function useJobStatus(
  jobId: string | null,
  onDone?: (data: unknown) => void,
  onCancelled?: () => void,
): () => void {
  const addLog = useUIStore((s) => s.addLog);
  const setError = useUIStore((s) => s.setError);
  const setLoading = useUIStore((s) => s.setLoading);
  const connRef = useRef<WSConnection | null>(null);

  useEffect(() => {
    if (!jobId) return;

    connRef.current = connectWS(jobId, {
      onLog: (msg) => addLog(msg),
      onDone: (data) => {
        setLoading(false);
        onDone?.(data);
      },
      onError: (err) => {
        setError(err);
      },
      onCancelled: () => {
        setLoading(false);
        onCancelled?.();
      },
    });

    return () => {
      connRef.current?.close();
      connRef.current = null;
    };
  }, [jobId, onDone, onCancelled, addLog, setError, setLoading]);

  const cancel = useCallback(() => {
    connRef.current?.cancel();
  }, []);

  return cancel;
}
