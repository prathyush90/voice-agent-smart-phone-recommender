// server/env.js
import dotenv from 'dotenv';
dotenv.config();

export const DEEPGRAM_KEY = process.env.DEEPGRAM_API_KEY  || '';
export const ELEVEN_KEY   = process.env.ELEVENLABS_API_KEY || '';
export const ELEVEN_VOICE = process.env.ELEVENLABS_VOICE_ID || 'Rachel';
export const OPENAI_KEY   = process.env.OPENAI_API_KEY     || '';
export const REDIS_URL    = process.env.REDIS_URL          || 'redis://127.0.0.1:6379';
