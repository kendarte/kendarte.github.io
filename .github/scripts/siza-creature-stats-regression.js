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
const H=dom.window.__CREATURE_STATS_REGRESSION__,R=dom.window.SizaCreatureRules;if(!H||!R)throw new Error('Creature rule hooks unavailable');
H.TEST_CARD_DB_V1.push(
  {id:'reg_stats_body',name:'Stats Body',type:'Creature',cost:1,difficulty:1,pips:{U:1},power:2,toughness:3,text:'Body.',art:'multi',glyph:'B',effects:[]},
  {id:'reg_stats_blade',name:'Stats Blade',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'+3.',art:'multi',glyph:'E',effects:[{event:'equipped',type:'modify-power',amount:3}]},
  {id:'reg_stats_charm',name:'Stats Charm',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'+1.',art:'multi',glyph:'C',effects:[{event:'equipped',type:'modify-power',amount:1}]}
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

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA creature rules regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
