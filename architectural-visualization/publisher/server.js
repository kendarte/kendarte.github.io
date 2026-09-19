const http = require('node:http');
const crypto = require('node:crypto');
const { URL } = require('node:url');
const Busboy = require('busboy');
const { Pool } = require('pg');

const port = Number(process.env.PORT || 3000);
const publicUrl = String(process.env.PUBLIC_URL || '').replace(/\/$/, '');
const setupSecret = process.env.SETUP_SECRET || '';
const databaseUrl = process.env.DATABASE_URL || '';
const allowedOrigin = 'https://kendarte.github.io';
const repo = 'kendarte/kendarte.github.io';
const base = 'architectural-visualization';
const ownerLogin = 'kendarte';

if (!publicUrl || !setupSecret || !databaseUrl) {
  throw new Error('PUBLIC_URL, SETUP_SECRET and DATABASE_URL are required.');
}

const pool = new Pool({ connectionString: databaseUrl });

function now() { return Date.now(); }
function b64url(value) { return Buffer.from(value).toString('base64url'); }
function randomToken() { return crypto.randomBytes(32).toString('base64url'); }
function timingSafeEqual(a, b) {
  const left = Buffer.from(String(a));
  const right = Buffer.from(String(b));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}
function sign(value) {
  return crypto.createHmac('sha256', setupSecret).update(value).digest('base64url');
}
function validSetupState(value) {
  const parts = String(value || '').split('.');
  if (parts.length !== 2) return false;
  const issued = Number(parts[0]);
  return Number.isFinite(issued) && now() - issued < 3600000 && timingSafeEqual(parts[1], sign(parts[0]));
}
function htmlEscape(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  })[character]);
}
function send(res, status, contentType, body, headers = {}) {
  res.writeHead(status, { 'Content-Type': contentType, 'Cache-Control': 'no-store', ...headers });
  res.end(body);
}
function json(res, status, payload, headers = {}) {
  send(res, status, 'application/json; charset=utf-8', JSON.stringify(payload), headers);
}
function page(res, status, title, content) {
  send(res, status, 'text/html; charset=utf-8', `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${htmlEscape(title)}</title><style>body{margin:0;background:#0b0d10;color:#f4f5f6;font:16px/1.5 Arial,sans-serif;padding:40px;max-width:760px}a,button{background:#d9c3a3;color:#111;border:0;border-radius:7px;padding:11px 14px;font-weight:700;text-decoration:none;cursor:pointer}.box{background:#14171b;border:1px solid #343a40;border-radius:12px;padding:24px}p{color:#c5c9cc}</style><main class="box">${content}</main>`);
}
function corsHeaders(req) {
  return req.headers.origin === allowedOrigin ? {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Vary': 'Origin'
  } : {};
}
function requireEditorOrigin(req, res) {
  if (req.headers.origin !== allowedOrigin) {
    json(res, 403, { error: 'This endpoint accepts requests only from the editor.' });
    return false;
  }
  return true;
}
async function init() {
  await pool.query(`CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());`);
  await pool.query(`CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, purpose TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb);`);
  await pool.query(`CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions (expires_at);`);
}
async function setSetting(key, value) {
  await pool.query(`INSERT INTO settings (key,value,updated_at) VALUES ($1,$2::jsonb,NOW()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()`, [key, JSON.stringify(value)]);
}
async function getSetting(key) {
  const result = await pool.query(`SELECT value FROM settings WHERE key=$1`, [key]);
  return result.rowCount ? result.rows[0].value : null;
}
async function createSession(purpose, payload, lifetimeMs) {
  const token = randomToken();
  await pool.query(`INSERT INTO sessions (token,purpose,expires_at,payload) VALUES ($1,$2,to_timestamp($3 / 1000.0),$4::jsonb)`, [token, purpose, now() + lifetimeMs, JSON.stringify(payload || {})]);
  return token;
}
async function takeSession(token, purpose) {
  const result = await pool.query(`DELETE FROM sessions WHERE token=$1 AND purpose=$2 AND expires_at>NOW() RETURNING payload`, [token, purpose]);
  return result.rowCount ? result.rows[0].payload : null;
}
async function getSession(token, purpose) {
  const result = await pool.query(`SELECT payload FROM sessions WHERE token=$1 AND purpose=$2 AND expires_at>NOW()`, [token, purpose]);
  return result.rowCount ? result.rows[0].payload : null;
}
function appJwt(config) {
  const issued = Math.floor(now() / 1000);
  const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const payload = b64url(JSON.stringify({ iat: issued - 60, exp: issued + 540, iss: String(config.appId) }));
  const data = `${header}.${payload}`;
  const signer = crypto.createSign('RSA-SHA256');
  signer.update(data);
  signer.end();
  return `${data}.${signer.sign(config.privateKey, 'base64url')}`;
}
async function installationToken(config) {
  const result = await fetch(`https://api.github.com/app/installations/${config.installationId}/access_tokens`, {
    method: 'POST',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${appJwt(config)}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'Kendarte-Archviz-Publisher'
    }
  });
  if (!result.ok) throw new Error(`GitHub installation access failed (${result.status}).`);
  return (await result.json()).token;
}
async function github(token, path, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${repo}/${path}`, {
    method: options.method || 'GET',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'Kendarte-Archviz-Publisher',
      ...(options.body ? { 'Content-Type': 'application/json' } : {})
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  if (!response.ok) {
    let message = `GitHub request failed (${response.status}).`;
    try { message = (await response.json()).message || message; } catch (_) {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}
function extension(mime) {
  if (mime === 'image/png') return 'png';
  if (mime === 'image/webp') return 'webp';
  return 'jpg';
}
function slug(value) {
  return String(value || 'item').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'item';
}
function ensurePortfolio(value) {
  if (!value || typeof value !== 'object' || !value.site || !Array.isArray(value.projects)) throw new Error('Invalid portfolio data.');
}
async function parsePublish(req) {
  return new Promise((resolve, reject) => {
    const fields = {};
    const files = new Map();
    let failed = false;
    const parser = Busboy({ headers: req.headers, limits: { files: 60, fields: 10, fileSize: 95 * 1024 * 1024 } });
    parser.on('field', (name, value) => { fields[name] = value; });
    parser.on('file', (name, stream, info) => {
      const chunks = [];
      let size = 0;
      let limited = false;
      stream.on('data', chunk => { size += chunk.length; chunks.push(chunk); });
      stream.on('limit', () => { limited = true; });
      stream.on('end', () => {
        if (limited) { failed = true; return; }
        if (name === 'file' && info.filename) files.set(info.filename, { buffer: Buffer.concat(chunks, size), mime: info.mimeType });
      });
    });
    parser.on('error', reject);
    parser.on('finish', () => {
      if (failed) reject(new Error('One image exceeds the 95 MB limit.'));
      else resolve({ fields, files });
    });
    req.pipe(parser);
  });
}
function draftEntries(portfolio) {
  const entries = [];
  if (portfolio.heroImage && portfolio.heroImage.type === 'draft') entries.push({ image: portfolio.heroImage, replace: value => { portfolio.heroImage = value; }, kind: 'hero', project: null, shot: null });
  portfolio.projects.forEach(project => (project.shots || []).forEach(shot => {
    if (shot.image && shot.image.type === 'draft') entries.push({ image: shot.image, replace: value => { shot.image = value; }, kind: 'shot', project, shot });
  }));
  return entries;
}
async function publishPortfolio(portfolio, files) {
  ensurePortfolio(portfolio);
  const config = await getSetting('githubApp');
  if (!config || !config.installationId) throw new Error('Publisher setup is incomplete.');
  const token = await installationToken(config);
  const result = JSON.parse(JSON.stringify(portfolio));
  const uploads = draftEntries(result);
  for (let index = 0; index < uploads.length; index += 1) {
    const item = uploads[index];
    const file = files.get(item.image.key);
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.mime)) throw new Error('A selected image is missing or invalid.');
    const stamp = `${Date.now()}-${index}`;
    const filename = item.kind === 'hero'
      ? `hero-${stamp}.${extension(file.mime)}`
      : `${slug(item.project.id)}-${slug(item.shot.id)}-${stamp}.${extension(file.mime)}`;
    const path = `${base}/media/${filename}`;
    await github(token, `contents/${path}`, {
      method: 'PUT',
      body: { message: `Publish archviz image: ${filename}`, content: file.buffer.toString('base64'), branch: 'main' }
    });
    item.replace({
      type: 'file',
      src: `media/${filename}`,
      alt: item.kind === 'hero' ? 'Architectural visualization hero' : (item.shot.label || item.project.title || 'Architectural visualization')
    });
  }
  const current = await github(token, `contents/${base}/portfolio.json?ref=main`);
  const update = await github(token, `contents/${base}/portfolio.json`, {
    method: 'PUT',
    body: {
      message: 'Publish architectural visualization portfolio',
      content: Buffer.from(JSON.stringify(result, null, 2)).toString('base64'),
      sha: current.sha,
      branch: 'main'
    }
  });
  return { portfolio: result, commit: update && update.commit ? update.commit.sha : null };
}
async function handle(req, res) {
  const url = new URL(req.url, publicUrl);
  if (req.method === 'OPTIONS') return send(res, 204, 'text/plain', '', corsHeaders(req));
  if (url.pathname === '/health') return json(res, 200, { ok: true });

  if (url.pathname === '/setup') {
    if (!timingSafeEqual(url.searchParams.get('key') || '', setupSecret)) return page(res, 404, 'Not found', '<h1>Not found</h1>');
    const issued = String(now());
    const state = `${issued}.${sign(issued)}`;
    const manifest = {
      name: 'Kendarte Archviz Publisher',
      url: publicUrl,
      description: 'Publishes the Kendarte architectural visualization portfolio.',
      hook_attributes: { url: `${publicUrl}/webhooks`, active: false },
      redirect_url: `${publicUrl}/setup/callback`,
      callback_urls: [`${publicUrl}/auth/callback`],
      setup_url: `${publicUrl}/setup/installed?key=${encodeURIComponent(setupSecret)}`,
      public: false,
      default_events: [],
      default_permissions: { contents: 'write', metadata: 'read' }
    };
    return page(res, 200, 'Create publisher connection', `<h1>Connect publisher</h1><p>This creates one private GitHub App restricted to the portfolio repository.</p><form action="https://github.com/settings/apps/new?state=${encodeURIComponent(state)}" method="post"><input type="hidden" name="manifest" value="${htmlEscape(JSON.stringify(manifest))}"><button type="submit">Create GitHub App</button></form>`);
  }

  if (url.pathname === '/setup/callback') {
    if (!validSetupState(url.searchParams.get('state')) || !url.searchParams.get('code')) return page(res, 400, 'Setup failed', '<h1>Setup failed</h1><p>The setup link expired. Start it again.</p>');
    const conversion = await fetch(`https://api.github.com/app-manifests/${encodeURIComponent(url.searchParams.get('code'))}/conversions`, { method: 'POST', headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'Kendarte-Archviz-Publisher' } });
    if (!conversion.ok) throw new Error('GitHub could not create the publisher app.');
    const app = await conversion.json();
    await setSetting('githubApp', { appId: app.id, clientId: app.client_id, clientSecret: app.client_secret, privateKey: app.pem, webhookSecret: app.webhook_secret, slug: app.slug, installationId: null });
    const installUrl = `${app.html_url}/installations/new`;
    return page(res, 200, 'Install publisher', `<h1>App created</h1><p>Install it only on <b>kendarte.github.io</b>.</p><a href="${htmlEscape(installUrl)}">Install publisher</a>`);
  }

  if (url.pathname === '/setup/installed') {
    if (!timingSafeEqual(url.searchParams.get('key') || '', setupSecret)) return page(res, 404, 'Not found', '<h1>Not found</h1>');
    const installationId = url.searchParams.get('installation_id');
    const config = await getSetting('githubApp');
    if (!config || !installationId) return page(res, 400, 'Installation failed', '<h1>Installation failed</h1><p>GitHub did not return the installation.</p>');
    config.installationId = Number(installationId);
    await setSetting('githubApp', config);
    return page(res, 200, 'Publisher connected', `<h1>Publisher connected</h1><p>Return to the editor and press PUBLISH TO SITE. The first use signs in with GitHub; it never asks for a token.</p><a href="${allowedOrigin}/architectural-visualization/editor.html">Open editor</a>`);
  }

  if (url.pathname === '/auth/start') {
    const config = await getSetting('githubApp');
    if (!config || !config.installationId) return json(res, 409, { error: 'Publisher is not connected yet.' }, corsHeaders(req));
    const state = await createSession('oauth-state', {}, 10 * 60 * 1000);
    const authorize = new URL('https://github.com/login/oauth/authorize');
    authorize.searchParams.set('client_id', config.clientId);
    authorize.searchParams.set('redirect_uri', `${publicUrl}/auth/callback`);
    authorize.searchParams.set('state', state);
    res.writeHead(302, { Location: authorize.toString(), 'Cache-Control': 'no-store' });
    return res.end();
  }

  if (url.pathname === '/auth/callback') {
    const state = url.searchParams.get('state');
    const code = url.searchParams.get('code');
    if (!state || !code || !await takeSession(state, 'oauth-state')) return page(res, 400, 'Sign in failed', '<h1>Sign in failed</h1><p>Start publishing again from the editor.</p>');
    const config = await getSetting('githubApp');
    const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Kendarte-Archviz-Publisher' },
      body: JSON.stringify({ client_id: config.clientId, client_secret: config.clientSecret, code, redirect_uri: `${publicUrl}/auth/callback` })
    });
    const oauth = await tokenResponse.json();
    if (!oauth.access_token) return page(res, 401, 'Sign in failed', '<h1>Sign in failed</h1><p>GitHub did not approve access.</p>');
    const identityResponse = await fetch('https://api.github.com/user', { headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${oauth.access_token}`, 'User-Agent': 'Kendarte-Archviz-Publisher' } });
    const identity = await identityResponse.json();
    if (identity.login !== ownerLogin) return page(res, 403, 'Not authorized', '<h1>Not authorized</h1><p>This editor is restricted to the repository owner.</p>');
    const session = await createSession('editor', { login: identity.login }, 30 * 24 * 60 * 60 * 1000);
    const target = JSON.stringify(allowedOrigin);
    return page(res, 200, 'Signed in', `<h1>Signed in</h1><p>Returning to the editor…</p><script>if(window.opener){window.opener.postMessage({type:'archviz-publish-session',session:${JSON.stringify(session)}},${target});window.close();}</script>`);
  }

  if (url.pathname === '/publish' && req.method === 'POST') {
    if (!requireEditorOrigin(req, res)) return;
    const match = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || '');
    if (!match || !await getSession(match[1], 'editor')) return json(res, 401, { error: 'Sign in required.' }, corsHeaders(req));
    try {
      const incoming = await parsePublish(req);
      const portfolio = JSON.parse(incoming.fields.portfolio || '');
      const published = await publishPortfolio(portfolio, incoming.files);
      return json(res, 200, { commit: published.commit, portfolio: published.portfolio }, corsHeaders(req));
    } catch (error) {
      return json(res, 400, { error: error.message || 'Publish failed.' }, corsHeaders(req));
    }
  }

  return page(res, 404, 'Not found', '<h1>Not found</h1>');
}

init().then(() => http.createServer((req, res) => {
  handle(req, res).catch(error => {
    console.error(error);
    if (!res.headersSent) json(res, 500, { error: 'Publisher error.' }, corsHeaders(req));
    else res.end();
  });
}).listen(port, '0.0.0.0', () => console.log(`Publisher listening on ${port}`))).catch(error => {
  console.error(error);
  process.exit(1);
});
