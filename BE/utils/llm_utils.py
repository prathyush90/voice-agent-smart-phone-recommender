
import os, asyncio
from openai import OpenAI, AsyncOpenAI
from utils.redis_utils import get_session_data, set_session_data
import time

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_MAP = {
    1: "gpt-4.1-nano",
    2: "gpt-4.1-mini",
    3: "gpt-4.1"
}

MAX_MODEL_ID = max(MODEL_MAP)

# async def is_frustrated(utterance: str) -> bool:
#     try:
#         prompt = (
#             "You are a classifier that detects emotional tone in a user's message.\n"
#             "Respond with only one word: 'frustrated' or 'not frustrated'.\n\n"
#             f"User: \"{utterance}\""
#         )
#
#         resp = client.chat.completions.create(
#             model="gpt-4.1-nano",
#             messages=[{"role": "user", "content": prompt}]
#         )
#
#         classification = resp.choices[0].message.content.strip().lower()
#         print(f"[FRUSTRATION DETECTION] → {classification}")
#         return classification == "frustrated"
#
#     except Exception as e:
#         print("Frustration detection error:", e)
#         return False

# async def is_frustrated(utterance: str) -> bool:
#     try:
#         resp = client.moderations.create(
#             model="text-moderation-latest",
#             input=utterance
#         )
#         scores = resp.results[0].category_scores
#         print("[MODERATION SCORES]")
#         for category, value in scores.__dict__.items():
#             print(f"  {category}: {value}")
#         # return (scores.harassment or 0.0) > 0.35
#         return False
#     except Exception as e:
#         print("Moderation API error:", e)
#         bad_words = ["useless", "annoying", "not helpful", "waste of time", "you never"]
#         return any(w in utterance.lower() for w in bad_words)

# async def decide_model(session_id: str, user_utterance: str) -> int:
#     state = get_session_data(session_id)
#     print(state)
#     cur_id = state.get("model_id", 1)
#     dissatisfied = state.get("dissatisfied_count", 0)
#
#     if await is_frustrated(user_utterance):
#         print("enetering frustrated loop")
#         dissatisfied += 1
#     else:
#         print("enetering no-frustrated loop")
#         dissatisfied = max(0, dissatisfied - 1)
#
#     if dissatisfied >= 2 and cur_id < MAX_MODEL_ID:
#         cur_id += 1
#         dissatisfied = 0
#
#     set_session_data(
#         session_id,
#         summary=state.get("summary", ""),
#         model_id=cur_id,
#         extra={"dissatisfied_count": dissatisfied}
#     )
#     return cur_id

async def stream_llm_response(session_id: str, user_utterance: str):
    # model_id = await decide_model(session_id, user_utterance)
    model_id = 1
    model = MODEL_MAP[model_id]

    print(f" Using model: {model} for session: {session_id}")
    state = get_session_data(session_id)
    summary = state.get("summary", "")
    print(summary)
    system_prompt = f"""
    You are a friendly, concise smartphone-buying assistant.
    - First ask 2-3 clarifying questions if needed.
    - Then recommend 2-3 phones with brief rationale.
    - Answer follow-up questions without repeating full list.
    Context: {summary}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_utterance}
    ]
    t0 = time.perf_counter()
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)

    full_reply = ""
    first_token_time = None
    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if not first_token_time and token.strip():
            first_token_time = time.perf_counter()
            print(f"\n⏱️ First token latency: {first_token_time - t0:.2f} seconds")
        full_reply += token
        yield token.encode("utf-8")
    print(full_reply)
    asyncio.create_task(_update_summary(session_id, summary, user_utterance, full_reply))

async def _update_summary(session_id: str, old_summary: str, user_msg: str, bot_msg: str):
    try:
        print("creating summary")
        summary_prompt = (
            "Update the session summary by incorporating any new factual preferences from this turn.\n"
            "Keep all previously known details unless directly contradicted.\n"
            "Do not remove existing information. Only add new or revised facts.\n"
            "Avoid any tone analysis or generic commentary.\n\n"
            f"Previous summary:\n«{old_summary}»\n\n"
            f"New turn:\nUSER: «{user_msg}»\nASSISTANT: «{bot_msg}»\n\n"
            "Updated summary:"
        )

        resp = await async_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": summary_prompt}]
        )

        new_summary = resp.choices[0].message.content.strip()
        prev = get_session_data(session_id)
        set_session_data(
            session_id,
            summary=new_summary,
            model_id=prev["model_id"],
            extra={"dissatisfied_count": prev.get("dissatisfied_count", 0)}
        )
        print("completed summary")
    except Exception as e:
        print("summary-update error:", e)
