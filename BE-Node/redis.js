// server/redis.js
// ────────────────────────────────────────────────────────────────────────────
import Redis from 'ioredis';
import { REDIS_URL } from './env.js';
const r = new Redis(REDIS_URL);

export const redisGet = async (k) => JSON.parse(await r.get(k) ?? '{}');
export const redisSet = async (k, obj) => r.set(k, JSON.stringify(obj));
