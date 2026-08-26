const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

function inlineCore(html){
  let out=html;
  for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']){
    const tag=`<script src="../siza-core/${name}"></script>`;
    if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);
    out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
  }
  return out;
}

const original=inlineCore(fs.readFileSync('siza-mobile-test/index.html','utf8'));
const marker='window.SIZA={';
if(!original.includes(marker))throw new Error('SIZA export marker not found');
const probe=`window.__SIZA_PRISM_TEST__={createMatch,setMatch:m=>state.match=m,setModal:m=>state.modal=m,usePrismV070,enemyResolveManifestRoll,manifestInlineHtml,manifestBonusSourcesV1,applyManifestBonusSourceV1,TEST_CARD_DB_V1};\n`;
const virtualConsole=new VirtualConsole();
virtualConsole.on('jsdomError',error=>console.error('[JSDOM prism]',error.message));
const dom=new JSDOM(original.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole});
dom.window.setTimeout=()=>0;
const H=dom.window.__SIZA_PRISM_TEST__,R=dom.window.SizaManifestRules;
if(!H||!R)throw new Error('Prism test hooks were not exposed');

const results=[];
const test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};

function setupPlayer(cardId='counter',artifactId='prism',roll=3,dc=6){
  const M=H.createMatch(false,'prepare');
  H.setMatch(M);
  M.player.artifacts=[artifactId];
  M.player.artifactExhausted=[];
  M.player.hand=[cardId];
  const modal={type:'manifest',owner:'player',cardId,idx:0,roll,burnSelected:[],prismBonus:0,dc,ai:false,stage:'roll',payment:{spent:{}}};
  H.setModal(modal);
  return{M,modal};
}

function setupAi({cardId='counter',hand=['counter','dock'],artifacts=['prism'],roll=3,dc=6,prismBonus=0,burnSelected=[],aiFailure=false,mf=null}={}){
  const M=H.createMatch(false,'prepare');
  H.setMatch(M);
  M.enemy.artifacts=[...artifacts];
  M.enemy.artifactExhausted=[];
  M.enemy.hand=[...hand];
  if(mf!=null)M.enemy.mf=mf;
  const modal={type:'manifest',owner:'enemy',cardId,idx:0,roll,burnSelected:[...burnSelected],prismBonus,dc,ai:true,stage:'roll',payment:{spent:{}}};
  if(aiFailure)modal.aiFailure=true;
  H.setModal(modal);
  return{M,modal};
}

test('Prisma oficial descubre bonus +1 desde effects',()=>{
  const {M}=setupPlayer();
  const source=H.manifestBonusSourcesV1(M.player,dom.window.SizaCardCatalog.get('counter'))[0];
  return source?.id==='prism'&&source.effect.type==='manifest-bonus'&&source.effect.amount===1&&source.effect.requiresPip==='U'&&source.effect.exhaustSource===true;
});

test('Jugador agota Prisma y recibe +1 visible',()=>{
  const {M,modal}=setupPlayer();
  const before=H.manifestInlineHtml();
  H.usePrismV070();
  return before.includes('AGOTAR PRISMA +1')&&modal.prismBonus===1&&M.player.artifactExhausted.length===1&&M.player.artifactExhausted[0]===0;
});

test('Prisma no aplica a una Manafestation sin pip Azul',()=>{
  const {M,modal}=setupPlayer('spark');
  H.usePrismV070();
  return modal.prismBonus===0&&M.player.artifactExhausted.length===0&&!H.manifestInlineHtml().includes('AGOTAR PRISMA');
});

test('IA usa Prisma cuando le falta exactamente uno',()=>{
  const {M,modal}=setupAi();
  H.enemyResolveManifestRoll();
  return modal.prismBonus===1&&M.enemy.artifactExhausted[0]===0&&modal.burnSelected.length===0;
});

test('Fuente temporal desconocida puede dar +2 sólo por effects',()=>{
  H.TEST_CARD_DB_V1.push({id:'regression_generated_focus',name:'Regression Focus',type:'Artifact',cost:1,difficulty:1,pips:{},text:'Focus.',art:'multi',glyph:'F',effects:[{event:'manifest-roll',type:'manifest-bonus',amount:2,requiresPip:'U',exhaustSource:true}]});
  const {M,modal}=setupPlayer('counter','regression_generated_focus',2,6);
  const source=H.manifestBonusSourcesV1(M.player,dom.window.SizaCardCatalog.get('counter'))[0];
  const before=H.manifestInlineHtml();
  H.usePrismV070();
  return source?.id==='regression_generated_focus'&&source.effect.amount===2&&before.includes('AGOTAR PRISMA +2')&&modal.prismBonus===2&&M.player.artifactExhausted[0]===0;
});

test('aiManifestRollPlan usa bonus sólo con déficit exactamente uno',()=>{
  const bonus={index:0,effect:{amount:1}};
  const one=R.aiManifestRollPlan({dc:3,roll:2,prismBonus:0,burnSelected:[]},{mf:0},[],bonus);
  const two=R.aiManifestRollPlan({dc:4,roll:2,prismBonus:0,burnSelected:[]},{mf:0},[1,2],bonus);
  return one.bonus===bonus&&!one.aiFailure&&one.burnSelected.length===0&&two.bonus===null&&!two.aiFailure&&JSON.stringify(two.burnSelected)===JSON.stringify([1,2]);
});

test('aiManifestRollPlan reporta fallo sin reemplazar Burn previo',()=>{
  const modal={dc:5,roll:1,prismBonus:0,burnSelected:[9]};
  const plan=R.aiManifestRollPlan(modal,{mf:0},[1],null);
  return plan.aiFailure===true&&plan.burnSelected===null&&JSON.stringify(modal.burnSelected)===JSON.stringify([9]);
});

test('IA selecciona la primera Reserva necesaria como Burn',()=>{
  const {M,modal}=setupAi({artifacts:[],hand:['counter','dock','cinder'],roll:2,dc:6,mf:3});
  H.enemyResolveManifestRoll();
  return modal.prismBonus===0&&!modal.aiFailure&&JSON.stringify(modal.burnSelected)===JSON.stringify([1])&&M.enemy.artifactExhausted.length===0;
});

test('IA no usa Prisma cuando el déficit es dos',()=>{
  const {M,modal}=setupAi({hand:['counter','dock','cinder'],roll:2,dc:7,mf:3});
  H.enemyResolveManifestRoll();
  return modal.prismBonus===0&&!modal.aiFailure&&JSON.stringify(modal.burnSelected)===JSON.stringify([1,2])&&M.enemy.artifactExhausted.length===0;
});

test('IA conserva aiFailure histórico aunque luego el total alcance D',()=>{
  const {modal}=setupAi({artifacts:[],hand:['counter'],roll:3,dc:5,mf:2,aiFailure:true,burnSelected:[9]});
  H.enemyResolveManifestRoll();
  return modal.aiFailure===true&&modal.burnSelected.length===0;
});

for(const result of results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
const passed=results.filter(result=>result.pass).length;
console.log(`SIZA Prism data-driven regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
