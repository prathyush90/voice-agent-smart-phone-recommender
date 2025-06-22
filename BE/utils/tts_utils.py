import asyncio
import os
import json
import re
import html
import base64
import time
from websockets.legacy.client import connect
from websockets.exceptions import ConnectionClosed

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "Rachel")

def clean_text_for_tts(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"[^\x00-\x7F]+", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


async def stream_tts_audio_websocket(text_stream):
    url = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id=eleven_monolingual_v1&inactivity_timeout=30"
    headers = { "xi-api-key": ELEVENLABS_API_KEY }

    async with connect(url, extra_headers=headers) as ws:
        print("[TTS] Connected to ElevenLabs WebSocket")

        # First buffer to prime config
        buffer = ""
        async for token in text_stream:
            buffer += token.decode("utf-8")
            if len(buffer.strip()) >= 20:
                init_payload = {
                    "text": buffer,
                    "voice_settings": {
                        "stability": 0.3,
                        "similarity_boost": 0.8
                    },
                    "generation_config": {
                        "chunk_length_schedule": [50, 100, 150]
                    },
                    "try_trigger_generation": True
                }
                await ws.send(json.dumps(init_payload))
                print(f"[TTS] Sent config with first chunk")
                break

        # Start sending rest of stream in background
        async def send_rest():
            rest = ""
            async for token in text_stream:
                rest += token.decode("utf-8")
                if len(rest.strip()) >= 20:
                    await ws.send(json.dumps({
                        "text": rest,
                        "try_trigger_generation": True
                    }))
                    rest = ""
            if rest:
                await ws.send(json.dumps({ "text": rest }))
            await ws.send(json.dumps({ "text": "", "is_final": True }))
            print("[TTS] Finished sending all text")

        send_task = asyncio.create_task(send_rest())

        # Receive and yield audio in order
        try:
            first_audio_time = None
            start = time.perf_counter()
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    try:
                        data = json.loads(msg)
                        if data.get("isFinal"):
                            print("[TTS] Final chunk received. Ending TTS stream.")
                            break
                        if "audio" in data and data["audio"]:
                            if not first_audio_time:
                                first_audio_time = time.perf_counter()
                                print(f"[TTS] First audio chunk received after {first_audio_time - start:.2f} seconds")
                            audio_bytes = base64.b64decode(data["audio"])
                            yield audio_bytes
                    except Exception as e:
                        print("[TTS] Failed to parse JSON message:", e)
        except ConnectionClosed as e:
            print("[TTS] WebSocket closed:", e)
        finally:
            await send_task
