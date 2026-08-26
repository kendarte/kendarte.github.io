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
const probe=`window.__SIZA_PRISM_TEST__={createMatch,setMatch:m=>state.match=m,setModal:m=>state.modal=m,getState:()=>state,usePrismV070,selectBurn,consumeBurnV070,commitManifest,failManifest,enemyResolveManifestRoll,manifestInlineHtml,manifestBonusSourcesV1,applyManifestBonusSourceV1,TEST_CARD_DB_V1};\n`;
const virtualConsole=new VirtualConsole();
virtualConsole.on('jsdomError',error=>console.error('[JSDOM prism]',error.message));
const dom=new JSDOM(original.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole});
dom.window.setTimeout=()=>0;
const H=dom.window.__SIZA_PRISM_TEST__,R=dom.window.SizaManifestRules,E=dom.window.SizaCardEffects;
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

function setupBurn({hand=['counter','dock','cinder'],roll=2,dc=6,mf=3,idx=0,selected=[],ai=false}={}){
  const M=H.createMatch(false,'prepare');H.setMatch(M);M.player.hand=[...hand];M.player.mf=mf;
  const modal={type:'manifest',owner:'player',cardId:M.player.hand[idx],idx,roll,burnSelected:[...selected],prismBonus:0,dc,ai,stage:'roll',payment:{spent:{}}};
  H.setModal(modal);return{M,modal};
}

function setupOutcome({owner='player',hand=['counter'],idx=0,cardId=null,mf=2,roll=3,dc=6,prismBonus=0,burnSelected=[],reactive=false,targetStackId=null}={}){
  const M=H.createMatch(false,'prepare');H.setMatch(M);M.stack=[];M.stackReturnOwner=null;M.log=[];M.active='player';M.phase='Main';
  const P=M[owner];P.hand=[...hand];P.exile=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.mf=mf;
  const modal={type:'manifest',owner,cardId:cardId||P.hand[idx],idx,roll,burnSelected:[...burnSelected],prismBonus,dc,ai:owner==='enemy',stage:'roll',reactive,targetStackId,payment:{spent:{}}};
  H.setModal(modal);return{M,P,modal};
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

test('burnSelectionPlan agrega y quita la misma Reserva',()=>{
  const modal={dc:6,roll:2,prismBonus:0,burnSelected:[],idx:0,ai:false},P={mf:3};
  const a=R.burnSelectionPlan(modal,P,1,true);modal.burnSelected=a;const b=R.burnSelectionPlan(modal,P,1,true);
  return JSON.stringify(a)==='[1]'&&JSON.stringify(b)==='[]';
});

test('burnSelectionPlan respeta el máximo dictado por déficit',()=>{
  const modal={dc:6,roll:2,prismBonus:0,burnSelected:[1],idx:0,ai:false};
  return JSON.stringify(R.burnSelectionPlan(modal,{mf:3},2,true))==='[1]';
});

test('burnSelectionPlan rechaza no-Land carta fuente y modo IA',()=>{
  const base={dc:7,roll:2,prismBonus:0,burnSelected:[],idx:0,ai:false};
  return R.burnSelectionPlan(base,{mf:3},1,false)===null&&R.burnSelectionPlan(base,{mf:3},0,true)===null&&R.burnSelectionPlan({...base,ai:true},{mf:3},1,true)===null;
});

test('selectBurn runtime usa el plan compartido',()=>{
  const {modal}=setupBurn({dc:7,mf:3});H.selectBurn(1);H.selectBurn(2);H.selectBurn(1);
  return JSON.stringify(modal.burnSelected)===JSON.stringify([2]);
});

test('burnConsumptionPlan ordena descendente y rebasa índice manifestado',()=>{
  const plan=R.burnConsumptionPlan({idx:3,burnSelected:[0,4,2]});
  return JSON.stringify(plan.indices)===JSON.stringify([4,2,0])&&plan.manifestIndex===1;
});

test('burnConsumptionPlan conserva rebasing paso a paso con duplicados',()=>{
  const plan=R.burnConsumptionPlan({idx:3,burnSelected:[2,2]});
  return JSON.stringify(plan.indices)===JSON.stringify([2,2])&&plan.manifestIndex===2;
});

test('burnConsumptionPlan conserva error histórico con modal incompleto',()=>{
  let threw=false;try{R.burnConsumptionPlan({idx:1})}catch{threw=true}return threw;
});

test('consumeBurn runtime exilia descendente y conserva carta manifestada',()=>{
  const {M,modal}=setupBurn({hand:['dock','mist','counter','spark','cinder'],idx:2,selected:[0,4]});M.player.exile=[];H.consumeBurnV070(modal,M.player);
  return JSON.stringify(M.player.hand)===JSON.stringify(['mist','counter','spark'])&&JSON.stringify(M.player.exile)===JSON.stringify(['cinder','dock'])&&modal.idx===1&&M.player.hand[modal.idx]==='counter';
});

test('manifestOutcome conserva Burn total y umbral de éxito',()=>{
  const fail=R.manifestOutcome({dc:6,roll:3,prismBonus:0,burnSelected:[]},{mf:2});
  const pass=R.manifestOutcome({dc:6,roll:3,prismBonus:0,burnSelected:[1]},{mf:2});
  return fail.burn===0&&fail.total===5&&!fail.success&&pass.burn===1&&pass.total===6&&pass.success;
});

test('manifestStackPlan conserva carta owner y target reactivo',()=>{
  const counter=dom.window.SizaCardCatalog.get('counter'),mist=dom.window.SizaCardCatalog.get('mist'),has=(c,t,e)=>E.hasEffect(c,t,e);
  const reactive=R.manifestStackPlan({idx:1,owner:'player',reactive:true,targetStackId:'stk_target'},{hand:['dock','counter']},counter,has);
  const normal=R.manifestStackPlan({idx:0,owner:'enemy',reactive:true,targetStackId:'stk_target'},{hand:['mist']},mist,has);
  return reactive.cardId==='counter'&&reactive.owner==='player'&&reactive.targetStackId==='stk_target'&&normal.cardId==='mist'&&normal.owner==='enemy'&&normal.targetStackId===null;
});

test('manifestFailurePlan conserva total sin Burn y continuación',()=>{
  const player=R.manifestFailurePlan({owner:'player',reactive:false,roll:2,prismBonus:1,burnSelected:[9]},{mf:2});
  const enemy=R.manifestFailurePlan({owner:'enemy',reactive:false,roll:2,prismBonus:0,burnSelected:[9]},{mf:2});
  const reactive=R.manifestFailurePlan({owner:'enemy',reactive:true,roll:2,prismBonus:0,burnSelected:[9]},{mf:2});
  return player.total===5&&player.resume==='none'&&enemy.total===4&&enemy.resume==='enemy'&&reactive.total===4&&reactive.resume==='priority';
});

test('commitManifest usa outcome y stack plan compartidos',()=>{
  const {M,P}=setupOutcome({hand:['dock','counter','cinder'],idx:1,cardId:'counter',mf:2,roll:3,dc:6,burnSelected:[0],reactive:true,targetStackId:'stk_target'});P.exile=[];H.commitManifest();
  return H.getState().modal===null&&JSON.stringify(P.hand)===JSON.stringify(['cinder'])&&JSON.stringify(P.exile)===JSON.stringify(['dock'])&&M.stack.length===1&&M.stack[0].cardId==='counter'&&M.stack[0].owner==='player'&&M.stack[0].targetStackId==='stk_target';
});

test('failManifest usa failure plan y devuelve Main al rival',()=>{
  const {M,P}=setupOutcome({owner:'enemy',hand:['mist'],idx:0,cardId:'mist',mf:2,roll:2,dc:7});H.failManifest();
  return H.getState().modal===null&&M.active==='enemy'&&JSON.stringify(P.hand)===JSON.stringify(['mist'])&&M.stack.length===0;
});

for(const result of results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
const passed=results.filter(result=>result.pass).length;
console.log(`SIZA Prism data-driven regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
