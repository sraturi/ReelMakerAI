export interface WSCallbacks {
  onLog?: (message: string) => void;
  onDone?: (data: unknown) => void;
  onError?: (error: string) => void;
  onCancelled?: () => void;
}

export interface WSConnection {
  close: () => void;
  cancel: () => void;
}

export function connectWS(jobId: string, callbacks: WSCallbacks): WSConnection {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}/ws/status/${jobId}`;
  const ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      switch (msg.event) {
        case "log":
          callbacks.onLog?.(msg.data);
          break;
        case "done":
          callbacks.onDone?.(msg.data);
          ws.close();
          break;
        case "error":
          callbacks.onError?.(msg.data);
          ws.close();
          break;
        case "cancelled":
          callbacks.onCancelled?.();
          ws.close();
          break;
      }
    } catch {
      // ignore malformed messages
    }
  };

  ws.onerror = () => {
    callbacks.onError?.("Connection lost");
  };

  ws.onclose = () => {
    // no-op — terminal events already handled above
  };

  return {
    close: () => ws.close(),
    cancel: () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "cancel" }));
      }
    },
  };
}
