export interface SSECallbacks {
  onLog?: (message: string) => void;
  onDone?: (data: string) => void;
  onError?: (error: string) => void;
}

export function connectSSE(jobId: string, callbacks: SSECallbacks): () => void {
  const es = new EventSource(`/api/status/${jobId}`);

  es.addEventListener("log", (e) => {
    callbacks.onLog?.(e.data);
  });

  es.addEventListener("done", (e) => {
    callbacks.onDone?.(e.data);
    es.close();
  });

  es.addEventListener("error", (e) => {
    if (e instanceof MessageEvent) {
      callbacks.onError?.(e.data);
    } else {
      callbacks.onError?.("Connection lost");
    }
    es.close();
  });

  return () => es.close();
}
