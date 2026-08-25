const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

function inlineCore(html){
  let out=html;
  for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js']){
    const tag=`<script src="../siza-core/${name}"></script>`;
    if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);
    out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
  }
  return out;
}

const original=inlineCore(fs.readFileSync('siza-mobile-test/index.html','utf8'));
const marker='window.SIZA={';
if(!original.includes(marker))throw new Error('SIZA export marker not found');
const probe=`window.__SIZA_EQUIPMENT_TEST__={createMatch,setMatch:m=>state.match=m,normalizeMatchV600,resolveTopStack,effectivePower,beginEquip,chooseEquipCrystalV070,equipTo,matchCardMini,TEST_CARD_DB_V1,isEquipmentCardV1,equipmentEquipCostV1,equipmentPowerBonusV1};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM equipment]',e.message));
const dom=new JSDOM(original.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
dom.window.setTimeout=()=>0;
const H=dom.window.__SIZA_EQUIPMENT_TEST__;
if(!H)throw new Error('Equipment hooks were not exposed');

const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

function fresh(){const M=H.createMatch(false,'prepare');H.setMatch(M);return M}

test('Espada se clasifica como Equipment desde datos',()=>{
  const c=dom.window.SizaCardCatalog.get('tideblade');
  return H.isEquipmentCardV1(c)&&H.equipmentEquipCostV1(c)===1&&c.effects?.[0]?.event==='equipped'&&c.effects[0].type==='modify-power'&&c.effects[0].amount===2;
});

test('Espada resuelve a zona Equipment, no Reliquias',()=>{
  const M=fresh();M.player.equipment=[];M.player.artifacts=[];M.stack=[{id:'blade-stack',cardId:'tideblade',owner:'player'}];H.resolveTopStack();
  return M.player.equipment[0]?.id==='tideblade'&&M.player.equipment[0].target===null&&M.player.artifacts.length===0;
});

test('Equipar {1} consume exactamente un cristal y fija objetivo',()=>{
  const M=fresh();M.active='player';M.phase='Main';M.player.battlefield=['servitor'];M.player.powerCounters=[0];M.player.summonedOn=[0];M.player.equipment=[{id:'tideblade',target:null}];M.player.crystals={U:1,R:1};
  H.beginEquip(0);H.chooseEquipCrystalV070('U');H.equipTo(0);
  return M.player.crystals.U===0&&M.player.crystals.R===1&&M.player.equipment[0].target===0&&H.effectivePower(M.player,0)===4;
});

test('Equipo temporal desconocido usa equipCost 1 y +3 por effects',()=>{
  H.TEST_CARD_DB_V1.push({id:'regression_generated_blade',name:'Regression Blade',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'Equipped creature gets +3/+0.',art:'multi',glyph:'B',effects:[{event:'equipped',type:'modify-power',amount:3}]});
  const M=fresh();M.player.equipment=[];M.player.artifacts=[];M.stack=[{id:'generated-stack',cardId:'regression_generated_blade',owner:'player'}];H.resolveTopStack();
  if(M.player.equipment[0]?.id!=='regression_generated_blade'||M.player.artifacts.length)return false;
  M.player.battlefield=['servitor'];M.player.powerCounters=[0];M.player.summonedOn=[0];M.player.crystals={U:1,R:1};H.beginEquip(0);H.chooseEquipCrystalV070('U');H.equipTo(0);
  return H.effectivePower(M.player,0)===5&&H.matchCardMini('servitor','player',0).includes('+3/+0');
});

test('Normalización de partida mueve Equipment generado fuera de battlefield',()=>{
  const M=fresh();M.player.battlefield=['regression_generated_blade'];M.player.powerCounters=[0];M.player.summonedOn=[0];M.player.equipment=[];M.player.artifacts=[];H.normalizeMatchV600();
  return M.player.battlefield.length===0&&M.player.equipment[0]?.id==='regression_generated_blade'&&M.player.artifacts.length===0;
});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);
const passed=results.filter(r=>r.pass).length;
console.log(`SIZA Equipment data-driven regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
