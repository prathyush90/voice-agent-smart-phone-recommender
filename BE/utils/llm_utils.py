# utils/llm_utils.py

import os
import asyncio
import time
from openai import OpenAI
from utils.redis_utils import get_session_data, set_session_data

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_MAP = {
    1: "gpt-4o-mini",
    2: "gpt-4.1-nano",
    3: "gpt-4.1-mini",
    4: "gpt-4.1"
}


async def update_summary(session_id: str, prev_summary: str, user: str, bot: str):
    prompt = (
        "Update the session summary by incorporating any new factual preferences from this turn.\n"
        "Keep all previously known details unless directly contradicted.\n"
        "Do not remove existing information. Only add new or revised facts.\n"
        "Avoid any tone analysis or generic commentary.\n\n"
        f"Previous summary:\n«{prev_summary}»\n\n"
        f"New turn:\nUSER: «{user}»\nASSISTANT: «{bot}»\n\n"
        "Updated summary:"
    )
    # offload blocking call to thread
    resp = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=MODEL_MAP[get_session_data(session_id).get("model_id", 1)],
            messages=[{"role": "user", "content": prompt}],
        )
    )
    new_summary = resp.choices[0].message.content.strip()

    prev = get_session_data(session_id) or {}
    set_session_data(
        session_id,
        summary=new_summary,
        model_id=prev.get("model_id", 1),
        extra={"dissatisfied_count": prev.get("dissatisfied_count", 0)},
    )
    print(f"[LLM] Summary updated for session {session_id!r}")


async def llm_stream(session_id: str, user_text: str):
    """
    Async generator yielding raw UTF-8 bytes of each LLM token,
    iterating the sync client generator with a normal for-loop.
    """
    print("[LLM] init")

    # 1️⃣ load existing summary
    state   = get_session_data(session_id) or {}
    summary = state.get("summary", "")
    print(f"[LLM] Loaded summary (len={len(summary)}): {summary!r}")

    # choose model
    model_id = state.get("model_id", 1)
    model    = MODEL_MAP.get(model_id, MODEL_MAP[1])
    print(f"[LLM] Using model: {model} for session: {session_id}")

    # 2️⃣ build system prompt
    system_prompt = f"""
You are a friendly, concise smartphone-buying assistant.
- First ask 2-3 clarifying questions if needed.
- Then recommend 2-3 phones with brief rationale.
- Answer follow-up questions without repeating full list.
Context: {summary}
""".strip()
    print("[LLM] Calling OpenAI with user text:", user_text)

    # 3️⃣ blocking, synchronous stream generator offloaded to thread
    resp = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=model,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text     },
            ],
        )
    )

    full_reply = ""
    t0 = time.perf_counter()
    first_token_time = None

    # **regular** for-loop over the sync generator
    for chunk in resp:
        token = chunk.choices[0].delta.content or ""
        if not first_token_time and token.strip():
            first_token_time = time.perf_counter()
            print(f"[LLM] First token latency: {first_token_time - t0:.2f} sec")
        full_reply += token
        yield token.encode("utf-8")

    print(f"[LLM] Full reply collected ({len(full_reply)} chars)")
    # 4️⃣ update summary in background
    asyncio.create_task(
        update_summary(session_id, summary, user_text, full_reply)
    )
    print("[LLM] Stream complete, summary update scheduled")
