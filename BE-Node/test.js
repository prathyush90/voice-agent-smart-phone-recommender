// test.js (absolute bare minimum)
import { createClient, LiveTranscriptionEvents } from "@deepgram/sdk";
import { DEEPGRAM_KEY } from './env.js';

if (!DEEPGRAM_KEY) {
    console.error("DEEPGRAM_KEY is not defined in env.js!");
    process.exit(1);
}

// Optional: Add global unhandled promise rejection/uncaught exception handlers
// as discussed previously, at the very top of this file.
process.on('unhandledRejection', (reason, promise) => {
  console.error('UNHANDLED REJECTION in test.js:', reason);
});
process.on('uncaughtException', (error) => {
  console.error('UNCAUGHT EXCEPTION in test.js:', error);
  process.exit(1);
});

const deepgram = createClient(DEEPGRAM_KEY); // Using the variable from env.js

console.log("Attempting to connect to Deepgram...");
const deepgramLive = deepgram.listen.live({
    model: 'nova-2',
    language: 'en-US',
    encoding: 'opus',
    sample_rate: 48000,
});

deepgramLive.on(LiveTranscriptionEvents.Open, () => {
    console.log('[DG Test] Deepgram connection OPENED successfully!');
    deepgramLive.finish(); // Close after confirming open
    deepgramLive.close();
});

deepgramLive.on(LiveTranscriptionEvents.Close, () => {
    console.log('[DG Test] Deepgram connection CLOSED.');
});

deepgramLive.on(LiveTranscriptionEvents.Error, (err) => {
    console.error('[DG Test] Deepgram connection ERROR:', err);
    // Log the full error object for more details
    console.error('Error object:', JSON.stringify(err, null, 2));
    deepgramLive.close();
});

// If no events fire, this warns
setTimeout(() => {
    console.warn('[DG Test] No Deepgram events (open/error) after 10 seconds. This is unexpected.');
    deepgramLive.close();
}, 10000);