// Run with NODE_PATH pointing to an installation of jsdom.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const js = path.join(__dirname, '../web/static/webclient/js');

async function checkGuard(source, expectLoop) {
  const dom = new JSDOM('<main id="pokerol-client"><span id="pkb-command-hint">OLD</span></main>', {runScripts:'outside-only'});
  const w = dom.window;
  let mutations = 0;
  const NativeObserver = w.MutationObserver;
  w.MutationObserver = class extends NativeObserver {
    constructor(callback) {
      super((records, observer) => {
        if (++mutations > 30) { observer.disconnect(); return; }
        callback(records, observer);
      });
    }
  };
  w.eval(source);
  await new Promise(r => setTimeout(r, 10));
  const hint = w.document.getElementById('pkb-command-hint');
  hint.textContent = 'REACCIONES';
  await new Promise(r => setTimeout(r, 10));
  assert.equal(hint.textContent, 'ATAQUES + ACCIONES');
  assert.equal(mutations > 30, expectLoop, 'observer must settle after updating its own label');
  if (!expectLoop) {
    const before = mutations;
    w.PokerolBattleUiGuardV01.refresh();
    await new Promise(r => setTimeout(r, 10));
    assert.equal(mutations, before, 'refresh must not write identical text');
  }
  w.close();
}

async function checkTransport(evenniaSource, transportSource, expectOpen) {
  const dom = new JSDOM('<span id="pk-speaker"></span><span id="pk-dialogue-text"></span><input id="inputfield"><button id="inputsend"></button>', {runScripts:'outside-only',url:'https://pokerol.test/webclient/'});
  const w = dom.window, sockets = [], packets = [];
  w.console.log = () => {};
  w.$ = () => ({ready: fn => w.document.addEventListener('DOMContentLoaded', fn)});
  w.wsactive = true; w.wsurl = 'wss://pokerol.test/ws'; w.csessid = 'test-session'; w.cuid = 'test-client';
  w.WebSocket = class {
    static OPEN = 1;
    constructor(url, protocols) { this.url=url; this.protocols=protocols; this.readyState=1; sockets.push(this); }
    send(packet) { packets.push(JSON.parse(packet)); }
    close() {}
  };
  w.eval(evenniaSource);
  w.eval(transportSource);
  let opens = 0, secondListener = 0;
  w.document.addEventListener('DOMContentLoaded', () => {
    w.Evennia.emitter.on('connection_open', () => opens++);
    w.Evennia.emitter.on('connection_open', () => secondListener++);
  });
  await new Promise(r => setTimeout(r, 20));
  assert.equal(sockets.length, expectOpen ? 1 : 0, 'bootstrap must open WebSocket without user input');
  if (expectOpen) {
    assert.equal(sockets[0].url, 'wss://pokerol.test/ws?test-session&test-client&other');
    sockets[0].onopen();
    assert.equal(opens, 1); assert.equal(secondListener, 1);
    assert.equal(w.Evennia.isConnected(), true);
    w.Evennia.init(); w.Evennia.connect();
    assert.equal(sockets.length, 1, 'other modules must not open duplicate connections');
    w.document.getElementById('inputfield').value = 'look';
    w.document.getElementById('inputsend').click();
    assert.equal(packets[0][0], 'text'); assert.equal(packets[0][1][0], 'look');
  }
  w.close();
}

(async () => {
  const evennia = fs.readFileSync(process.argv[2], 'utf8');
  const guard = fs.readFileSync(path.join(js,'pokerol_battle_ui_guard_v01.js'),'utf8');
  const transport = fs.readFileSync(path.join(js,'pokerol_transport_bootstrap_v01.js'),'utf8');
  await checkGuard(guard, false);
  await checkTransport(evennia, transport, true);
  if (process.argv[3]) {
    await checkGuard(fs.readFileSync(path.join(process.argv[3],'pokerol_battle_ui_guard_v01.js'),'utf8'), true);
    await checkTransport(evennia, fs.readFileSync(path.join(process.argv[3],'pokerol_transport_bootstrap_v01.js'),'utf8'), false);
    console.log('Confirmed: published client reproduces both regressions.');
  }
  console.log('PASS: observer settles, automatic connection, multicast events, no duplicate socket, look command.');
})().catch(error => {console.error(error); process.exitCode=1;});
