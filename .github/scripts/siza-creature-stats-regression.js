const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

let html=fs.readFileSync('siza-mobile-test/index.html','utf8');
for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`;
  if(!html.includes(tag))throw new Error(`Missing shared core tag ${name}`);
  html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
}
const entryTag='<script src="../siza-core/entry-rules.js"></script>';
if(html.includes(entryTag))html=html.replace(entryTag,`<script>${fs.readFileSync('siza-core/entry-rules.js','utf8')}</script>`);
else if(!html.includes('SizaEntryRules'))throw new Error('Entry rules unavailable');
const creature=fs.readFileSync('siza-core/creature-rules.js','utf8'),creatureTag='<script src="../siza-core/creature-rules.js"></script>';
if(html.includes(creatureTag))html=html.replace(creatureTag,`<script>${creature}</script>`);
else if(!html.includes('SizaCreatureRules'))html=html.replace('<script>\nconst NEREIDA_IMG=',`<script>${creature}</script>\n<script>\nconst NEREIDA_IMG=`);
const marker='window.SIZA={';if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__CREATURE_STATS_REGRESSION__={cardById,TEST_CARD_DB_V1,counterV070,equipmentFor,equipmentPowerBonusV1,effectivePower,toughV070};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM creature-stats]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;
const H=dom.window.__CREATURE_STATS_REGRESSION__,R=dom.window.SizaCreatureRules,E=dom.window.SizaCardEffects;if(!H||!R||!E)throw new Error('Creature rule hooks unavailable');
H.TEST_CARD_DB_V1.push(
  {id:'reg_stats_body',name:'Stats Body',type:'Creature',cost:1,difficulty:1,pips:{U:1},power:2,toughness:3,text:'Body.',art:'multi',glyph:'B',effects:[]},
  {id:'reg_stats_blade',name:'Stats Blade',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'+3.',art:'multi',glyph:'E',effects:[{event:'equipped',type:'modify-power',amount:3}]},
  {id:'reg_stats_charm',name:'Stats Charm',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'+1.',art:'multi',glyph:'C',effects:[{event:'equipped',type:'modify-power',amount:1}]},
  {id:'reg_combat_2_2',name:'Combat 2/2',type:'Creature',power:2,toughness:2,effects:[]},
  {id:'reg_combat_1_1',name:'Combat 1/1',type:'Creature',power:1,toughness:1,effects:[]},
  {id:'reg_combat_grow_1_3',name:'Combat Grow 1/3',type:'Creature',power:1,toughness:3,effects:[{event:'combat-damage',type:'add-power-counter',amount:2}]},
  {id:'reg_combat_grow_1_1',name:'Combat Grow 1/1',type:'Creature',power:1,toughness:1,effects:[{event:'combat-damage',type:'add-power-counter',amount:2}]},
  {id:'reg_combat_def_grow',name:'Combat Defender Grow',type:'Creature',power:1,toughness:3,effects:[{event:'combat-damage',type:'add-power-counter',amount:1}]},
  {id:'reg_ai_3_3',name:'AI 3/3',type:'Creature',power:3,toughness:3,effects:[]},
  {id:'reg_ai_1_4',name:'AI 1/4',type:'Creature',power:1,toughness:4,effects:[]},
  {id:'reg_ad_two',name:'AD Two',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:2}]},
  {id:'reg_ad_three',name:'AD Three',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:3}]},
  {id:'reg_ad_default',name:'AD Default',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',amount:1}]},
  {id:'reg_ad_self',name:'AD Self',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'self',amount:4}]}
);
const P={battlefield:['reg_stats_body'],powerCounters:[2],equipment:[{id:'reg_stats_blade',target:0},{id:'reg_stats_charm',target:0},{id:'reg_stats_blade',target:null}]};
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
test('Contador devuelve el valor persistente',()=>H.counterV070(P,0)===2&&H.counterV070(P,9)===0);
test('equipmentFor devuelve sólo Equipment ligado al índice',()=>H.equipmentFor(P,0).length===2&&H.equipmentFor(P,1).length===0);
test('Bonus de Equipment suma effects modify-power',()=>H.equipmentPowerBonusV1(P,0)===4);
test('Poder efectivo suma base contador y Equipment',()=>H.effectivePower(P,0)===8);
test('Resistencia suma base y contador pero no Equipment de poder',()=>H.toughV070(P,0)===5);
test('Equipment desconocido funciona sólo por descriptors',()=>{P.equipment=[{id:'reg_stats_charm',target:0}];return H.equipmentPowerBonusV1(P,0)===1&&H.effectivePower(P,0)===5});

function statePlayer(){return{battlefield:['a','b','c'],powerCounters:[2,1,0],summonedOn:[1,2,3],ownTurn:4,exhausted:[0,2],equipment:[{id:'blade',target:1},{id:'charm',target:2}],hand:[],graveyard:[]}}
test('addCreature agrega carta contador cero y turno de entrada',()=>{const X={battlefield:['a'],powerCounters:[3],summonedOn:[2],ownTurn:5,equipment:[],exhausted:[],hand:[],graveyard:[]},i=R.addCreature(X,'new');return i===1&&JSON.stringify(X.battlefield)==='["a","new"]'&&JSON.stringify(X.powerCounters)==='[3,0]'&&JSON.stringify(X.summonedOn)==='[2,5]'});
test('removeAt manda al Cementerio y alinea arrays paralelos',()=>{const X=statePlayer(),id=R.removeAt(X,1);return id==='b'&&JSON.stringify(X.battlefield)==='["a","c"]'&&JSON.stringify(X.graveyard)==='["b"]'&&JSON.stringify(X.powerCounters)==='[2,0]'&&JSON.stringify(X.summonedOn)==='[1,3]'});
test('removeAt puede devolver a la mano',()=>{const X=statePlayer(),id=R.removeAt(X,0,'hand');return id==='a'&&JSON.stringify(X.hand)==='["a"]'&&X.graveyard.length===0});
test('removeAt elimina y rebasa índices agotados',()=>{const X=statePlayer();R.removeAt(X,1);return JSON.stringify(X.exhausted)==='[0,1]'});
test('Equipment sobre criatura removida queda sin objetivo',()=>{const X=statePlayer();R.removeAt(X,1);return X.equipment[0].target===null});
test('Equipment posterior a criatura removida rebasa su objetivo',()=>{const X=statePlayer();R.removeAt(X,1);return X.equipment[1].target===1});
test('Índice inválido no muta estado',()=>{const X=statePlayer(),before=JSON.stringify(X),id=R.removeAt(X,9);return id===null&&JSON.stringify(X)===before});

function combatPlayer(ids,equipment=[]){return{battlefield:[...ids],powerCounters:ids.map(()=>0),summonedOn:ids.map(()=>0),equipment:equipment.map(x=>({...x}))}}
function attackPlan(ids,indices=ids.map((_,index)=>index)){const A=combatPlayer(ids);return R.attackDeclaredDamage(A,indices,H.cardById,E.forEvent)}
test('attackDeclaredDamage suma una fuente data-driven',()=>{const x=attackPlan(['reg_ad_two']);return x.amount===2&&x.source==='AD Two'});
test('attackDeclaredDamage conserva source cuando todas las fuentes coinciden',()=>{const x=attackPlan(['reg_ad_two','reg_ad_two']);return x.amount===4&&x.source==='AD Two'});
test('attackDeclaredDamage usa etiqueta genérica para fuentes mixtas',()=>{const x=attackPlan(['reg_ad_two','reg_ad_three']);return x.amount===5&&x.source==='Efectos de ataque'});
test('attackDeclaredDamage usa opponent por defecto e ignora target self',()=>{const x=attackPlan(['reg_ad_default','reg_ad_self']);return x.amount===1&&x.source==='AD Default'});

function blockerPlan(blockers,slot,index,legal){return R.blockerAssignmentPlan(blockers,slot,index,legal)}
test('blockerAssignmentPlan crea asignación legal con slot string',()=>{const x=blockerPlan({},2,1,[0,1,2]);return JSON.stringify(x)==='{"removeSlots":[],"slot":"2","blockerIndex":1}'});
test('blockerAssignmentPlan mueve un bloqueador ya asignado',()=>{const x=blockerPlan({'0':1,'2':0},3,1,[0,1]);return JSON.stringify(x)==='{"removeSlots":["0"],"slot":"3","blockerIndex":1}'});
test('blockerAssignmentPlan elimina todas las asignaciones duplicadas del mismo bloqueador',()=>{const x=blockerPlan({'0':1,'1':1,'2':0},4,1,[0,1]);return JSON.stringify(x.removeSlots)==='["0","1"]'&&x.slot==='4'&&x.blockerIndex===1});
test('blockerAssignmentPlan rechaza índice ilegal',()=>blockerPlan({'0':0},1,2,[0,1])===null);
test('blockerAssignmentPlan es puro y no muta blockers',()=>{const b={'0':1,'2':0},before=JSON.stringify(b);blockerPlan(b,3,1,[0,1]);return JSON.stringify(b)===before});

function plan(attackers,defenders,blockers={},equipment=[]){const A=combatPlayer(attackers,equipment),D=combatPlayer(defenders),combat={attackers:attackers.map((id,index)=>({index,id})),blockers};return R.combatPlan(combat,A,D,H.cardById,E.forEvent)}
test('combatPlan calcula daño sin bloqueo y counter gain',()=>{const x=plan(['reg_combat_grow_1_3'],[]);return x.damage===1&&JSON.stringify(x.attackerCounterGains)==='[[0,2]]'&&!x.attackerDeaths.length&&!x.defenderDeaths.length});
test('combatPlan marca muerte simultánea 2/2 contra 2/2',()=>{const x=plan(['reg_combat_2_2'],['reg_combat_2_2'],{'0':0});return JSON.stringify(x.attackerDeaths)==='[0]'&&JSON.stringify(x.defenderDeaths)==='[0]'&&x.damage===0});
test('combatPlan conserva counter gain sólo si atacante sobrevive',()=>{const survives=plan(['reg_combat_grow_1_3'],['reg_combat_1_1'],{'0':0}),dies=plan(['reg_combat_grow_1_1'],['reg_combat_2_2'],{'0':0});return JSON.stringify(survives.attackerCounterGains)==='[[0,2]]'&&JSON.stringify(dies.attackerCounterGains)==='[]'});
test('combatPlan incorpora Equipment al daño efectivo',()=>{const x=plan(['reg_combat_2_2'],[],{},[{id:'reg_stats_blade',target:0}]);return x.damage===5});
test('combatPlan concede counter gain a bloqueador superviviente',()=>{const x=plan(['reg_combat_1_1'],['reg_combat_def_grow'],{'0':0});return JSON.stringify(x.attackerDeaths)==='[0]'&&JSON.stringify(x.defenderCounterGains)==='[[0,1]]'});
test('combatPlan produce snapshot de intercambio para logs',()=>{const x=plan(['reg_combat_2_2'],['reg_combat_1_1'],{'0':0}),e=x.exchanges[0];return e.attackerName==='Combat 2/2'&&e.defenderName==='Combat 1/1'&&e.attackerPower===2&&e.attackerToughness===2&&e.defenderPower===1&&e.defenderToughness===1});

function aiPlan(attackers,defenders,{exhausted=[],equipment=[]}={}){const A=combatPlayer(attackers,equipment),D=combatPlayer(defenders);D.exhausted=[...exhausted];const combat={attackers:attackers.map((id,index)=>({index,id})),blockers:{}};return R.aiBlockers(combat,A,D,H.cardById,E.forEvent)}
test('aiBlockers empareja mayor poder con mayor resistencia',()=>{const x=aiPlan(['reg_combat_1_1','reg_ai_3_3','reg_combat_2_2'],['reg_combat_1_1','reg_ai_1_4','reg_combat_grow_1_3']);return x['1']===1&&x['2']===2&&x['0']===0});
test('aiBlockers excluye bloqueadores agotados',()=>{const x=aiPlan(['reg_combat_1_1','reg_ai_3_3','reg_combat_2_2'],['reg_combat_1_1','reg_ai_1_4','reg_combat_grow_1_3'],{exhausted:[1]});return x['1']===2&&x['2']===0&&x['0']==null});
test('aiBlockers usa poder efectivo con Equipment para ordenar atacantes',()=>{const plain=aiPlan(['reg_combat_1_1','reg_combat_2_2'],['reg_ai_1_4','reg_combat_grow_1_3']),equipped=aiPlan(['reg_combat_1_1','reg_combat_2_2'],['reg_ai_1_4','reg_combat_grow_1_3'],{equipment:[{id:'reg_stats_blade',target:0}]});return plain['1']===0&&plain['0']===1&&equipped['0']===0&&equipped['1']===1});
test('aiBlockers deja atacantes sin bloquear cuando faltan defensores',()=>{const x=aiPlan(['reg_ai_3_3','reg_combat_2_2','reg_combat_1_1'],['reg_ai_1_4']);return x['0']===0&&x['1']==null&&x['2']==null});
test('aiBlockers ignora permanentes no Creature en battlefield defensivo',()=>{const x=aiPlan(['reg_ai_3_3'],['reg_stats_blade','reg_ai_1_4']);return x['0']===1});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA creature rules regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
