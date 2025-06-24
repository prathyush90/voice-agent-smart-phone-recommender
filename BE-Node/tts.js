// server/tts.js  (patched)
import WebSocket from 'ws';
import { ELEVEN_KEY, ELEVEN_VOICE } from './env.js';

const URL =
  `wss://api.elevenlabs.io/v1/text-to-speech/${ELEVEN_VOICE}/stream-input` +
  '?model_id=eleven_monolingual_v1&inactivity_timeout=30';

export async function* ttsStream(llmTokens) {
  const ws = new WebSocket(URL, { headers: { 'xi-api-key': ELEVEN_KEY } });
  await new Promise((r) => ws.once('open', r));

  /* ----------------------------- send LLM text */
  (async () => {
    let buf = '';
    for await (const tok of llmTokens) {
      buf += tok;
      if (buf.trim().length >= 20) {
        ws.send(JSON.stringify({ text: buf, try_trigger_generation: true }));
        buf = '';
      }
    }
    if (buf) ws.send(JSON.stringify({ text: buf }));
    ws.send(JSON.stringify({ text: '', is_final: true }));
  })();

  /* ---------------------- receive with sequencing */
  const waiting = new Map();   // index -> Buffer
  let   nextIdx = 0;
  let   lastArr = Date.now();

  const flush = function* () {
    while (waiting.has(nextIdx)) {
      yield waiting.get(nextIdx);
      waiting.delete(nextIdx);
      nextIdx += 1;
    }
  };

  while (true) {
    /* race WS message vs 250 ms timer  */
    const res = await Promise.race([
      new Promise((r) => ws.once('message', (d) => r({ kind: 'msg', data: d }))),
      new Promise((r) => setTimeout(() => r({ kind: 'tick' }), 250)),
    ]);

    if (res.kind === 'tick') {
      if (Date.now() - lastArr > 250 && waiting.size) {
        yield* flush();        // push whatever we have
      }
      continue;
    }

    // got a WS message
    lastArr = Date.now();
    const msg = JSON.parse(res.data);

    if (msg.isFinal) break;
    if (msg.audio && typeof msg.index === 'number') {
      waiting.set(msg.index, Buffer.from(msg.audio, 'base64'));
      yield* flush();
    }
  }

  // final drain
  yield* flush();
}
