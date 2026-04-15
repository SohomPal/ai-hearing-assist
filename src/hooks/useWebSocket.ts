import { useState, useEffect, useRef, useCallback } from "react";

interface BandData {
  cr: number | null;
  gain_dB: number | null;
  atk_ms: number | null;
  rel_ms: number | null;
  tk_dB?: number | null;
}

interface WSState {
  isConnected: boolean;
  isBleConnected: boolean;
  bands: BandData[];
  logs: string[];
  sendCommand: (cmd: string) => void;
}

const DEFAULT_BANDS: BandData[] = Array.from({ length: 6 }, () => ({
  cr: null,
  gain_dB: null,
  atk_ms: null,
  rel_ms: null,
  tk_dB: null,
}));

export function useWebSocket(url = "ws://localhost:8765"): WSState {
  const [isConnected, setIsConnected] = useState(false);
  const [isBleConnected, setIsBleConnected] = useState(false);
  const [bands, setBands] = useState<BandData[]>(DEFAULT_BANDS);
  const [logs, setLogs] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();

  const addLog = useCallback((msg: string) => {
    setLogs((prev) => [...prev.slice(-49), msg]);
  }, []);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        addLog("Connected to Python backend");
      };

      ws.onclose = () => {
        setIsConnected(false);
        setIsBleConnected(false);
        addLog("Disconnected from backend");
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "ble_status") {
            setIsBleConnected(msg.connected);
          } else if (msg.type === "params") {
            setBands(msg.bands);
          } else if (msg.type === "log") {
            addLog(msg.message);
          } else if (msg.type === "intent_result") {
            addLog(`Intent: ${msg.intent} → ${msg.changes} change(s)`);
          }
        } catch {
          addLog(ev.data);
        }
      };
    } catch {
      reconnectRef.current = setTimeout(connect, 3000);
    }
  }, [url, addLog]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback((cmd: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "command", text: cmd }));
    }
  }, []);

  return { isConnected, isBleConnected, bands, logs, sendCommand };
}
