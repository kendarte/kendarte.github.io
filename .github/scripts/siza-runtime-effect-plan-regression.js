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

const html=inlineCore(fs.readFileSync('siza-mobile-test/index.html','utf8'));
const marker='window.SIZA={';
if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__RUNTIME_PLAN_TEST__={createMatch,setMatch:m=>state.match=m,getState:()=>state,applyCardEffectV1,cardById};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM runtime-plan]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
dom.window.setTimeout=()=>0;
const H=dom.window.__RUNTIME_PLAN_TEST__,E=dom.window.SizaCardEffects;
if(!H||!E)throw new Error('runtime plan hooks unavailable');

const results=[];
const test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
function baseMatch(){return{
  player:{library:['dock'],hand:['mist','spark'],graveyard:[],battlefield:[],artifacts:[],equipment:[]},
  enemy:{library:['cinder'],hand:['spark','mist'],graveyard:[],battlefield:[],artifacts:[],equipment:[]},
  stack:[],pendingChoice:null,over:false
}}

test('runtimePlan counter usa objetivo explícito y fallback al tope',()=>{
  const M=baseMatch();M.stack=[{id:'a'},{id:'b'}];
  const a=E.runtimePlan({type:'counter-stack-target'},{match:M,sourceOwner:'player',targetStackId:'a'});
  const b=E.runtimePlan({type:'counter-stack-target'},{match:M,sourceOwner:'player',targetStackId:'x'});
  return a.terminal===true&&a.stackIndex===0&&b.stackIndex===1;
});

test('runtimePlan draw conserva self amount y log de resolve',()=>{
  const p=E.runtimePlan({type:'draw',event:'resolve',amount:2},{match:baseMatch(),sourceOwner:'player'});
  return p.kind==='draw'&&p.targetOwner==='player'&&p.amount===2&&p.logResolve===true&&!p.terminal;
});

test('runtimePlan damage usa opponent por defecto',()=>{
  const p=E.runtimePlan({type:'damage-character',amount:3},{match:baseMatch(),sourceOwner:'player'});
  return p.kind==='damage-character'&&p.targetOwner==='enemy'&&p.amount===3;
});

test('runtimePlan observe distingue choice log y none',()=>{
  const A=baseMatch(),B=baseMatch(),C=baseMatch();C.player.library=[];
  const a=E.runtimePlan({type:'observe-top'},{match:A,sourceOwner:'player'});
  const b=E.runtimePlan({type:'observe-top'},{match:B,sourceOwner:'enemy'});
  const c=E.runtimePlan({type:'observe-top'},{match:C,sourceOwner:'player'});
  return a.action==='choice'&&a.topCardId==='dock'&&b.action==='log'&&b.topCardId==='cinder'&&c.action==='none';
});

test('runtimePlan bounce abre elección al jugador y autoelige para IA',()=>{
  const A=baseMatch();A.player.battlefield=['leviathan','servitor'];A.enemy.artifacts=['prism'];
  const B=baseMatch();B.enemy.battlefield=['leviathan'];B.player.artifacts=['prism'];
  const a=E.runtimePlan({type:'bounce-other-permanent'},{match:A,sourceOwner:'player',entryIndex:0});
  const b=E.runtimePlan({type:'bounce-other-permanent'},{match:B,sourceOwner:'enemy',entryIndex:0});
  return a.action==='choice'&&a.targets.some(x=>x.id==='servitor')&&b.action==='bounce'&&b.preferredTarget?.owner==='player'&&b.preferredTarget?.id==='prism';
});

test('runtimePlan discard conserva choice discard-last y amount no soportado',()=>{
  const A=baseMatch(),B=baseMatch(),C=baseMatch();
  const a=E.runtimePlan({type:'discard',amount:1},{match:A,sourceOwner:'player'});
  const b=E.runtimePlan({type:'discard',amount:1},{match:B,sourceOwner:'enemy'});
  const c=E.runtimePlan({type:'discard',amount:2},{match:C,sourceOwner:'player'});
  return a.targetOwner==='player'&&a.action==='choice'&&b.targetOwner==='enemy'&&b.action==='discard-last'&&c.action==='none';
});

function fresh(){
  const M=H.createMatch(false,'prepare');H.setMatch(M);M.pendingChoice=null;M.over=false;M.log=[];M.stack=[];
  for(const side of ['player','enemy']){
    const P=M[side];P.life=20;P.hand=[];P.library=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.artifacts=[];P.equipment=[];P.equipmentTargets=[];
  }
  return M;
}

test('executor aplica draw desde runtimePlan',()=>{
  const M=fresh();M.player.library=['dock','cinder'];
  const s={owner:'player'},c=H.cardById('mist');
  H.applyCardEffectV1({type:'draw',event:'resolve',amount:2,target:'self'},s,c,M.player,M.enemy,null);
  return JSON.stringify(M.player.hand)===JSON.stringify(['dock','cinder']);
});

test('executor aplica counter y daño desde runtimePlan',()=>{
  const M=fresh();M.stack=[{id:'target',cardId:'spark',owner:'enemy'}];
  H.applyCardEffectV1({type:'counter-stack-target',event:'resolve'},{owner:'player',targetStackId:'target'},H.cardById('counter'),M.player,M.enemy,null);
  const counterOk=M.stack.length===0&&M.enemy.graveyard.includes('spark');
  H.applyCardEffectV1({type:'damage-character',event:'resolve',amount:2,target:'opponent'},{owner:'player'},H.cardById('spark'),M.player,M.enemy,null);
  return counterOk&&M.enemy.life===18;
});

test('executor conserva observe bounce y discard como elecciones del jugador',()=>{
  const M=fresh();M.player.library=['dock'];
  H.applyCardEffectV1({type:'observe-top',event:'enter',target:'self'},{owner:'player'},H.cardById('servitor'),M.player,M.enemy,0);
  const observe=M.pendingChoice?.type==='observe'&&M.pendingChoice.cardId==='dock';
  M.pendingChoice=null;M.player.battlefield=['leviathan','servitor'];M.player.powerCounters=[0,0];M.player.summonedOn=[0,0];
  H.applyCardEffectV1({type:'bounce-other-permanent',event:'enter'},{owner:'player'},H.cardById('leviathan'),M.player,M.enemy,0);
  const bounce=M.pendingChoice?.type==='bounce'&&M.pendingChoice.targets.some(x=>x.id==='servitor');
  M.pendingChoice=null;M.player.hand=['mist'];
  H.applyCardEffectV1({type:'discard',event:'enter',amount:1,target:'self'},{owner:'player'},H.cardById('queen'),M.player,M.enemy,null);
  return observe&&bounce&&M.pendingChoice?.type==='discard';
});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);
const passed=results.filter(r=>r.pass).length;
console.log(`SIZA runtime effect plan regression: ${passed}/${results.length}`);
dom.window.close();
if(passed!==results.length)process.exit(1);
