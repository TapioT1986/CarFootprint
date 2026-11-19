// CarFootprint feedback receiver: a Cloudflare Worker (free plan) that turns feedback from the page into issues
// in the owner's private GitHub repository. Licence AGPL-3.0, like the page.
//
// What it stores: the thumb (up/down), the text the user wrote, the share link if the user ticked "attach my
// comparison", the page version and language, and the time. Nothing else: no IP address, no cookies, no user agent.
// The IP address is used only in memory for a short rate limit (below) and is never written anywhere.
//
// Setup (Cloudflare dashboard -> Workers & Pages -> this worker -> Settings -> Variables and Secrets):
//   GITHUB_TOKEN  secret: fine-grained GitHub token with only "Issues: Read and write" on the feedback repository
//   REPO          text:   owner/name of the private feedback repository, e.g. TapioT1986/CarFootprint-palaute
//
// API (JSON over POST, only from the page's own address):
//   {vote:"up"|"down", lang, version}                 -> {ok:true, id, key}   creates an issue
//   {id, key, text, link, lang, version}              -> {ok:true}            adds the optional details as a comment
//   {text, link, lang, version} (no vote, no id)      -> {ok:true, id, key}   text-only feedback, creates an issue
//   website (honeypot field, hidden from people): if filled in, the request is accepted and silently dropped.

const ORIGINS = ['https://tapiot1986.github.io', 'http://127.0.0.1:8765', 'http://localhost:8765'];
const LINK_PREFIX = 'https://tapiot1986.github.io/CarFootprint/#s=';
const MAX_TEXT = 2000, MAX_LINK = 2000, MAX_BODY = 6000;
const RATE_N = 6, RATE_MS = 10 * 60 * 1000;   // at most 6 requests per 10 minutes from one address (in memory only)
const recent = new Map();

function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function reply(origin, status, obj) {
  return new Response(JSON.stringify(obj), {status, headers: {'Content-Type': 'application/json', ...cors(origin)}});
}

function limited(ip) {
  const now = Date.now();
  for (const [k, t] of recent) if (now - t[t.length - 1] > RATE_MS) recent.delete(k);
  const t = (recent.get(ip) || []).filter(x => now - x < RATE_MS);
  t.push(now);
  recent.set(ip, t);
  return t.length > RATE_N;
}

// A key that lets the same browser add details to the issue it just created, and nobody else
async function sign(secret, id) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), {name: 'HMAC', hash: 'SHA-256'}, false, ['sign']);
  const s = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode('carfootprint-feedback:' + id));
  return [...new Uint8Array(s)].slice(0, 16).map(b => b.toString(16).padStart(2, '0')).join('');
}

function clean(s, max) {
  return typeof s === 'string' ? s.replace(/\r\n?/g, '\n').replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, '').trim().slice(0, max) : '';
}

// User text is shown as a quote, so Markdown in it cannot ping people or add links to the issue layout
function quote(text) {
  return text.split('\n').map(l => '> ' + l.replace(/@/g, '@​')).join('\n');
}

async function github(env, path, body) {
  const r = await fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'carfootprint-feedback-worker',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return r.json();
}

function details(d) {
  const lines = [];
  if (d.text) lines.push(quote(d.text), '');
  if (d.link) lines.push(`Vertailu / comparison: ${d.link}`, '');
  lines.push(`Versio ${d.version || '?'} · kieli ${d.lang || '?'} · ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC`);
  return lines.join('\n');
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (!ORIGINS.includes(origin)) return new Response('Forbidden', {status: 403});
    if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: cors(origin)});
    if (request.method !== 'POST') return reply(origin, 405, {ok: false});
    if (!env.GITHUB_TOKEN || !env.REPO) return reply(origin, 500, {ok: false, error: 'not configured'});

    const raw = await request.text();
    if (raw.length > MAX_BODY) return reply(origin, 413, {ok: false});
    let d;
    try { d = JSON.parse(raw); } catch { return reply(origin, 400, {ok: false}); }
    if (d.website) return reply(origin, 200, {ok: true});   // honeypot: a bot filled in the hidden field

    if (limited(request.headers.get('CF-Connecting-IP') || '')) return reply(origin, 429, {ok: false, error: 'rate'});

    const vote = d.vote === 'up' ? '👍' : d.vote === 'down' ? '👎' : '';
    const text = clean(d.text, MAX_TEXT);
    let link = clean(d.link, MAX_LINK);
    if (link && !link.startsWith(LINK_PREFIX)) link = '';
    const lang = d.lang === 'en' ? 'en' : 'fi', version = clean(String(d.version ?? ''), 20);

    try {
      // Details for an issue this browser just created
      if (d.id) {
        const id = parseInt(d.id, 10);
        if (!id || d.key !== await sign(env.GITHUB_TOKEN, id)) return reply(origin, 403, {ok: false});
        if (!text && !link) return reply(origin, 400, {ok: false});
        await github(env, `/issues/${id}/comments`, {body: details({text, link, lang, version})});
        return reply(origin, 200, {ok: true});
      }
      if (!vote && !text) return reply(origin, 400, {ok: false});
      const title = [vote, text ? text.split('\n')[0].slice(0, 70) : (lang === 'en' ? 'Thumb only' : 'Pelkkä peukku')].filter(Boolean).join(' ');
      const issue = await github(env, '/issues', {title, body: details({text, link, lang, version})});
      return reply(origin, 200, {ok: true, id: issue.number, key: await sign(env.GITHUB_TOKEN, issue.number)});
    } catch (e) {
      return reply(origin, 502, {ok: false, error: 'github'});
    }
  },
};
