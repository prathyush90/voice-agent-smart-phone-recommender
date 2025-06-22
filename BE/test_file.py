from dotenv import load_dotenv
load_dotenv()

import asyncio
import time
from utils.llm_utils import stream_llm_response


async def test_llm():
    session_id = "test-session-123"
    user_input = "What the hell did i just say man no other preferences. Have i not made myself very clear?"
    print(user_input)
    print("Streaming LLM response:\n")
    t0 = time.perf_counter()

    full_output = ""
    async for token in stream_llm_response(session_id, user_input):
        chunk = token.decode("utf-8")
        print(chunk, end="", flush=True)
        full_output += chunk

    t1 = time.perf_counter()
    print(f"\n\n⏱️ Total LLM latency: {t1 - t0:.2f} seconds")
    print(f"\n📄 Final output length: {len(full_output)} characters")

asyncio.run(test_llm())
