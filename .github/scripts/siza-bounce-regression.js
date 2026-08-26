const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

let html=fs.readFileSync('siza-mobile-test/index.html','utf8');
for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`;
  if(!html.includes(tag))throw new Error(`Missing shared core tag ${name}`);
  html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
}
for(const name of ['entry-rules.js','creature-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`,globalName=name==='entry-rules.js'?'SizaEntryRules':'SizaCreatureRules';
  if(html.includes(tag))html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
  else if(!html.includes(globalName))throw new Error(`${globalName} unavailable`);
}
const marker='window.SIZA={';
if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__BOUNCE_REGRESSION__={createMatch,setMatch:m=>state.match=m,bounceV070,resolveTopStack};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM bounce]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
dom.window.setTimeout=()=>0;
const H=dom.window.__BOUNCE_REGRESSION__,E=dom.window.SizaCardEffects;
if(!H||!E)throw new Error('Bounce hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
const fresh=()=>{const M=H.createMatch(false,'prepare');H.setMatch(M);M.player.hand=[];M.enemy.hand=[];M.player.graveyard=[];M.enemy.graveyard=[];M.player.artifacts=[];M.enemy.artifacts=[];M.player.equipment=[];M.enemy.equipment=[];M.player.battlefield=[];M.enemy.battlefield=[];M.player.powerCounters=[];M.enemy.powerCounters=[];M.player.summonedOn=[];M.enemy.summonedOn=[];M.log=[];M.ui={hand:-1,creature:-1,attackMode:false,attackers:[],fieldFocus:null};return M};

test('bouncePlan usa battlefield y hand por defecto',()=>{const p=E.bouncePlan({owner:'player',index:2});return p.owner==='player'&&p.zone==='battlefield'&&p.index===2&&p.destination==='hand'&&p.zoneLabel==='Invocaciones'});
test('bouncePlan conserva etiquetas de Reliquias y Equipo',()=>{const a=E.bouncePlan({owner:'enemy',zone:'artifacts',index:0}),q=E.bouncePlan({owner:'enemy',zone:'equipment',index:1});return a.zoneLabel==='Reliquias'&&q.zoneLabel==='Equipo'&&a.destination==='hand'&&q.destination==='hand'});
test('preferredPermanentTarget prioriza owner y cae al primero',()=>{const xs=[{owner:'enemy',id:'a'},{owner:'player',id:'b'},{owner:'player',id:'c'}],ys=[{owner:'enemy',id:'x'}];return E.preferredPermanentTarget(xs,'player')===xs[1]&&E.preferredPermanentTarget(ys,'player')===ys[0]&&E.preferredPermanentTarget([],'player')===null});
test('Bounce de Reliquia mueve una sola carta a la mano',()=>{const M=fresh();M.enemy.artifacts=['prism','prism'];H.bounceV070({owner:'enemy',zone:'artifacts',index:0,id:'prism'});return M.enemy.artifacts.length===1&&M.enemy.hand.length===1&&M.enemy.hand[0]==='prism'});
test('Bounce de Equipment mueve el id sin duplicarlo',()=>{const M=fresh();M.enemy.equipment=[{id:'tideblade',target:0},{id:'tideblade',target:null}];H.bounceV070({owner:'enemy',zone:'equipment',index:1,id:'tideblade'});return M.enemy.equipment.length===1&&M.enemy.hand.length===1&&M.enemy.hand[0]==='tideblade'});
test('Bounce de criatura conserva rebasing de estado y UI',()=>{const M=fresh();M.player.battlefield=['servitor','ignimite','watcher'];M.player.powerCounters=[0,2,1];M.player.summonedOn=[0,0,0];M.player.exhausted=[1,2];M.player.equipment=[{id:'tideblade',target:2}];M.ui.attackers=[0,1,2];M.ui.creature=2;M.ui.fieldFocus={owner:'player',index:2};H.bounceV070({owner:'player',zone:'battlefield',index:1,id:'ignimite'});return JSON.stringify(M.player.battlefield)==='["servitor","watcher"]'&&JSON.stringify(M.player.powerCounters)==='[0,1]'&&JSON.stringify(M.player.exhausted)==='[1]'&&M.player.equipment[0].target===1&&JSON.stringify(M.ui.attackers)==='[0,1]'&&M.ui.creature===1&&M.ui.fieldFocus?.index===1&&M.player.hand[0]==='ignimite'});
test('Leviatán rival prefiere permanente del jugador',()=>{const M=fresh();M.player.artifacts=['prism'];M.stack=[{id:'lev-ai',cardId:'leviathan',owner:'enemy'}];H.resolveTopStack();return M.player.artifacts.length===0&&M.player.hand[0]==='prism'&&M.enemy.battlefield.includes('leviathan')});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);
const passed=results.filter(r=>r.pass).length;
console.log(`SIZA bounce regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
