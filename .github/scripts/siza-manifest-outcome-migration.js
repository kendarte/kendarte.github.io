const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');
const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`,headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'},assert=(v,m)=>{if(!v)throw new Error(m)};
async function get(path){const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});if(!r.ok)throw new Error(`${path}: GET ${r.status}`);const f=await r.json();return{sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')}}
function inlineCore(html){let out=html;for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js','creature-rules.js']){const tag=`<script src="../siza-core/${name}"></script>`;assert(out.includes(tag),`Missing ${tag}`);out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`)}return out}
function makeDom(html,label){const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[${label}]`,e.message));const d=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});d.window.Date.now=()=>1000;d.window.Math.random=()=>0.25;return d}
function oldOutcome(m,p){const burn=m.burnSelected.length,total=p.mf+m.roll+m.prismBonus+burn;return{burn,total,success:total>=m.dc}}
function oldStackPlan(m,p,c,has){return{cardId:p.hand[m.idx],owner:m.owner,targetStackId:m.reactive&&has(c,'counter-stack-target','resolve')?m.targetStackId:null}}
function oldFailurePlan(m,p){return{total:p.mf+m.roll+m.prismBonus,resume:m.reactive?'priority':m.owner==='enemy'?'enemy':'none'}}
(async()=>{
 const live=await get('siza-mobile-test/index.html');
 const oldCommit="function commitManifest(){const m=state.modal,M=state.match;if(!m||m.roll==null)return;const P=M[m.owner],c=cardById(m.cardId),burn=m.burnSelected.length,total=P.mf+m.roll+m.prismBonus+burn;if(total<m.dc)return;consumeBurnV070(m,P);const id=P.hand.splice(m.idx,1)[0];if(m.offeringIndex!=null){const off=removeBattlefieldAt(P,m.offeringIndex);addLog('Ofrenda · prueba',cardById(off).name+' se sacrifica después del éxito.')}if(!M.stack.length)M.stackReturnOwner=m.owner;const obj={id:'stk_'+Date.now()+Math.random(),cardId:id,owner:m.owner,targetStackId:m.reactive&&cardHasEffectV1(c,'counter-stack-target','resolve')?m.targetStackId:null};M.stack.push(obj);addLog(m.reactive?'Respuesta':'Manafestation',(m.owner==='enemy'?'Rival · ':'')+c.name+': MF '+P.mf+' + dado '+m.roll+(m.prismBonus?' + Prisma 1':'')+(burn?' + Burn '+burn:'')+' = '+total+' / D'+m.dc+' — ÉXITO.');state.modal=null;openPriorityV070(obj);save();render()}";
 const newCommit="function commitManifest(){const m=state.modal,M=state.match;if(!m||m.roll==null)return;const P=M[m.owner],c=cardById(m.cardId),outcome=SizaManifestRules.manifestOutcome(m,P);if(!outcome.success)return;consumeBurnV070(m,P);const plan=SizaManifestRules.manifestStackPlan(m,P,c,cardHasEffectV1);P.hand.splice(m.idx,1);if(m.offeringIndex!=null){const off=removeBattlefieldAt(P,m.offeringIndex);addLog('Ofrenda · prueba',cardById(off).name+' se sacrifica después del éxito.')}if(!M.stack.length)M.stackReturnOwner=m.owner;const obj={id:'stk_'+Date.now()+Math.random(),cardId:plan.cardId,owner:plan.owner,targetStackId:plan.targetStackId};M.stack.push(obj);addLog(m.reactive?'Respuesta':'Manafestation',(m.owner==='enemy'?'Rival · ':'')+c.name+': MF '+P.mf+' + dado '+m.roll+(m.prismBonus?' + Prisma 1':'')+(outcome.burn?' + Burn '+outcome.burn:'')+' = '+outcome.total+' / D'+m.dc+' — ÉXITO.');state.modal=null;openPriorityV070(obj);save();render()}";
 const oldFail="function failManifest(){const m=state.modal,M=state.match;if(!m||m.roll==null)return;const P=M[m.owner],c=cardById(m.cardId),total=P.mf+m.roll+m.prismBonus;addLog('Fallo',`${c.name}: MF ${P.mf} + dado ${m.roll}${m.prismBonus?' + Prisma 1':''} = ${total} / D${m.dc}. Carta en mano; cristales gastados.${m.offeringIndex!=null?' La Ofrenda sobrevive agotada.':''}`);state.modal=null;save();render();if(m.reactive)return setTimeout(()=>passPriorityV070(m.owner),350);if(m.owner==='enemy'){M.active='enemy';setTimeout(enemyChoosePlay,420)}}";
 const newFail="function failManifest(){const m=state.modal,M=state.match;if(!m||m.roll==null)return;const P=M[m.owner],c=cardById(m.cardId),plan=SizaManifestRules.manifestFailurePlan(m,P);addLog('Fallo',`${c.name}: MF ${P.mf} + dado ${m.roll}${m.prismBonus?' + Prisma 1':''} = ${plan.total} / D${m.dc}. Carta en mano; cristales gastados.${m.offeringIndex!=null?' La Ofrenda sobrevive agotada.':''}`);state.modal=null;save();render();if(plan.resume==='priority')return setTimeout(()=>passPriorityV070(m.owner),350);if(plan.resume==='enemy'){M.active='enemy';setTimeout(enemyChoosePlay,420)}}";
 assert(live.text.includes(oldCommit),'commitManifest anchor changed');assert(live.text.includes(oldFail),'failManifest anchor changed');
 const candidate=live.text.replace(oldCommit,newCommit).replace(oldFail,newFail),marker='window.SIZA={';assert(candidate.includes(marker),'SIZA export marker missing');
 const probe=`window.__MANIFEST_OUTCOME__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getState:()=>state,commitManifest,failManifest,cardById,cardHasEffectV1};\n`;
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new'),o=O.window.__MANIFEST_OUTCOME__,n=N.window.__MANIFEST_OUTCOME__,R=N.window.SizaManifestRules,E=N.window.SizaCardEffects;let compared=0;
 const pureOut=[
  [{dc:6,roll:3,prismBonus:0,burnSelected:[]},{mf:2}],
  [{dc:6,roll:3,prismBonus:0,burnSelected:[1]},{mf:2}],
  [{dc:6,roll:2,prismBonus:1,burnSelected:[]},{mf:3}],
  [{dc:8,roll:1,prismBonus:2,burnSelected:[1,2]},{mf:3}]
 ];
 for(const [m,p] of pureOut){const a=oldOutcome(m,p),b=R.manifestOutcome(m,p);assert(JSON.stringify(a)===JSON.stringify(b),`manifestOutcome mismatch ${JSON.stringify([m,p])}`);compared++}
 const counter=N.window.SizaCardCatalog.get('counter'),mist=N.window.SizaCardCatalog.get('mist'),has=(c,t,e)=>E.hasEffect(c,t,e);
 const pureStack=[
  [{idx:1,owner:'player',reactive:false,targetStackId:'stk_old'},{hand:['dock','mist']},counter],
  [{idx:1,owner:'player',reactive:true,targetStackId:'stk_old'},{hand:['dock','counter']},counter],
  [{idx:0,owner:'enemy',reactive:true,targetStackId:'stk_old'},{hand:['mist']},mist],
  [{idx:0,owner:'enemy',reactive:false,targetStackId:null},{hand:['counter']},counter]
 ];
 for(const [m,p,c] of pureStack){const a=oldStackPlan(m,p,c,has),b=R.manifestStackPlan(m,p,c,has);assert(JSON.stringify(a)===JSON.stringify(b),`manifestStackPlan mismatch ${JSON.stringify([m,p,c?.id])}`);compared++}
 const pureFail=[
  [{owner:'player',reactive:false,roll:2,prismBonus:0},{mf:3}],
  [{owner:'enemy',reactive:false,roll:2,prismBonus:1},{mf:2}],
  [{owner:'enemy',reactive:true,roll:1,prismBonus:0},{mf:4}],
  [{owner:'player',reactive:true,roll:4,prismBonus:2},{mf:0}]
 ];
 for(const [m,p] of pureFail){const a=oldFailurePlan(m,p),b=R.manifestFailurePlan(m,p);assert(JSON.stringify(a)===JSON.stringify(b),`manifestFailurePlan mismatch ${JSON.stringify([m,p])}`);compared++}
 function installTimer(H,win){const arr=[];win.setTimeout=(fn,delay)=>{arr.push({name:fn?.name||'',delay});return 0};H.__timers=arr;return arr}
 const ot=installTimer(o,O.window),nt=installTimer(n,N.window);
 function setup(H,cfg){const M=H.createMatch(false,'prepare');H.setMatch(M);M.stack=[];M.stackReturnOwner=null;M.responseWindow=null;M.pendingResolution=false;M.active='player';M.phase='Main';M.log=[];for(const side of ['player','enemy']){const P=M[side];P.hand=[];P.exile=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.equipment=[];P.equipmentTargets=[]}const owner=cfg.owner||'player',P=M[owner];P.mf=cfg.mf??2;P.hand=[...(cfg.hand||['mist'])];if(cfg.offering){P.battlefield=['servitor'];P.powerCounters=[0];P.summonedOn=[0];P.exhausted=[]}const m={type:'manifest',owner,cardId:cfg.cardId||P.hand[cfg.idx??0],idx:cfg.idx??0,roll:cfg.roll??3,burnSelected:[...(cfg.burnSelected||[])],prismBonus:cfg.prismBonus??0,dc:cfg.dc??5,ai:owner==='enemy',stage:'roll',reactive:!!cfg.reactive,targetStackId:cfg.targetStackId??null,offeringIndex:cfg.offering?0:null,payment:{spent:{}}};H.setModal(m);H.__timers.length=0;return{M,P,m}}
 function snap(H){const s=H.getState(),M=s.match,pick=P=>({hand:P.hand,exile:P.exile,graveyard:P.graveyard,battlefield:P.battlefield,powerCounters:P.powerCounters,summonedOn:P.summonedOn,exhausted:P.exhausted,equipment:P.equipment,equipmentTargets:P.equipmentTargets});return JSON.stringify({modal:s.modal,player:pick(M.player),enemy:pick(M.enemy),stack:M.stack,stackReturnOwner:M.stackReturnOwner,responseWindow:M.responseWindow,pendingResolution:M.pendingResolution,active:M.active,phase:M.phase,log:M.log,timers:H.__timers})}
 const commits=[
  {hand:['mist'],cardId:'mist',idx:0,mf:2,roll:2,dc:6},
  {hand:['mist'],cardId:'mist',idx:0,mf:2,roll:3,dc:5},
  {hand:['dock','counter','cinder'],cardId:'counter',idx:1,mf:2,roll:3,dc:6,burnSelected:[0],reactive:true,targetStackId:'stk_target'},
  {hand:['spark'],cardId:'spark',idx:0,mf:3,roll:3,dc:6,offering:true},
  {owner:'enemy',hand:['mist'],cardId:'mist',idx:0,mf:3,roll:3,dc:6}
 ];
 for(const cfg of commits){const A=setup(o,cfg),B=setup(n,cfg);o.commitManifest();n.commitManifest();const a=snap(o),b=snap(n);assert(a===b,`commit runtime mismatch ${JSON.stringify(cfg)}\nOLD ${a}\nNEW ${b}`);compared++}
 const fails=[
  {hand:['mist'],cardId:'mist',idx:0,mf:2,roll:2,dc:7},
  {owner:'enemy',hand:['mist'],cardId:'mist',idx:0,mf:2,roll:2,dc:7},
  {owner:'enemy',hand:['counter'],cardId:'counter',idx:0,mf:2,roll:2,dc:7,reactive:true,targetStackId:'stk_target'}
 ];
 for(const cfg of fails){setup(o,cfg);setup(n,cfg);o.failManifest();n.failManifest();const a=snap(o),b=snap(n);assert(a===b,`fail runtime mismatch ${JSON.stringify(cfg)}\nOLD ${a}\nNEW ${b}`);compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);console.log(`PASS Manafestation outcome old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during migration');const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared Manafestation outcome plans',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);console.log('COMMIT '+(await put.json()).commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
