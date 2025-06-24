import os
import json
import asyncio
import time
import webrtcvad
from websockets.legacy.client import connect

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def stream_to_deepgram(websocket, transcript_buffer):
    url = "wss://api.deepgram.com/v1/listen?punctuate=true"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

    vad = webrtcvad.Vad(3)
    speaking = False
    silence_sent = False

    async with connect(url, extra_headers=headers) as dg_ws:
        print("inside connect")
        def frame_generator(chunk, frame_ms=30, sample_rate=16000):
            frame_size = int(sample_rate * (frame_ms / 1000.0) * 2)  # 2 bytes per sample
            for i in range(0, len(chunk), frame_size):
                yield chunk[i:i + frame_size]

        async def forward_audio():
            nonlocal speaking, silence_sent
            try:
                while True:
                    msg = await websocket.receive()
                    if msg["type"] == "websocket.disconnect":
                        print("[WS] Client disconnected.")
                        break

                    if msg["type"] == "websocket.receive" and "bytes" in msg:
                        audio_bytes = msg["bytes"]
                        print("enetered message loop")
                        has_speech = False
                        for frame in frame_generator(audio_bytes):
                            if len(frame) != 480:
                                continue  # Skip invalid frame
                            if vad.is_speech(frame, sample_rate=16000):
                                has_speech = True
                                break

                        if has_speech:
                            await dg_ws.send(audio_bytes)
                            speaking = True
                            silence_sent = False
                            print("[VAD] 🎤 Voice detected — audio sent")
                        elif speaking and not silence_sent:
                            await dg_ws.send(b"")
                            silence_sent = True
                            speaking = False
                            print("[VAD] 🤫 Silence — b'' sent to flush Deepgram")
            except Exception as e:
                print(f"[ERROR] Audio forward failed: {e}")

        async def receive_transcript():
            try:
                async for msg in dg_ws:
                    res = json.loads(msg)
                    if res.get("is_final"):
                        alt = res["channel"]["alternatives"][0]
                        transcript = alt.get("transcript", "")
                        if transcript:
                            transcript_buffer.append(transcript)
                            print(f"[TRANSCRIPT] {transcript}")
            except Exception as e:
                print(f"[ERROR] Deepgram closed: {e}")

        await asyncio.gather(forward_audio(), receive_transcript())
        return " ".join(transcript_buffer).strip()
