# utils/tts_utils.py

import os, json, re, html, base64, time, asyncio
from websockets.legacy.client import connect
from websockets.exceptions import ConnectionClosed

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID           = os.getenv("ELEVENLABS_VOICE_ID", "Rachel")

def clean_text_for_tts(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"[^\x00-\x7F]+", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

async def tts_stream(llm_token_stream):
    url     = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input"
        "?model_id=eleven_monolingual_v1&inactivity_timeout=30"
    )
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    async with connect(url, extra_headers=headers) as ws:
        print("[TTS] Connected to ElevenLabs WebSocket")

        # ── 1) Prime with initial settings ───────────────────────
        buffer = ""
        async for tok in llm_token_stream:
            buffer += tok.decode("utf-8")
            if len(buffer.strip()) >= 10:
                init_payload = {
                    "text": clean_text_for_tts(buffer),
                    "voice_settings": {"stability": 0.3, "similarity_boost": 0.8},
                    "generation_config": {"chunk_length_schedule": [50, 100, 150]},
                    "try_trigger_generation": True,
                }
                await ws.send(json.dumps(init_payload))
                print("[TTS] Sent initial config payload")
                break

        # ── 2) Background sender for the rest ────────────────────
        async def send_rest():
            rest = ""
            async for tok in llm_token_stream:
                rest += tok.decode("utf-8")
                if len(rest.strip()) >= 50:
                    payload = {
                        "text": clean_text_for_tts(rest),
                        "try_trigger_generation": True,
                    }
                    await ws.send(json.dumps(payload))
                    print("[TTS] Sent chunk payload")
                    rest = ""
            if rest:
                await ws.send(json.dumps({"text": clean_text_for_tts(rest)}))
            await ws.send(json.dumps({"text": "", "is_final": True}))
            print("[TTS] Finished sending all text")

        send_task = asyncio.create_task(send_rest())

        # ── 3) Receive & yield audio immediately ─────────────────
        start = time.perf_counter()
        first_audio_time = None

        try:
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)

                # end-of-stream
                if msg.get("isFinal"):
                    print("[TTS] Final chunk received. Ending TTS stream.")
                    break

                # audio chunk
                audiob64 = msg.get("audio")
                if audiob64:
                    if not first_audio_time:
                        first_audio_time = time.perf_counter()
                        print(f"[TTS] First audio chunk after {first_audio_time - start:.2f}s")
                    audio_bytes = base64.b64decode(audiob64)
                    yield audio_bytes

        except ConnectionClosed as e:
            print("[TTS] WebSocket closed:", e)
        finally:
            # ensure the sender finishes before we exit
            await send_task
            print("[TTS] send_rest task done")
