// deepgram.js
import { createClient, LiveTranscriptionEvents } from "@deepgram/sdk"
import { DEEPGRAM_KEY } from './env.js';

const dg = createClient(DEEPGRAM_KEY);

let keepAlive
export function pumpSTT(ws, sessionId) {

  if (keepAlive) clearInterval(keepAlive);
  keepAlive = setInterval(() => {
    console.log("deepgram: keepalive");
    deepgram.keepAlive();
  }, 10 * 1000);

  console.log("isnide pump stt")
  const deepgramLive = dg.listen.live({
    model: 'nova-2',         
    language: 'en-US',
    encoding: 'opus',        
    sample_rate: 48000,      
  });
  deepgramLive.on(LiveTranscriptionEvents.Open, () => {
    console.log(`[DG] ${sessionId} → connected`);
  });

  deepgramLive.on(LiveTranscriptionEvents.Metadata, () => {
    console.log(`[DG] ${sessionId} → Metadata`);
  });

  deepgramLive.on(LiveTranscriptionEvents.Transcript, (data) => {
    const msg = JSON.parse(data);
    const transcript = msg.channel?.alternatives?.[0]?.transcript;
    if (transcript) {
      console.log(`[DG] ${sessionId} → ${transcript}`);
      // You can plug in LLM and TTS here...
      // ws.send(JSON.stringify({ transcript }));
    }
  });

  deepgramLive.on(LiveTranscriptionEvents.Error, (err) => {
    console.error(`[DG] ${sessionId} error:`, err);
  });

  deepgramLive.on(LiveTranscriptionEvents.Close, () => {
    console.log(`[DG] ${sessionId} closed`);
  });

  // receive and forward mic data
  ws.on('message', (data) => {
    if (typeof data === 'string') return; // ignore __START__ control messages
    console.log("Sending message")
    deepgramLive.send(data);
  });

  ws.on('close', () => {
    deepgramLive.finish();
  });
}

//const watchdog = setInterval(async () => {
  //   const elapsed = Date.now() - lastSpeechTs;
  //   if (!partials.length || elapsed < 500) return;

  //   const utterance = partials.join(' ').trim();
  //   partials = [];

  //   const llm = llmStream(sessionId, utterance);
  //   const tts = ttsStream(llm);

  //   for await (const chunk of tts) {
  //     if (client.readyState === WebSocket.OPEN) {
  //       client.send(chunk);
  //     }
  //   }

  //   if (client.readyState === WebSocket.OPEN) {
  //     client.send('__END__');
  //   }
  // }, 200);


  // dg.on('close', () => clearInterval(watchdog));
