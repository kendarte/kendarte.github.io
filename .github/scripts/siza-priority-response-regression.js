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
const probe=`window.__PRIORITY_RESPONSE_REGRESSION__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getModal:()=>state.modal,enemyRespondV070,enemyChoosePlay,openPriorityV070,passPriorityV070};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM priority-response]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.__scheduled=[];dom.window.setTimeout=(fn,delay)=>{dom.window.__scheduled.push([fn?.name||'',delay]);return 0};
const H=dom.window.__PRIORITY_RESPONSE_REGRESSION__,E=dom.window.SizaCardEffects;
if(!H||!E)throw new Error('Priority response hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

const cards={
  normalA:{id:'normalA',type:'Instant',difficulty:6,effects:[]},
  counterA:{id:'counterA',type:'Instant',difficulty:1,effects:[{event:'resolve',type:'counter-stack-target'}]},
  creature:{id:'creature',type:'Creature',difficulty:4,effects:[{event:'resolve',type:'counter-stack-target'}]},
  normalB:{id:'normalB',type:'Instant',difficulty:7,effects:[]},
  counterB:{id:'counterB',type:'Instant',difficulty:2,effects:[{event:'resolve',type:'counter-stack-target'}]},
  low:{id:'low',type:'Creature',difficulty:4,effects:[]},
  tie:{id:'tie',type:'Artifact',difficulty:4,effects:[]},
  land:{id:'land',type:'Land',difficulty:1,effects:[]}
};
const resolve=id=>cards[id];
test('preferredResponseCard prioriza counter pagable',()=>{const x=E.preferredResponseCard(['normalA','counterA','normalB'],resolve,()=>true);return x?.i===1&&x.c.id==='counterA'});
test('preferredResponseCard conserva primer Instant cuando no hay counter',()=>{const x=E.preferredResponseCard(['normalA','normalB'],resolve,()=>true);return x?.i===0&&x.c.id==='normalA'});
test('preferredResponseCard ignora no-Instant aunque tenga counter effect',()=>{const x=E.preferredResponseCard(['creature','normalB'],resolve,()=>true);return x?.i===1&&x.c.id==='normalB'});
test('preferredResponseCard ignora counter no pagable',()=>{const x=E.preferredResponseCard(['counterA','normalA'],resolve,c=>c.id==='normalA');return x?.i===1&&x.c.id==='normalA'});
test('preferredResponseCard conserva primer counter entre empates',()=>{const x=E.preferredResponseCard(['counterA','counterB','normalA'],resolve,()=>true);return x?.i===0&&x.c.id==='counterA'});
test('preferredResponseCard devuelve null sin candidato',()=>E.preferredResponseCard([],resolve,()=>true)===null);
test('preferredMainPhaseCard elige menor dificultad',()=>{const x=E.preferredMainPhaseCard(['normalB','low','normalA'],resolve,()=>true);return x?.i===1&&x.c.id==='low'});
test('preferredMainPhaseCard excluye Land y counter reactivo',()=>{const x=E.preferredMainPhaseCard(['land','counterA','normalA'],resolve,()=>true);return x?.i===2&&x.c.id==='normalA'});
test('preferredMainPhaseCard ignora candidatos no pagables',()=>{const x=E.preferredMainPhaseCard(['low','normalA'],resolve,c=>c.id==='normalA');return x?.i===1&&x.c.id==='normalA'});
test('preferredMainPhaseCard conserva primer candidato en empate',()=>{const x=E.preferredMainPhaseCard(['low','tie'],resolve,()=>true);return x?.i===0&&x.c.id==='low'});
test('preferredMainPhaseCard conserva undefined sin candidato',()=>E.preferredMainPhaseCard(['land','counterA'],resolve,()=>true)===undefined);
test('priorityWindowPlan alterna rival y jugador con estados exactos',()=>{const p=E.priorityWindowPlan('player'),e=E.priorityWindowPlan('enemy');return p.responder==='enemy'&&p.active==='enemy-response'&&p.phase==='Prioridad rival'&&e.responder==='player'&&e.active==='response'&&e.phase==='Tu prioridad'});
test('priorityWindowPlan conserva fallback histórico a jugador',()=>{const x=E.priorityWindowPlan('unexpected');return x.responder==='player'&&x.active==='response'&&x.phase==='Tu prioridad'});
test('priorityPassPlan produce transición exacta para ambos responders',()=>{const p=E.priorityPassPlan({responder:'player'},'player'),e=E.priorityPassPlan({responder:'enemy'},'enemy');return JSON.stringify(p)===JSON.stringify({responseWindow:null,pendingResolution:true,active:'resolving',phase:'Stack listo'})&&JSON.stringify(e)===JSON.stringify(p)});
test('priorityPassPlan rechaza owner incorrecto o ventana ausente',()=>E.priorityPassPlan({responder:'player'},'enemy')===null&&E.priorityPassPlan(null,'player')===null);
function priority(owner,cardId,id){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.responseWindow=null;M.active='player';M.phase='Main';M.log=[];H.openPriorityV070({id,cardId,owner});return M}
test('openPriority de carta del jugador entrega prioridad al rival',()=>{const M=priority('player','mist','p');return M.responseWindow?.stackId==='p'&&M.responseWindow?.responder==='enemy'&&M.active==='enemy-response'&&M.phase==='Prioridad rival'&&M.log.some(x=>x.t==='Prioridad'&&x.m==='El rival puede responder a Niebla de Sal.')});
test('openPriority de carta rival entrega prioridad al jugador',()=>{const M=priority('enemy','spark','e');return M.responseWindow?.stackId==='e'&&M.responseWindow?.responder==='player'&&M.active==='response'&&M.phase==='Tu prioridad'&&M.log.some(x=>x.t==='Prioridad'&&x.m==='Puedes responder a Chispa del Estuario.')});
function pass(responder,owner){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.responseWindow={stackId:'x',responder};M.pendingResolution=false;M.active=responder==='player'?'response':'enemy-response';M.phase=responder==='player'?'Tu prioridad':'Prioridad rival';H.passPriorityV070(owner);return M}
test('passPriority válido entrega el Stack a resolución',()=>{const M=pass('player','player');return M.responseWindow===null&&M.pendingResolution===true&&M.active==='resolving'&&M.phase==='Stack listo'});
test('passPriority con owner incorrecto conserva la ventana',()=>{const M=pass('player','enemy');return M.responseWindow?.responder==='player'&&M.pendingResolution===false&&M.active==='response'&&M.phase==='Tu prioridad'});

function setup({hand=['mist','counter','spark'],crystals={U:2,R:1,G:0,W:0,B:0},modal=null}={}){
  const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(modal);M.enemy.hand=[...hand];M.enemy.battlefield=[];M.enemy.powerCounters=[];M.enemy.summonedOn=[];M.enemy.crystals={...crystals};M.player.hand=[];M.stack=[{id:'target',cardId:'spark',owner:'player'}];M.responseWindow={stackId:'target',responder:'enemy'};M.pendingResolution=false;M.active='enemy-response';M.phase='Prioridad rival';M.log=[];return M;
}
test('IA abre Manafestation reactiva con counter preferido',()=>{const M=setup();H.enemyRespondV070();const m=H.getModal();return m?.owner==='enemy'&&m.cardId==='counter'&&m.idx===1&&m.reactive===true&&m.targetStackId==='target'&&M.responseWindow?.responder==='enemy'});
test('IA pasa prioridad cuando no tiene Instant pagable',()=>{const M=setup({crystals:{U:0,R:0,G:0,W:0,B:0}});H.enemyRespondV070();return H.getModal()===null&&M.responseWindow===null&&M.pendingResolution===true&&M.active==='resolving'&&M.phase==='Stack listo'&&M.log.some(x=>x.t==='Prioridad rival'&&x.m==='El rival pasa.')});
test('IA no responde de nuevo con modal ya abierto',()=>{const sentinel={type:'sentinel'},M=setup({hand:['counter'],modal:sentinel});H.enemyRespondV070();return H.getModal()===sentinel&&M.responseWindow?.responder==='enemy'&&!M.pendingResolution});
function setupMain({hand=['watcher','servitor'],crystals={U:2,R:1,G:0,W:0,B:0},equipment=[],battlefield=[]}={}){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.active='enemy';M.phase='Main rival';M.responseWindow=null;M.enemyStage='main';const P=M.enemy;P.hand=[...hand];P.library=[];P.graveyard=[];P.battlefield=[...battlefield];P.powerCounters=P.battlefield.map(()=>0);P.summonedOn=P.battlefield.map(()=>0);P.equipment=equipment.map(x=>({...x}));P.artifacts=[];P.crystals={...crystals};P.exhausted=[];P.offeringUsed=false;M.log=[];dom.window.__scheduled.length=0;return M}
test('IA principal elige la carta pagable de menor dificultad',()=>{const M=setupMain();H.enemyChoosePlay();const m=H.getModal();return m?.owner==='enemy'&&m.cardId==='servitor'&&m.idx===1&&m.reactive===false&&M.enemy.crystals.U===1});
test('IA principal conserva counter para respuesta y juega otra carta',()=>{setupMain({hand:['counter','spark']});H.enemyChoosePlay();const m=H.getModal();return m?.cardId==='spark'&&m.idx===1});
test('IA principal ignora candidato barato no pagable',()=>{setupMain({hand:['leviathan','watcher']});H.enemyChoosePlay();const m=H.getModal();return m?.cardId==='watcher'&&m.idx===1});
test('IA principal mantiene prioridad de Equipment suelto',()=>{const M=setupMain({hand:['spark'],equipment:[{id:'tideblade',target:null}],battlefield:['servitor']});H.enemyChoosePlay();return H.getModal()===null&&M.enemy.equipment[0].target===0&&M.enemy.crystals.U===1&&dom.window.__scheduled.some(x=>x[1]===260)});
test('IA principal sin carta válida continúa después de Main',()=>{const M=setupMain({hand:['dock','counter']});H.enemyChoosePlay();return H.getModal()===null&&M.active==='enemy'&&dom.window.__scheduled.some(x=>x[1]===400)});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA priority response regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
