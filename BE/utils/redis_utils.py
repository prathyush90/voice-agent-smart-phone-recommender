
import redis
import json
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    username="default",
    password=REDIS_PASSWORD,
)

def get_session_data(session_id: str):
    data = r.get(session_id)
    if data:
        return json.loads(data)
    return {"summary": "", "model_id": 1}

def set_session_data(session_id, summary, model_id, extra=None):
    doc = {"summary": summary, "model_id": model_id}
    if extra: doc.update(extra)
    r.set(session_id, json.dumps(doc))

