const http = require('node:http');
const crypto = require('node:crypto');
const { URL } = require('node:url');
const Busboy = require('busboy');

const port = Number(process.env.PORT || 3000);
const publicUrl = String(process.env.PUBLIC_URL || '').replace(/\/$/, '');
const setupSecret = process.env.SETUP_SECRET || '';
const configValue = process.env.GITHUB_OAUTH_CONFIG || '';
const editorOrigin = 'https://kendarte.github.io';
const repo = 'kendarte/kendarte.github.io';
const base = 'architectural-visualization';
const ownerLogin = 'kendarte';
const pendingApps = new Map();

if (!publicUrl || !setupSecret) throw new Error('PUBLIC_URL and SETUP_SECRET are required.');

function now() { return Date.now(); }
function randomToken() { return crypto.randomBytes(32).toString('base64url'); }
function b64url(value) { return Buffer.from(value).toString('base64url'); }
function decode(value) { return JSON.parse(Buffer.from(String(value), 'base64url').toString('utf8')); }
function timingSafeEqual(a, b) {
  const left = Buffer.from(String(a));
  const right = Buffer.from(String(b));
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}
function sign(value) { return crypto.createHmac('sha256', setupSecret).update(value).digest('base64url'); }
function state(kind, payload) {
  const issued = String(now());
  const body = `${kind}.${issued}.${payload}`;
  return `${body}.${sign(body)}`;
}
function readState(value, expectedKind) {
  const parts = String(value || '').split('.');
  if (parts.length !== 4 || parts[0] !== expectedKind) return null;
  const body = parts.slice(0, 3).join('.');
  if (!timingSafeEqual(parts[3], sign(body))) return null;
  const issued = Number(parts[1]);
  if (!Number.isFinite(issued) || now() - issued > 60 * 60 * 1000) return null;
  return parts[2];
}
function oauthConfig() {
  if (!configValue) return null;
  try { return decode(configValue); } catch (_) { return null; }
}
function htmlEscape(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  })[character]);
}
function send(res, status, type, body, headers = {}) {
  res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store', ...headers });
  res.end(body);
}
function json(res, status, payload, headers = {}) { send(res, status, 'application/json; charset=utf-8', JSON.stringify(payload), headers); }
function page(res, status, title, content) {
  send(res, status, 'text/html; charset=utf-8', `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${htmlEscape(title)}</title><style>body{margin:0;background:#0b0d10;color:#f4f5f6;font:16px/1.5 Arial,sans-serif;padding:40px;max-width:760px}a,button{background:#d9c3a3;color:#111;border:0;border-radius:7px;padding:11px 14px;font-weight:700;text-decoration:none;cursor:pointer}.box{background:#14171b;border:1px solid #343a40;border-radius:12px;padding:24px}p{color:#c5c9cc}</style><main class="box">${content}</main>`);
}
function cors(req) {
  return req.headers.origin === editorOrigin ? {
    'Access-Control-Allow-Origin': editorOrigin,
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Vary': 'Origin'
  } : {};
}
function requireEditor(req, res) {
  if (req.headers.origin !== editorOrigin) { json(res, 403, { error: 'This endpoint accepts requests only from the editor.' }); return false; }
  return true;
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
  const response = await fetch(`https://api.github.com/app/installations/${config.installationId}/access_tokens`, {
    method: 'POST',
    headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${appJwt(config)}`, 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Kendarte-Archviz-Publisher' }
  });
  if (!response.ok) throw new Error(`GitHub installation access failed (${response.status}).`);
  return (await response.json()).token;
}
async function github(token, path, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${repo}/${path}`, {
    method: options.method || 'GET',
    headers: {
      Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Kendarte-Archviz-Publisher',
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
async function verifyEditorUser(token) {
  const response = await fetch('https://api.github.com/user', { headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'User-Agent': 'Kendarte-Archviz-Publisher' } });
  if (!response.ok) throw new Error('GitHub sign-in expired.');
  const user = await response.json();
  if (user.login !== ownerLogin && user.login !== 'janrulez') throw new Error('This editor is restricted to the publishing account.');
}
function extension(mime) { return mime === 'image/png' ? 'png' : mime === 'image/webp' ? 'webp' : 'jpg'; }
function slug(value) { return String(value || 'item').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'item'; }
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
      const chunks = []; let size = 0; let limited = false;
      stream.on('data', chunk => { size += chunk.length; chunks.push(chunk); });
      stream.on('limit', () => { limited = true; });
      stream.on('end', () => {
        if (limited) { failed = true; return; }
        if (name === 'file' && info.filename) files.set(info.filename, { buffer: Buffer.concat(chunks, size), mime: info.mimeType });
      });
    });
    parser.on('error', reject);
    parser.on('finish', () => failed ? reject(new Error('One image exceeds the 95 MB limit.')) : resolve({ fields, files }));
    req.pipe(parser);
  });
}
function draftEntries(portfolio) {
  const entries = [];
  if (portfolio.heroImage && portfolio.heroImage.type === 'draft') entries.push({ image: portfolio.heroImage, replace: value => { portfolio.heroImage = value; }, kind: 'hero' });
  portfolio.projects.forEach(project => (project.shots || []).forEach(shot => {
    if (shot.image && shot.image.type === 'draft') entries.push({ image: shot.image, replace: value => { shot.image = value; }, kind: 'shot', project, shot });
  }));
  return entries;
}
async function publishPortfolio(portfolio, files, githubToken) {
  ensurePortfolio(portfolio);
  const result = JSON.parse(JSON.stringify(portfolio));
  const uploads = draftEntries(result);
  for (let index = 0; index < uploads.length; index += 1) {
    const item = uploads[index];
    const file = files.get(item.image.key);
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.mime)) throw new Error('A selected image is missing or invalid.');
    const stamp = `${Date.now()}-${index}`;
    const filename = item.kind === 'hero' ? `hero-${stamp}.${extension(file.mime)}` : `${slug(item.project.id)}-${slug(item.shot.id)}-${stamp}.${extension(file.mime)}`;
    const path = `${base}/media/${filename}`;
    await github(githubToken, `contents/${path}`, { method: 'PUT', body: { message: `Publish archviz image: ${filename}`, content: file.buffer.toString('base64'), branch: 'main' } });
    item.replace({ type: 'file', src: `media/${filename}`, alt: item.kind === 'hero' ? 'Architectural visualization hero' : (item.shot.label || item.project.title || 'Architectural visualization') });
  }
  const current = await github(githubToken, `contents/${base}/portfolio.json?ref=main`);
  let existing = null;
  try { existing = JSON.parse(Buffer.from(current.content || '', 'base64').toString('utf8')); } catch (_) {}
  if (existing && JSON.stringify(existing) === JSON.stringify(result)) {
    return { portfolio: result, commit: null, unchanged: true };
  }
  const update = await github(githubToken, `contents/${base}/portfolio.json`, {
    method: 'PUT',
    body: { message: 'Publish architectural visualization portfolio', content: Buffer.from(JSON.stringify(result, null, 2)).toString('base64'), sha: current.sha, branch: 'main' }
  });
  return { portfolio: result, commit: update && update.commit ? update.commit.sha : null, unchanged: false };
}
async function handle(req, res) {
  const url = new URL(req.url, publicUrl);
  if (req.method === 'OPTIONS') return send(res, 204, 'text/plain', '', cors(req));
  if (url.pathname === '/health') return json(res, 200, { ok: true });
  if (url.pathname === '/webhooks') return send(res, 204, 'text/plain', '');

  if (url.pathname === '/setup') {
    if (!timingSafeEqual(url.searchParams.get('key') || '', setupSecret)) return page(res, 404, 'Not found', '<h1>Not found</h1>');
    const ticket = randomToken();
    const manifest = {
      name: 'Kendarte Archviz Publisher', url: publicUrl, description: 'Publishes the Kendarte architectural visualization portfolio.',
      hook_attributes: { url: `${publicUrl}/webhooks`, active: false }, redirect_url: `${publicUrl}/setup/callback`, callback_urls: [`${publicUrl}/auth/callback`],
      setup_url: `${publicUrl}/setup/installed?key=${encodeURIComponent(setupSecret)}&ticket=${encodeURIComponent(ticket)}`,
      public: false, default_events: [], default_permissions: { contents: 'write', metadata: 'read' }
    };
    return page(res, 200, 'Create publisher connection', `<h1>Connect publisher</h1><p>This creates one private GitHub App restricted to the portfolio repository.</p><form action="https://github.com/settings/apps/new?state=${encodeURIComponent(state('setup', ticket))}" method="post"><input type="hidden" name="manifest" value="${htmlEscape(JSON.stringify(manifest))}"><button type="submit">Create GitHub App</button></form>`);
  }

  if (url.pathname === '/setup/callback') {
    const ticket = readState(url.searchParams.get('state'), 'setup');
    const code = url.searchParams.get('code');
    if (!ticket || !code) return page(res, 400, 'Setup failed', '<h1>Setup failed</h1><p>The setup link expired. Start it again.</p>');
    const conversion = await fetch(`https://api.github.com/app-manifests/${encodeURIComponent(code)}/conversions`, { method: 'POST', headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'Kendarte-Archviz-Publisher' } });
    if (!conversion.ok) throw new Error('GitHub could not create the publisher app.');
    const app = await conversion.json();
    pendingApps.set(ticket, { expires: now() + 30 * 60 * 1000, config: { appId: app.id, clientId: app.client_id, clientSecret: app.client_secret, privateKey: app.pem, webhookSecret: app.webhook_secret, slug: app.slug } });
    return page(res, 200, 'Install publisher', `<h1>App created</h1><p>Install it only on <b>kendarte.github.io</b>.</p><a href="${htmlEscape(`${app.html_url}/installations/new`)}">Install publisher</a>`);
  }

  if (url.pathname === '/setup/installed') {
    if (!timingSafeEqual(url.searchParams.get('key') || '', setupSecret)) return page(res, 404, 'Not found', '<h1>Not found</h1>');
    const pending = pendingApps.get(url.searchParams.get('ticket'));
    const installationId = url.searchParams.get('installation_id');
    if (!pending || pending.expires < now() || !installationId) return page(res, 400, 'Installation failed', '<h1>Installation failed</h1><p>Restart the secure setup.</p>');
    pending.config.installationId = Number(installationId);
    const configuration = b64url(JSON.stringify(pending.config));
    pendingApps.delete(url.searchParams.get('ticket'));
    return page(res, 200, 'Publisher connected', `<h1>Publisher connected</h1><p>The connection is ready. Finalizing it now.</p><div id="publisher-config" data-config="${configuration}"></div>`);
  }

  if (url.pathname === '/auth/start') {
    const config = oauthConfig();
    if (!config) return page(res, 409, 'Publisher unavailable', '<h1>Publisher setup is not finished yet.</h1>');
    const authorize = new URL('https://github.com/login/oauth/authorize');
    authorize.searchParams.set('client_id', config.clientId);
    authorize.searchParams.set('redirect_uri', `${publicUrl}/auth/callback`);
    authorize.searchParams.set('scope', 'public_repo');
    authorize.searchParams.set('state', state('oauth', randomToken()));
    res.writeHead(302, { Location: authorize.toString(), 'Cache-Control': 'no-store' });
    return res.end();
  }

  if (url.pathname === '/auth/callback') {
    if (!readState(url.searchParams.get('state'), 'oauth') || !url.searchParams.get('code')) return page(res, 400, 'Sign in failed', '<h1>Sign in failed</h1><p>Start publishing again from the editor.</p>');
    const config = oauthConfig();
    const tokenResponse = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Kendarte-Archviz-Publisher' },
      body: JSON.stringify({ client_id: config.clientId, client_secret: config.clientSecret, code: url.searchParams.get('code'), redirect_uri: `${publicUrl}/auth/callback` })
    });
    const oauth = await tokenResponse.json();
    if (!oauth.access_token) return page(res, 401, 'Sign in failed', '<h1>Sign in failed</h1><p>GitHub did not approve access.</p>');
    await verifyEditorUser(oauth.access_token);
    return page(res, 200, 'Signed in', `<h1>Signed in</h1><p>Returning to the editor…</p><script>if(window.opener){window.opener.postMessage({type:'archviz-publish-session',session:${JSON.stringify(oauth.access_token)}},${JSON.stringify(editorOrigin)});window.close();}</script>`);
  }

  if (url.pathname === '/publish' && req.method === 'POST') {
    if (!requireEditor(req, res)) return;
    const match = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || '');
    if (!match) return json(res, 401, { error: 'Sign in required.' }, cors(req));
    try {
      await verifyEditorUser(match[1]);
      const incoming = await parsePublish(req);
      const published = await publishPortfolio(JSON.parse(incoming.fields.portfolio || ''), incoming.files, match[1]);
      return json(res, 200, { commit: published.commit, unchanged: published.unchanged, portfolio: published.portfolio }, cors(req));
    } catch (error) {
      const message = error.message || 'Publish failed.';
      return json(res, /sign-in|restricted/i.test(message) ? 401 : 400, { error: message }, cors(req));
    }
  }
  return page(res, 404, 'Not found', '<h1>Not found</h1>');
}

http.createServer((req, res) => handle(req, res).catch(error => {
  console.error(error);
  if (!res.headersSent) json(res, 500, { error: 'Publisher error.' }, cors(req));
  else res.end();
})).listen(port, '0.0.0.0', () => console.log(`Publisher listening on ${port}`));
