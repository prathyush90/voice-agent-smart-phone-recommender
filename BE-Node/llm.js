// server/llm.js
// ────────────────────────────────────────────────────────────────────────────
import OpenAI from 'openai';
import { redisGet, redisSet } from './redis.js';
import { OPENAI_KEY } from './env.js';
const openai = new OpenAI({ apiKey: OPENAI_KEY });

const MODEL = 'gpt-4o-mini';

export async function* llmStream(sessionId, user) {
  const state   = await redisGet(sessionId);
  const summary = state.summary ?? '';

  const sys = `
    You are a friendly, concise smartphone-buying assistant.
    - First ask 2-3 clarifying questions if needed.
    - Then recommend 2-3 phones with brief rationale.
    - Answer follow-up questions without repeating full list.
    Context: ${summary}
  `.trim();

  const stream = await openai.chat.completions.create({
    model: MODEL,
    stream: true,
    messages: [
      { role: 'system', content: sys },
      { role: 'user',   content: user }
    ]
  });

  let full = '';
  for await (const delta of stream) {
    const token = delta.choices[0].delta.content ?? '';
    full += token;
    yield Buffer.from(token, 'utf8');
  }

  // update summary off-thread
  updateSummary(sessionId, summary, user, full).catch(console.error);
}

async function updateSummary(id, prev, user, bot) {
  const prompt = `
    Update the session summary by incorporating any new factual preferences from this turn.
    Keep all previously known details unless directly contradicted.\n
    Do not remove existing information. Only add new or revised facts.\n
    Avoid any tone analysis or generic commentary.\n

    PREVIOUS: «${prev}»
    TURN:     USER «${user}» / BOT «${bot}»

    SUMMARY:
  `;
  const { choices } = await openai.chat.completions.create({
    model: 'gpt-4o-mini', messages: [{ role: 'user', content: prompt }]
  });
  await redisSet(id, { summary: choices[0].message.content.trim() });
}
