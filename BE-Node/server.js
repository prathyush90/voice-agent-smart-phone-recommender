// server.js
import WebSocket, { WebSocketServer } from 'ws';
import { pumpSTT } from './deepgram.js';
import { v4 as uuidv4 } from 'uuid';

const PORT = 8000;
const wss = new WebSocketServer({ port: PORT });

console.log(`🛰️  WebSocket server running on ws://localhost:${PORT}`);

wss.on('connection', (ws, req) => {
  const urlParams = new URLSearchParams(req.url.replace(/^.*\?/, ''));
  const sessionId = urlParams.get('session_id') || uuidv4();

  console.log('[WS] client connected →', sessionId);

  pumpSTT(ws, sessionId);

  ws.on('close', () => {
    console.log('[WS] disconnect →', sessionId);
  });
});
