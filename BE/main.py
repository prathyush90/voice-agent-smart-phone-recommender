import os
import json
import time
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from utils.deepgram_utils import stream_to_deepgram
from utils.llm_utils import stream_llm_response
from utils.tts_utils import stream_tts_audio_websocket



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = websocket.query_params.get("session_id") or "default_user"
    print("[WS] WebSocket connected.")

    try:
        while True:


            # Timer Start
            t0 = time.perf_counter()

            # STT: Deepgram with VAD
            transcript_buffer = []
            transcript = await stream_to_deepgram(websocket, transcript_buffer)
            t1 = time.perf_counter()



            await websocket.send_text("__END__")

    except Exception as e:
        print(f"[ERROR] WebSocket crashed: {e}")
