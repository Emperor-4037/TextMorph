import axios from 'axios';

const API_BASE = '';
const DEMO_TOKEN = import.meta.env.VITE_DEMO_TOKEN ?? 'demo-token';

const api = axios.create({
  baseURL: API_BASE,
  headers: { Authorization: `Bearer ${DEMO_TOKEN}` },
  timeout: 60_000,
});

export const paraphrase = (text, tone = 'neutral') =>
  api.post('/api/paraphrase', { text, tone });

export const grammar = (text) =>
  api.post('/api/grammar', { text });

export const simplify = (text, reading_level = 'middle school') =>
  api.post('/api/simplify', { text, reading_level });

export const tone = (text, target_tone = 'professional') =>
  api.post('/api/tone', { text, target_tone });

export const summarize = (text, max_length = 150) =>
  api.post('/api/summarize', { text, max_length });
