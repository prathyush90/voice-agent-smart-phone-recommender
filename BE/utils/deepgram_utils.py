import os
import json
import asyncio
import time
from websockets.legacy.client import connect

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def stream_to_deepgram(websocket, transcript_buffer):
    url = "wss://api.deepgram.com/v1/listen?punctuate=true"
    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

    async with connect(url, extra_headers=headers) as dg_ws:
        stop_time = None
        async def forward_audio():
            nonlocal stop_time
            try:
                while True:
                    msg = await websocket.receive()
                    if "type" not in msg:
                        continue

                    if msg["type"] == "websocket.receive":
                        if "bytes" in msg:
                            await dg_ws.send(msg["bytes"])
                            print("[DEBUG] Sent audio chunk to Deepgram")

                        elif "text" in msg:
                            try:
                                control = json.loads(msg["text"])
                                print("[DEBUG] Received control message:", control)

                                if control.get("type") == "control" and control.get("command") == "__STOP__":
                                    await dg_ws.send(b"")
                                    stop_time = time.perf_counter()
                                    print("[DEBUG] Sent STOP signal to Deepgram")
                                    break
                            except json.JSONDecodeError:
                                continue

                    elif msg["type"] == "websocket.disconnect":
                        print("[DEBUG] WebSocket disconnected by client")
                        break

            except RuntimeError as e:
                print(f"[ERROR] Runtime during receive: {e}")

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
                print(f"[DEBUG] Deepgram stream closed gracefully: {e}")

        await asyncio.gather(forward_audio(), receive_transcript())

        # Optional delay to ensure last packets are received before closing
        # await asyncio.sleep(0.2)
        # await dg_ws.close()

    final_transcript = " ".join(transcript_buffer).strip()

    if stop_time:
        t_end = time.perf_counter()
        print(f"[TIMER] STT-to-LLM latency: {t_end - stop_time:.2f} seconds")

    return final_transcript
