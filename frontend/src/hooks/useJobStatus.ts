import { useEffect, useRef, useCallback } from "react";
import { connectWS, type WSConnection } from "../api/ws";
import { useUIStore } from "../store/useUIStore";

/**
 * Connects to a job's WebSocket, streams logs into the UI store,
 * and auto-registers a cancel button in the LoadingOverlay.
 *
 * Returns a stable `cancel` function (ref-based, no stale closure risk).
 */
export function useJobStatus(
  jobId: string | null,
  onDone?: (data: unknown) => void,
  onCancelled?: () => void,
): () => void {
  const addLog = useUIStore((s) => s.addLog);
  const setError = useUIStore((s) => s.setError);
  const setLoading = useUIStore((s) => s.setLoading);
  const setCancelJob = useUIStore((s) => s.setCancelJob);
  const connRef = useRef<WSConnection | null>(null);

  // Keep latest callbacks in refs so the WS effect doesn't re-fire on every render
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;
  const onCancelledRef = useRef(onCancelled);
  onCancelledRef.current = onCancelled;

  useEffect(() => {
    if (!jobId) return;

    connRef.current = connectWS(jobId, {
      onLog: (msg) => addLog(msg),
      onDone: (data) => {
        setLoading(false);
        onDoneRef.current?.(data);
      },
      onError: (err) => {
        setError(err);
      },
      onCancelled: () => {
        setLoading(false);
        onCancelledRef.current?.();
      },
    });

    // Register cancel in the LoadingOverlay
    setCancelJob(() => {
      connRef.current?.cancel();
    });

    return () => {
      connRef.current?.close();
      connRef.current = null;
      setCancelJob(null);
    };
  }, [jobId, addLog, setError, setLoading, setCancelJob]);

  const cancel = useCallback(() => {
    connRef.current?.cancel();
  }, []);

  return cancel;
}
