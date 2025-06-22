from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from utils.deepgram_utils import stream_to_deepgram
from utils.llm_utils import stream_llm_response
from utils.tts_utils import stream_tts_audio_websocket

import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import time

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = websocket.query_params.get("session_id") or "default_user"
    print("[WS] WebSocket connected.")

    try:
        while True:
            # Wait for __START__
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    print("[WS] Client disconnected.")
                    return

                if "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        if data.get("type") == "control" and data.get("command") == "__START__":
                            print("[WS] Received __START__ → begin turn")
                            break
                    except json.JSONDecodeError:
                        continue

            # ⏱️ START TIMER
            t0 = time.perf_counter()

            # Deepgram
            transcript_buffer = []
            transcript = await stream_to_deepgram(websocket, transcript_buffer)
            t1 = time.perf_counter()

            if not transcript:
                await websocket.send_text("__END__")
                continue

            print(f"[TRANSCRIPT] «{transcript}»")

            # LLM
            print("[WS] Fetching response from LLM...")
            text_stream = stream_llm_response(session_id, transcript)
            t2 = time.perf_counter()
            print(f"[TIMER] LLM processing started after {t2 - t1:.2f} sec")

            # TTS
            print("[WS] Streaming TTS audio...")
            tts_start = time.perf_counter()
            chunk_count = 0
            async for audio_chunk in stream_tts_audio_websocket(text_stream):
                await websocket.send_bytes(audio_chunk)
                chunk_count += 1
            tts_end = time.perf_counter()

            print(f"[TIMER] TTS took {tts_end - tts_start:.2f} sec with {chunk_count} chunks")
            print(f"[TIMER] Total turn time: {tts_end - t0:.2f} sec")

            await websocket.send_text("__END__")

    except Exception as e:
        print(f"[ERROR] WebSocket crashed: {e}")



