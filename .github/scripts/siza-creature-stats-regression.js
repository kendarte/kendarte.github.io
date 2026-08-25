const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

let html=fs.readFileSync('siza-mobile-test/index.html','utf8');
for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`;
  if(!html.includes(tag))throw new Error(`Missing shared core tag ${name}`);
  html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
}
const creature=fs.readFileSync('siza-core/creature-rules.js','utf8'),creatureTag='<script src="../siza-core/creature-rules.js"></script>';
if(html.includes(creatureTag))html=html.replace(creatureTag,`<script>${creature}</script>`);
else html=html.replace('<script>\nconst NEREIDA_IMG=',`<script>${creature}</script>\n<script>\nconst NEREIDA_IMG=`);
const marker='window.SIZA={';if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__CREATURE_STATS_REGRESSION__={cardById,TEST_CARD_DB_V1,counterV070,equipmentFor,equipmentPowerBonusV1,effectivePower,toughV070};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM creature-stats]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});dom.window.setTimeout=()=>0;
const H=dom.window.__CREATURE_STATS_REGRESSION__;if(!H||!dom.window.SizaCreatureRules)throw new Error('Creature stat hooks unavailable');
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
for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA creature stats regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
