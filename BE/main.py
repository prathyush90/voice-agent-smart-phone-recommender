# server/main.py

from dotenv import load_dotenv
load_dotenv()

import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from websockets.legacy.client import connect
from websockets.exceptions import ConnectionClosed

from utils.llm_utils import llm_stream
from utils.tts_utils import tts_stream

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DG_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?punctuate=true"
    "&interim_results=true"
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/audio")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = ws.query_params.get("session_id", "default")
    print("[WS] Client connected:", session_id)

    # 1️⃣ transcript queue & background processor
    transcript_q = asyncio.Queue()

    async def processor_loop():
        while True:
            transcript = await transcript_q.get()
            print("[PROC] Got transcript:", transcript)
            # stream LLM → TTS → FE
            token_stream = llm_stream(session_id, transcript)
            print("[PROC] Starting LLM→TTS pipeline")
            async for audio_chunk in tts_stream(token_stream):
                await ws.send_bytes(audio_chunk)
            # signal end-of-turn
            await ws.send_text("__END__")
            transcript_q.task_done()

    proc_task = asyncio.create_task(processor_loop())

    # 2️⃣ connect to Deepgram
    async def connect_dg():
        while True:
            try:
                dg = await connect(
                    DG_URL,
                    extra_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"}
                )
                print("[DG] Connected")
                return dg
            except Exception as e:
                print("[DG] Connect failed:", e)
                await asyncio.sleep(1)

    dg_ws = await connect_dg()

    # 3️⃣ forward FE→DG
    async def forward_audio():
        nonlocal dg_ws
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if "bytes" in msg:
                    if dg_ws.closed:
                        dg_ws = await connect_dg()
                    await dg_ws.send(msg["bytes"])
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print("[WS] forward_audio error:", e)
        finally:
            try: await dg_ws.close()
            except: pass

    # 4️⃣ Deepgram event loop → queue final transcripts
    async def dg_event_loop():
        nonlocal dg_ws
        buffer = ""
        try:
            async for raw in dg_ws:
                print("message from dg")
                data = json.loads(raw)
                if data.get("is_final"):
                    txt = data["channel"]["alternatives"][0].get("transcript","")
                    if txt:
                        buffer = (buffer + " " + txt).strip()
                        print(f"[DG] Collected final chunk: «{txt}» → buffer=«{buffer}»")
                    else:
                        if buffer:
                            print(f"[DG] Silence final: flushing buffer «{buffer}»")
                            await transcript_q.put(buffer)
                            buffer = ""
                        else:
                            print("[DG] Silence final but buffer empty → nothing to enqueue")
        except Exception as e:
            print("[DG] event_loop error:", e)
        finally:
            try: await dg_ws.close()
            except: pass

    send_task = asyncio.create_task(forward_audio())
    dg_task   = asyncio.create_task(dg_event_loop())

    # 5️⃣ wait until FE disconnects
    done, pending = await asyncio.wait(
        [send_task, dg_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()

    await transcript_q.join()     # finish any in-flight processing
    proc_task.cancel()            # stop processor
    try: await proc_task
    except asyncio.CancelledError: pass

    print("[WS] Session ended:", session_id)
