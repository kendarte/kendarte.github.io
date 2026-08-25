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
const marker='window.SIZA={';
if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__ENTRY_RULES_REGRESSION__={createMatch,setMatch:m=>state.match=m,preparingV070,canAttackV070,availableAttackersV610,legalBlockersV070,spellCostV070,ENTRY_V070,TEST_CARD_DB_V1};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM entry-rules]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
dom.window.setTimeout=()=>0;
const H=dom.window.__ENTRY_RULES_REGRESSION__;
if(!H||!dom.window.SizaEntryRules)throw new Error('Entry rules hooks unavailable');

H.TEST_CARD_DB_V1.push(
  {id:'reg_entry_one',name:'Regression One Crystal',type:'Creature',cost:9,difficulty:1,pips:{U:1},power:1,toughness:1,text:'One.',art:'multi',glyph:'1',effects:[]},
  {id:'reg_entry_two',name:'Regression Two Crystal',type:'Creature',cost:1,difficulty:1,pips:{U:2},power:2,toughness:2,text:'Two.',art:'multi',glyph:'2',effects:[]},
  {id:'reg_entry_artifact',name:'Regression Artifact',type:'Artifact',cost:1,difficulty:1,pips:{},text:'Artifact.',art:'multi',glyph:'A',effects:[]}
);

const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
function fresh(mode='prepare'){
  const M=H.createMatch(false,mode);H.setMatch(M);
  M.player.battlefield=[];M.player.powerCounters=[];M.player.summonedOn=[];M.player.exhausted=[];M.player.ownTurn=3;
  return M;
}
function add(P,id,born){P.battlefield.push(id);P.powerCounters.push(0);P.summonedOn.push(born)}

test('Arena usa exactamente los modos compartidos',()=>H.ENTRY_V070===dom.window.SizaEntryRules.MODES&&H.ENTRY_V070.prepare.short==='PREPARACIÓN UNIVERSAL');
test('Preparación universal bloquea una Invocación recién entrada',()=>{const M=fresh('prepare');add(M.player,'reg_entry_one',3);return H.preparingV070(M.player,0)===true&&!H.canAttackV070(M.player,0)});
test('Una Invocación de turno anterior deja de preparar',()=>{const M=fresh('prepare');add(M.player,'reg_entry_two',2);return H.preparingV070(M.player,0)===false&&H.canAttackV070(M.player,0)});
test('Entrada inmediata permite atacar al entrar',()=>{const M=fresh('immediate');add(M.player,'reg_entry_two',3);return !H.preparingV070(M.player,0)&&H.canAttackV070(M.player,0)});
test('Impulso permite una Invocación de un cristal pero no una de dos',()=>{const M=fresh('oneCrystal');add(M.player,'reg_entry_one',3);add(M.player,'reg_entry_two',3);return !H.preparingV070(M.player,0)&&H.preparingV070(M.player,1)&&H.canAttackV070(M.player,0)&&!H.canAttackV070(M.player,1)});
test('Agotamiento bloquea ataque aunque la entrada lo permita',()=>{const M=fresh('immediate');add(M.player,'reg_entry_one',3);M.player.exhausted=[0];return !H.canAttackV070(M.player,0)&&H.availableAttackersV610().length===0});
test('availableAttackers filtra por preparación y agotamiento',()=>{const M=fresh('oneCrystal');add(M.player,'reg_entry_one',3);add(M.player,'reg_entry_two',3);add(M.player,'reg_entry_one',2);M.player.exhausted=[2];return JSON.stringify(H.availableAttackersV610())==='[0]'});
test('Bloqueadores legales ignoran preparación pero excluyen agotadas y no criaturas',()=>{const M=fresh('prepare');add(M.player,'reg_entry_one',3);add(M.player,'reg_entry_two',3);add(M.player,'reg_entry_artifact',3);M.player.exhausted=[1];return JSON.stringify(H.legalBlockersV070(M.player))==='[0]'});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);
const passed=results.filter(r=>r.pass).length;
console.log(`SIZA entry rules regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
