"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/store";

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const user = useAuthStore((state) => state.user);
  const { onMessage, onError, onOpen, onClose } = options;

  useEffect(() => {
    if (!user) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsUrl}/api/ws/metrics`);

    ws.onopen = () => {
      // Authenticate
      ws.send(
        JSON.stringify({
          type: "auth",
          token: document.cookie
            .split("; ")
            .find((row) => row.startsWith("access_token="))
            ?.split("=")[1],
        })
      );
      onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "connected") {
          console.log("WebSocket connected");
        } else if (message.type === "call_ingested") {
          onMessage?.(message);
        }
      } catch (error) {
        console.error("WebSocket message parse error:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      onError?.(error);
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
      onClose?.();
      // Reconnect after 5 seconds
      setTimeout(() => {
        if (user) {
          wsRef.current = ws;
        }
      }, 5000);
    };

    wsRef.current = ws;

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [user, onMessage, onError, onOpen, onClose]);
}

