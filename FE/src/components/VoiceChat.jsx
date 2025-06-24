// src/components/VoiceChat.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";

/* ────────────────── tunables ────────────────── */
const VAD_FRAME_MS  = 100;           // analyser polling interval
const VAD_THRESHOLD = 0.02;          // RMS above which we treat as speech
const CHUNK_MS      = 250;           // MediaRecorder chunk size
/* ─────────────────────────────────────────────── */

export default function VoiceChat() {
  /* durable refs ----------------------------------------------------------- */
  const sessionId          = useRef(uuidv4());
  const socketRef          = useRef(null);
  const mediaRecorderRef   = useRef(null);
  const audioCtxRef        = useRef(null);
  const analyserRef        = useRef(null);

  /* playback queue refs ---------------------------------------------------- */
  const nextStartRef       = useRef(0);
  const playingSrcRef      = useRef([]);          // queued AudioBufferSourceNodes

  /* VAD / latency refs ----------------------------------------------------- */
  const speakingRef        = useRef(false);       // TRUE while user is talking
  const ttsFirstChunkRef   = useRef(null);
  const speakStartRef      = useRef(null);

  /* state for UI ----------------------------------------------------------- */
  const [socketReady,  setSocketReady ] = useState(false);
  const [hasStarted,   setHasStarted  ] = useState(false);
  const [isSpeakingUI, setIsSpeakingUI] = useState(false);

  /* ─────────────── open backend WS exactly once ─────────────── */
  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const host  =
      location.hostname === "localhost"
        ? "localhost:8000"
        : location.host;                        // prod TLS (no :8000)
    const wsURL = `${proto}://${host}/ws/audio?session_id=${sessionId.current}`;

    const ws = new WebSocket(wsURL);
    ws.binaryType = "arraybuffer";
    socketRef.current = ws;

    ws.onopen  = () => { console.log("[FE] WS ✅ open →", wsURL); setSocketReady(true); };
    ws.onclose = () => { console.log("[FE] WS ❌ closed");        setSocketReady(false);};

    /* ----------- receive audio / __END__ from backend ---------- */
    ws.onmessage = async (ev) => {
      /* latency log on first audio packet in a turn */
      if (!ttsFirstChunkRef.current) {
        ttsFirstChunkRef.current = performance.now();
        if (speakStartRef.current) {
          console.log(
            `⏱️  TTS-first-chunk latency: ${
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

      const ctx = audioCtxRef.current;
      try {
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
          }s (ctx.current=${ctx.currentTime.toFixed(2)})`
        );
      } catch (e) {
        console.error("[FE] decodeAudioData error:", e);
      }
    };

    return () => {
      ws.close();
      audioCtxRef.current?.close();
    };
  }, []);

  /* ─────────────── voice-activity polling loop ─────────────── */
  useEffect(() => {
    if (!hasStarted) return;
    const id = setInterval(() => {
      const analyser = analyserRef.current;
      if (!analyser) return;

      const fft = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(fft);
      const rms = Math.sqrt(fft.reduce((s, v) => s + v * v, 0) / fft.length);

      const speakingNow = rms > VAD_THRESHOLD;

      // debug each poll (comment out if noisy)
      // console.log(`[VAD] rms=${rms.toFixed(4)} → ${speakingNow}`);

      /* transition silence→speech */
      if (speakingNow && !speakingRef.current) {
        speakStartRef.current = performance.now();
        stopCurrentTTS();
        console.log("[VAD] 🎤 user STARTED speaking");
      }
      /* transition speech→silence */
      if (!speakingNow && speakingRef.current) {
        console.log("[VAD] 🎤 user STOPPED speaking");
      }

      speakingRef.current = speakingNow;
      setIsSpeakingUI(speakingNow);
    }, VAD_FRAME_MS);

    return () => clearInterval(id);
  }, [hasStarted]);

  /* ───────────────────── helpers ───────────────────── */
  const stopCurrentTTS = () => {
    if (playingSrcRef.current.length) {
      console.log("[FE] ⏹️  Stopping", playingSrcRef.current.length, "queued TTS sources");
    }
    playingSrcRef.current.forEach((src) => {
      try { src.stop(0); } catch (_) {}
    });
    playingSrcRef.current = [];
    nextStartRef.current = audioCtxRef.current?.currentTime || 0;
  };

  /* ───────────── click “Start Conversation” once ───────────── */
  const handleStart = async () => {
    if (!socketReady || hasStarted) return;

    /* open mic & VAD analyser */
    const ctx    = new (window.AudioContext || window.webkitAudioContext)();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    audioCtxRef.current = ctx;
    analyserRef.current = ctx.createAnalyser();
    analyserRef.current.fftSize = 2048;
    ctx.createMediaStreamSource(stream).connect(analyserRef.current);

    /* MediaRecorder → send chunks whenever VAD says user is speaking */
    const rec = new MediaRecorder(stream);
    mediaRecorderRef.current = rec;

    rec.ondataavailable = (e) => {
      if (
        e.data.size &&
        speakingRef.current &&
        socketRef.current.readyState === WebSocket.OPEN
      ) {
        console.log(`[FE] ⇢ send opus chunk ${e.data.size} bytes`);
        socketRef.current.send(e.data);
      }
    };
    rec.start(CHUNK_MS);

    /* optional one-time hint to backend */
    socketRef.current.send(JSON.stringify({ type: "control", command: "__START__" }));

    setHasStarted(true);
    console.log("[FE] 🎤 MediaRecorder started, chunk =", CHUNK_MS, "ms");
  };

  /* ────────────────────────── UI ────────────────────────── */
  return (
    <div style={{ textAlign: "center", paddingTop: "2rem" }}>
      {!hasStarted ? (
        <button
          onClick={handleStart}
          disabled={!socketReady}
          style={{ fontSize: "1.2rem", padding: "0.6rem 1.4rem" }}
        >
          Start&nbsp;Conversation
        </button>
      ) : (
        <p style={{ fontFamily: "monospace" }}>
          🎙️ Listening…{" "}
          {isSpeakingUI && <span style={{ color: "orange" }}>● speaking</span>}
        </p>
      )}
    </div>
  );
}
