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
const marker='window.SIZA={';if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__PRIORITY_RESPONSE_REGRESSION__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getModal:()=>state.modal,enemyRespondV070,openPriorityV070};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM priority-response]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;
const H=dom.window.__PRIORITY_RESPONSE_REGRESSION__,E=dom.window.SizaCardEffects;
if(!H||!E)throw new Error('Priority response hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

const cards={
  normalA:{id:'normalA',type:'Instant',effects:[]},
  counterA:{id:'counterA',type:'Instant',effects:[{event:'resolve',type:'counter-stack-target'}]},
  creature:{id:'creature',type:'Creature',effects:[{event:'resolve',type:'counter-stack-target'}]},
  normalB:{id:'normalB',type:'Instant',effects:[]},
  counterB:{id:'counterB',type:'Instant',effects:[{event:'resolve',type:'counter-stack-target'}]}
};
const resolve=id=>cards[id];
test('preferredResponseCard prioriza counter pagable',()=>{const x=E.preferredResponseCard(['normalA','counterA','normalB'],resolve,()=>true);return x?.i===1&&x.c.id==='counterA'});
test('preferredResponseCard conserva primer Instant cuando no hay counter',()=>{const x=E.preferredResponseCard(['normalA','normalB'],resolve,()=>true);return x?.i===0&&x.c.id==='normalA'});
test('preferredResponseCard ignora no-Instant aunque tenga counter effect',()=>{const x=E.preferredResponseCard(['creature','normalB'],resolve,()=>true);return x?.i===1&&x.c.id==='normalB'});
test('preferredResponseCard ignora counter no pagable',()=>{const x=E.preferredResponseCard(['counterA','normalA'],resolve,c=>c.id==='normalA');return x?.i===1&&x.c.id==='normalA'});
test('preferredResponseCard conserva primer counter entre empates',()=>{const x=E.preferredResponseCard(['counterA','counterB','normalA'],resolve,()=>true);return x?.i===0&&x.c.id==='counterA'});
test('preferredResponseCard devuelve null sin candidato',()=>E.preferredResponseCard([],resolve,()=>true)===null);
test('priorityWindowPlan alterna rival y jugador con estados exactos',()=>{const p=E.priorityWindowPlan('player'),e=E.priorityWindowPlan('enemy');return p.responder==='enemy'&&p.active==='enemy-response'&&p.phase==='Prioridad rival'&&e.responder==='player'&&e.active==='response'&&e.phase==='Tu prioridad'});
test('priorityWindowPlan conserva fallback histórico a jugador',()=>{const x=E.priorityWindowPlan('unexpected');return x.responder==='player'&&x.active==='response'&&x.phase==='Tu prioridad'});
function priority(owner,cardId,id){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.responseWindow=null;M.active='player';M.phase='Main';M.log=[];H.openPriorityV070({id,cardId,owner});return M}
test('openPriority de carta del jugador entrega prioridad al rival',()=>{const M=priority('player','mist','p');return M.responseWindow?.stackId==='p'&&M.responseWindow?.responder==='enemy'&&M.active==='enemy-response'&&M.phase==='Prioridad rival'&&M.log.some(x=>x.t==='Prioridad'&&x.m==='El rival puede responder a Niebla de Sal.')});
test('openPriority de carta rival entrega prioridad al jugador',()=>{const M=priority('enemy','spark','e');return M.responseWindow?.stackId==='e'&&M.responseWindow?.responder==='player'&&M.active==='response'&&M.phase==='Tu prioridad'&&M.log.some(x=>x.t==='Prioridad'&&x.m==='Puedes responder a Chispa del Estuario.')});

function setup({hand=['mist','counter','spark'],crystals={U:2,R:1,G:0,W:0,B:0},modal=null}={}){
  const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(modal);M.enemy.hand=[...hand];M.enemy.battlefield=[];M.enemy.powerCounters=[];M.enemy.summonedOn=[];M.enemy.crystals={...crystals};M.player.hand=[];M.stack=[{id:'target',cardId:'spark',owner:'player'}];M.responseWindow={stackId:'target',responder:'enemy'};M.pendingResolution=false;M.active='enemy-response';M.phase='Prioridad rival';M.log=[];return M;
}
test('IA abre Manafestation reactiva con counter preferido',()=>{const M=setup();H.enemyRespondV070();const m=H.getModal();return m?.owner==='enemy'&&m.cardId==='counter'&&m.idx===1&&m.reactive===true&&m.targetStackId==='target'&&M.responseWindow?.responder==='enemy'});
test('IA pasa prioridad cuando no tiene Instant pagable',()=>{const M=setup({crystals:{U:0,R:0,G:0,W:0,B:0}});H.enemyRespondV070();return H.getModal()===null&&M.responseWindow===null&&M.pendingResolution===true&&M.active==='resolving'&&M.phase==='Stack listo'&&M.log.some(x=>x.t==='Prioridad rival'&&x.m==='El rival pasa.')});
test('IA no responde de nuevo con modal ya abierto',()=>{const sentinel={type:'sentinel'},M=setup({hand:['counter'],modal:sentinel});H.enemyRespondV070();return H.getModal()===sentinel&&M.responseWindow?.responder==='enemy'&&!M.pendingResolution});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA priority response regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
