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
const probe=`window.__RESOLUTION_KIND_REGRESSION__={createMatch,setMatch:m=>state.match=m,resolveTopStack,completeStackV070,TEST_CARD_DB_V1};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM resolution-kind]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.__scheduled=[];dom.window.setTimeout=(fn,delay)=>{dom.window.__scheduled.push([fn?.name||'',delay]);return 0};
const H=dom.window.__RESOLUTION_KIND_REGRESSION__,S=dom.window.SizaCardSchema,E=dom.window.SizaCardEffects;
if(!H||!S||!E)throw new Error('Resolution kind hooks unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

H.TEST_CARD_DB_V1.push(
  {id:'reg_resolution_artifact',name:'Generated Artifact',type:'Artifact',cost:1,difficulty:1,pips:{},text:'Artifact.',effects:[]},
  {id:'reg_resolution_equipment',name:'Generated Equipment',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'Equipment.',effects:[{event:'equipped',type:'modify-power',amount:3}]},
  {id:'reg_resolution_creature',name:'Generated Creature',type:'Creature',cost:1,difficulty:1,pips:{},power:2,toughness:3,text:'Creature.',effects:[]},
  {id:'reg_resolution_spell',name:'Generated Spell',type:'Instant',cost:1,difficulty:1,pips:{},text:'Draw.',effects:[{event:'resolve',type:'draw',target:'self',amount:1}]}
);
const fresh=()=>{const M=H.createMatch(false,'prepare');H.setMatch(M);for(const P of[M.player,M.enemy]){P.hand=[];P.library=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.artifacts=[];P.equipment=[];P.exile=[]}M.player.life=20;M.enemy.life=20;M.pendingChoice=null;M.log=[];return M};
const resolve=(id,owner='player',setup=null)=>{const M=fresh();if(setup)setup(M);M.stack=[{id:'reg-'+id,cardId:id,owner}];H.resolveTopStack();return M};

test('resolutionKind clasifica Creature Artifact Equipment y spell',()=>S.resolutionKind({type:'Creature'})==='creature'&&S.resolutionKind({type:'Artifact'})==='artifact'&&S.resolutionKind({type:'Artifact',equipCost:1})==='equipment'&&S.resolutionKind({type:'Instant'})==='spell');
test('resolutionKind conserva comparación literal de type',()=>S.resolutionKind({type:'artifact',equipCost:1})==='spell'&&S.resolutionKind({type:'Land'})==='spell'&&S.resolutionKind({})==='spell');
test('Artifact con effect equipped clasifica como Equipment',()=>S.resolutionKind({type:'Artifact',effects:[{event:'equipped',type:'modify-power',amount:2}]})==='equipment');
test('Creature oficial entra en battlefield con arrays alineados',()=>{const M=resolve('servitor');return M.player.battlefield[0]==='servitor'&&M.player.powerCounters[0]===0&&M.player.summonedOn[0]===M.player.ownTurn&&!M.player.graveyard.length});
test('Artifact normal oficial entra en Reliquias',()=>{const M=resolve('prism');return M.player.artifacts[0]==='prism'&&!M.player.equipment.length&&!M.player.graveyard.length});
test('Equipment oficial entra en zona Equipment sin objetivo',()=>{const M=resolve('tideblade');return M.player.equipment.length===1&&M.player.equipment[0].id==='tideblade'&&M.player.equipment[0].target===null&&!M.player.artifacts.length});
test('Instant oficial resuelve y termina en Cementerio',()=>{const M=resolve('spark');return M.enemy.life===18&&M.player.graveyard.includes('spark')&&!M.player.artifacts.length&&!M.player.equipment.length});
test('Cartas generadas usan clasificación por datos, no por ID',()=>{const A=resolve('reg_resolution_artifact','enemy'),E1=resolve('reg_resolution_equipment','enemy'),C=resolve('reg_resolution_creature','enemy'),I=resolve('reg_resolution_spell','player',M=>{M.player.library=['mist']});return A.enemy.artifacts[0]==='reg_resolution_artifact'&&E1.enemy.equipment[0]?.id==='reg_resolution_equipment'&&C.enemy.battlefield[0]==='reg_resolution_creature'&&I.player.hand[0]==='mist'&&I.player.graveyard.includes('reg_resolution_spell')});
test('stackCompletionPlan prioriza partida terminada sobre elección pendiente',()=>JSON.stringify(E.stackCompletionPlan({over:true,pendingChoice:{type:'discard'},stackReturnOwner:'enemy'}))===JSON.stringify({kind:'over'}));
test('stackCompletionPlan conserva elección pendiente sin consumir retorno',()=>JSON.stringify(E.stackCompletionPlan({over:false,pendingChoice:{type:'discard'},stackReturnOwner:'enemy'}))===JSON.stringify({kind:'choice',active:'choice'}));
test('stackCompletionPlan distingue retorno rival y jugador con fallback histórico',()=>{const r=E.stackCompletionPlan({stackReturnOwner:'enemy'}),p=E.stackCompletionPlan({stackReturnOwner:'player'}),f=E.stackCompletionPlan({stackReturnOwner:'unexpected'});return r.kind==='return'&&r.stackReturnOwner===null&&r.active==='enemy'&&r.phase==='Main rival'&&r.scheduleEnemy===true&&p.active==='player'&&p.phase==='Main'&&!p.scheduleEnemy&&f.active==='player'&&f.phase==='Main'&&!f.scheduleEnemy});
function complete({over=false,pendingChoice=null,stackReturnOwner=null}={}){const M=fresh();M.stack=[];M.over=over;M.pendingChoice=pendingChoice;M.stackReturnOwner=stackReturnOwner;M.active='resolving';M.phase='Stack listo';dom.window.__scheduled.length=0;H.completeStackV070();return{M,scheduled:dom.window.__scheduled.slice()}}
test('completeStack conserva retorno cuando hay elección pendiente',()=>{const {M,scheduled}=complete({pendingChoice:{type:'discard'},stackReturnOwner:'enemy'});return M.active==='choice'&&M.stackReturnOwner==='enemy'&&M.pendingChoice?.type==='discard'&&!scheduled.length});
test('completeStack devuelve turno rival limpia owner y programa IA',()=>{const {M,scheduled}=complete({stackReturnOwner:'enemy'});return M.active==='enemy'&&M.phase==='Main rival'&&M.stackReturnOwner===null&&scheduled.length===1&&scheduled[0][1]===420});
test('completeStack devuelve turno jugador sin programar IA',()=>{const {M,scheduled}=complete({stackReturnOwner:'player'});return M.active==='player'&&M.phase==='Main'&&M.stackReturnOwner===null&&!scheduled.length});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA resolution kind regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
