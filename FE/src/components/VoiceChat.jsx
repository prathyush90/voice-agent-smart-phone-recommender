// src/components/VoiceChat.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";

// chunk size remains 250 ms, same as your old working version
const CHUNK_MS = 250;

export default function VoiceChat() {
  const sessionId        = useRef(uuidv4());
  const socketRef        = useRef(null);
  const mediaRecorderRef = useRef(null);

  // playback setup (unchanged)
  const audioCtxRef  = useRef(null);
  const nextStartRef = useRef(0);
  const playingSrcRef = useRef([]);
  const ttsFirstChunkRef = useRef(null);
  const speakStartRef    = useRef(null);

  const [socketReady, setSocketReady] = useState(false);
  const [hasStarted,  setHasStarted]  = useState(false);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const host  = location.hostname === "localhost"
      ? "localhost:8000"
      : "https://18ac-13-220-204-79.ngrok-free.app";
    const wsURL = `${proto}://${host}/ws/audio?session_id=${sessionId.current}`;

    const ws = new WebSocket(wsURL);
    ws.binaryType = "arraybuffer";
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("[FE] WS ✅ open →", wsURL);
      setSocketReady(true);

      // init audio context for playback
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
      nextStartRef.current = audioCtxRef.current.currentTime;
    };

    ws.onclose = () => {
      console.log("[FE] WS ❌ closed");
      setSocketReady(false);
      mediaRecorderRef.current?.stop();
    };

    ws.onmessage = async (ev) => {
      // latency log on first TTS chunk
      if (!ttsFirstChunkRef.current) {
        ttsFirstChunkRef.current = performance.now();
        if (speakStartRef.current) {
          console.log(
            `⏱️ TTS-first-chunk latency: ${
              (ttsFirstChunkRef.current - speakStartRef.current).toFixed(0)
            } ms`
          );
        }
      }

      if (typeof ev.data === "string") {
        if (ev.data === "__END__") {
          console.log("[FE] <__END__> (turn finished)");
          ttsFirstChunkRef.current = null;
        } else {
          console.log("[FE] text-msg:", ev.data.slice(0, 30));
        }
        return;
      }

      if (!(ev.data instanceof ArrayBuffer)) return;

      try {
        const ctx = audioCtxRef.current;
        const buf = await ctx.decodeAudioData(ev.data.slice(0));
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);

        const startAt = Math.max(ctx.currentTime, nextStartRef.current);
        src.start(startAt);
        nextStartRef.current = startAt + buf.duration;
        playingSrcRef.current.push(src);

        console.log(
          `[FE] ▶ chunk ${buf.duration.toFixed(2)} s queued @ ${
            startAt.toFixed(2)
          }s`
        );
      } catch (e) {
        console.error("[FE] decodeAudioData error:", e);
      }
    };

    ws.onerror = (err) => {
      console.error("[FE] WS error:", err);
    };

    return () => {
      ws.close();
      audioCtxRef.current?.close();
      mediaRecorderRef.current?.stop();
    };
  }, []);

  const handleStart = async () => {
    if (!socketReady || hasStarted) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec    = new MediaRecorder(stream);
    mediaRecorderRef.current = rec;

    rec.ondataavailable = (e) => {
      if (e.data.size > 0 && socketRef.current.readyState === WebSocket.OPEN) {
        console.log(`[FE] ⇢ send chunk ${e.data.size} bytes`);
        socketRef.current.send(e.data);
      }
    };

    rec.onerror = (err) => {
      console.error("[FE] MediaRecorder error:", err);
    };

    rec.start(CHUNK_MS);
    // one-time hint to backend
    socketRef.current.send(JSON.stringify({ type: "control", command: "__START__" }));

    setHasStarted(true);
    console.log("[FE] 🎤 Recording started, chunk =", CHUNK_MS, "ms");
  };

  return (
    <div style={{ textAlign: "center", paddingTop: "2rem" }}>
      {!hasStarted ? (
        <button
          onClick={handleStart}
          disabled={!socketReady}
          style={{ fontSize: "1.2rem", padding: "0.6rem 1.4rem" }}
        >
          Start Conversation
        </button>
      ) : (
        <p style={{ fontFamily: "monospace" }}>🎙️ Recording…</p>
      )}
    </div>
  );
}
