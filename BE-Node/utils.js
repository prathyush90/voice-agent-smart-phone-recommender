// server/utils.js
export const clean = (t) =>
  t.replace(/<[^>]+>/g, '')
   .replace(/[*_~`]/g, '')
   .replace(/[^\x00-\x7F]+/g, '')
   .replace(/\s{2,}/g, ' ')
   .trim();
