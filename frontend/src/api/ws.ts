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

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

export function connectWS(jobId: string, callbacks: WSCallbacks): WSConnection {
  let ws: WebSocket | null = null;
  let retries = 0;
  let closed = false; // true once a terminal event fires or user calls close()
  let cancelled = false;

  function connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/status/${jobId}`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      retries = 0; // reset on successful connect
      // Re-send cancel if it was requested while reconnecting
      if (cancelled && ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "cancel" }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        switch (msg.event) {
          case "log":
            callbacks.onLog?.(msg.data);
            break;
          case "done":
            closed = true;
            callbacks.onDone?.(msg.data);
            ws?.close();
            break;
          case "error":
            closed = true;
            callbacks.onError?.(msg.data);
            ws?.close();
            break;
          case "cancelled":
            closed = true;
            callbacks.onCancelled?.();
            ws?.close();
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      // onerror is always followed by onclose — reconnect logic lives there
    };

    ws.onclose = () => {
      if (closed) return; // terminal event already handled
      if (retries < MAX_RETRIES) {
        retries++;
        setTimeout(connect, RETRY_DELAY_MS * retries);
      } else {
        closed = true;
        callbacks.onError?.("Connection lost");
      }
    };
  }

  connect();

  return {
    close: () => {
      closed = true;
      ws?.close();
    },
    cancel: () => {
      cancelled = true;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "cancel" }));
      }
    },
  };
}
