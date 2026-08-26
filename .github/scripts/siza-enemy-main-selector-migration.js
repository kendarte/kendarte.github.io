const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
const assert=(value,message)=>{if(!value)throw new Error(message)};
async function get(path){const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});if(!r.ok)throw new Error(`${path}: GET ${r.status}`);const f=await r.json();return{sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')}}
function inlineCore(html){let out=html;for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js','creature-rules.js']){const tag=`<script src="../siza-core/${name}"></script>`;if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`)}return out}
function makeDom(html,label){const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[JSDOM ${label}]`,e.message));const d=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});d.window.__scheduled=[];d.window.setTimeout=(fn,delay)=>{d.window.__scheduled.push([fn?.name||'',delay]);return 0};return d}

(async()=>{
 const live=await get('siza-mobile-test/index.html');
 const oldPart="const x=E.hand.map((id,i)=>({i,c:cardById(id)})).filter(x=>x.c?.type!=='Land'&&!cardHasEffectV1(x.c,'counter-stack-target','resolve')&&paymentV070(E,x.c)).sort((a,b)=>a.c.difficulty-b.c.difficulty)[0];";
 const newPart="const x=SizaCardEffects.preferredMainPhaseCard(E.hand,cardById,c=>paymentV070(E,c));";
 assert(live.text.includes(oldPart),'enemyChoosePlay selector anchor changed');
 const candidate=live.text.replace(oldPart,newPart),marker='window.SIZA={';
 const probe=`window.__ENEMY_MAIN_SELECTOR_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getModal:()=>state.modal,enemyChoosePlay};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__ENEMY_MAIN_SELECTOR_COMPARE__,n=N.window.__ENEMY_MAIN_SELECTOR_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 const cards={
  land:{id:'land',type:'Land',difficulty:1,effects:[]},
  counter:{id:'counterX',type:'Instant',difficulty:1,effects:[{event:'resolve',type:'counter-stack-target'}]},
  low:{id:'low',type:'Creature',difficulty:4,effects:[]},
  mid:{id:'mid',type:'Instant',difficulty:6,effects:[]},
  tie:{id:'tie',type:'Artifact',difficulty:4,effects:[]},
  high:{id:'high',type:'Creature',difficulty:8,effects:[]}
 };
 const resolve=id=>cards[id],oldPick=(hand,allowed)=>hand.map((id,i)=>({i,c:resolve(id)})).filter(x=>x.c?.type!=='Land'&&!E.hasEffect(x.c,'counter-stack-target','resolve')&&allowed.has(x.c.id)).sort((a,b)=>a.c.difficulty-b.c.difficulty)[0];
 const pureCases=[
  {hand:['high','low','mid'],allowed:['high','low','mid']},
  {hand:['land','counter','mid'],allowed:['land','counter','mid']},
  {hand:['low','tie','high'],allowed:['low','tie','high']},
  {hand:['low','mid'],allowed:['mid']},
  {hand:['counter','land'],allowed:['counter','land']},
  {hand:[],allowed:[]}
 ];
 for(const x of pureCases){const allowed=new Set(x.allowed),a=oldPick(x.hand,allowed),b=E.preferredMainPhaseCard(x.hand,resolve,c=>allowed.has(c.id));assert(JSON.stringify(a)===JSON.stringify(b),`selector mismatch ${JSON.stringify(x)} :: ${JSON.stringify(a)} / ${JSON.stringify(b)}`);compared++}
 function setup(H,{hand=['watcher','servitor'],crystals={U:2,R:1,G:0,W:0,B:0},equipment=[],battlefield=[]}={}){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.active='enemy';M.phase='Main rival';M.responseWindow=null;M.enemyStage='main';const P=M.enemy;P.hand=[...hand];P.library=[];P.graveyard=[];P.battlefield=[...battlefield];P.powerCounters=P.battlefield.map(()=>0);P.summonedOn=P.battlefield.map(()=>0);P.equipment=equipment.map(x=>({...x}));P.artifacts=[];P.crystals={...crystals};P.exhausted=[];P.offeringUsed=false;M.log=[];return M}
 function snap(H,dom,M){const m=H.getModal(),P=M.enemy;return JSON.stringify({active:M.active,phase:M.phase,responseWindow:M.responseWindow,hand:P.hand,crystals:P.crystals,battlefield:P.battlefield,equipment:P.equipment,graveyard:P.graveyard,modal:m?{type:m.type,stage:m.stage,owner:m.owner,idx:m.idx,cardId:m.cardId,dc:m.dc,reactive:m.reactive,targetStackId:m.targetStackId,ai:m.ai,payment:m.payment}:null,log:M.log.map(x=>[x.t,x.m]),scheduled:dom.window.__scheduled.slice()})}
 const runtimeCases=[
  {name:'lowest difficulty playable',options:{hand:['watcher','servitor']}},
  {name:'counter excluded from main',options:{hand:['counter','spark']}},
  {name:'unpayable low candidate skipped',options:{hand:['leviathan','watcher']}},
  {name:'no main play continues phase',options:{hand:['dock','counter']}},
  {name:'loose equipment keeps precedence',options:{hand:['spark'],equipment:[{id:'tideblade',target:null}],battlefield:['servitor']}}
 ];
 for(const x of runtimeCases){O.window.__scheduled.length=0;N.window.__scheduled.length=0;const A=setup(o,x.options),B=setup(n,x.options);o.enemyChoosePlay();n.enemyChoosePlay();const a=snap(o,O,A),b=snap(n,N,B);assert(a===b,`${x.name} mismatch :: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS rival main selector old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared rival main-phase selector',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
