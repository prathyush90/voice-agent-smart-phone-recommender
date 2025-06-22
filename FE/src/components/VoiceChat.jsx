import React, { useState, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

const VoiceChat = () => {
  const sessionId = useRef(uuidv4());
  const [isRecording, setIsRecording] = useState(false);
  const [isSocketReady, setIsSocketReady] = useState(false);
  const mediaRecorderRef = useRef(null);
  const socketRef = useRef(null);
  const audioContextRef = useRef(null);
  const nextStartTimeRef = useRef(0);
  const stopClickTimeRef = useRef(null);
  const firstAudioChunkTimeRef = useRef(null);


  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/audio?session_id=${sessionId.current}`);
    ws.binaryType = "arraybuffer";
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("[FE] WebSocket connected");
      setIsSocketReady(true);
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      nextStartTimeRef.current = audioContextRef.current.currentTime;
    };

    ws.onclose = () => {
      console.log("[FE] WebSocket disconnected");
      setIsSocketReady(false);
    };

    ws.onmessage = async (event) => {
      if (firstAudioChunkTimeRef.current === null) {
        firstAudioChunkTimeRef.current = performance.now();
        console.log("first audio time init:", firstAudioChunkTimeRef.current);
        console.log("stop  time init:", stopClickTimeRef.current);
        const latencyMs = firstAudioChunkTimeRef.current - stopClickTimeRef.current;
        console.log(`⏱️ TTS latency: ${latencyMs.toFixed(2)} ms`);
      }
      if (typeof event.data === "string" && event.data === "__END__") {
        firstAudioChunkTimeRef.current = null;
        stopClickTimeRef.current = null;
        console.log("[FE] Received __END__, playback done");
        return;
      }

      if (event.data instanceof ArrayBuffer) {
        const context = audioContextRef.current;
        if (!context) return;

        try {
          const audioBuffer = await context.decodeAudioData(event.data.slice(0));
          const source = context.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(context.destination);

          const startAt = Math.max(context.currentTime, nextStartTimeRef.current);
          source.start(startAt);
          nextStartTimeRef.current = startAt + audioBuffer.duration;

          console.log(`[FE] Played chunk of ${audioBuffer.duration.toFixed(2)}s`);
        } catch (err) {
          console.error("[FE] Error decoding audio chunk:", err);
        }
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "control", command: "__DISCONNECT__" }));
        ws.close();
      }
      audioContextRef.current?.close();
    };
  }, []);

  const toggleRecording = async () => {
  if (!isRecording && isSocketReady) {
    console.log("[FE] Starting recording...");

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: "control",
        command: "__START__"
      }));
      console.log("[FE] Sent __START__ control signal");
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0 && socketRef.current?.readyState === WebSocket.OPEN) {
        console.log("[FE] Sent audio chunk:", e.data.size);
        socketRef.current.send(e.data);
      }
    };

    recorder.start(250);
    setIsRecording(true);
  } else {
    console.log("[FE] Stopping recording...");
    mediaRecorderRef.current?.stop();

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      
      socketRef.current.send(JSON.stringify({
        type: "control",
        command: "__STOP__"
      }));
      console.log("[FE] Sent __STOP__ control signal");
      stopClickTimeRef.current = performance.now();
      console.log("Stop time init:", stopClickTimeRef.current);
    }

    setIsRecording(false);
  }
};


  return (
    <div className="voice-chat">
      <button onClick={toggleRecording} disabled={!isSocketReady}>
        {isRecording ? "Stop" : "Start"}
      </button>
    </div>
  );
};

export default VoiceChat;
