const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
const assert=(value,message)=>{if(!value)throw new Error(message)};
async function get(path){const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});if(!r.ok)throw new Error(`${path}: GET ${r.status}`);const f=await r.json();return{sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')}}
function inlineCore(html){let out=html;for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js','creature-rules.js']){const tag=`<script src="../siza-core/${name}"></script>`;if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`)}return out}
function makeDom(html,label){const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[JSDOM ${label}]`,e.message));const d=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});d.window.setTimeout=()=>0;return d}

(async()=>{
  const live=await get('siza-mobile-test/index.html');
  const oldFn="function enemyRespondV070(){const M=state.match,R=M?.responseWindow;if(!R||R.responder!=='enemy'||state.modal)return;const E=M.enemy,x=E.hand.map((id,i)=>({i,c:cardById(id)})).filter(x=>x.c?.type==='Instant'&&paymentV070(E,x.c)).sort((a,b)=>(cardHasEffectV1(a.c,'counter-stack-target','resolve')?-1:0)-(cardHasEffectV1(b.c,'counter-stack-target','resolve')?-1:0))[0];if(!x){addLog('Prioridad rival','El rival pasa.');return passPriorityV070('enemy')}openManifest(x.i,x.c,'enemy',true)}";
  const newFn="function enemyRespondV070(){const M=state.match,R=M?.responseWindow;if(!R||R.responder!=='enemy'||state.modal)return;const E=M.enemy,x=SizaCardEffects.preferredResponseCard(E.hand,cardById,c=>paymentV070(E,c));if(!x){addLog('Prioridad rival','El rival pasa.');return passPriorityV070('enemy')}openManifest(x.i,x.c,'enemy',true)}";
  assert(live.text.includes(oldFn),'enemyRespondV070 anchor changed');
  const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
  const probe=`window.__PRIORITY_RESPONSE_COMPARE__={createMatch,setMatch:m=>state.match=m,getMatch:()=>state.match,setModal:v=>state.modal=v,getModal:()=>state.modal,enemyRespondV070,cardById,paymentV070};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__PRIORITY_RESPONSE_COMPARE__,n=N.window.__PRIORITY_RESPONSE_COMPARE__,E=N.window.SizaCardEffects;
  let compared=0;

  const cards={
    a:{id:'a',type:'Instant',effects:[]},
    b:{id:'b',type:'Instant',effects:[{event:'resolve',type:'counter-stack-target'}]},
    c:{id:'c',type:'Creature',effects:[{event:'resolve',type:'counter-stack-target'}]},
    d:{id:'d',type:'Instant',effects:[]},
    e:{id:'e',type:'Instant',effects:[{event:'resolve',type:'counter-stack-target'}]}
  };
  const resolve=id=>cards[id],oldPick=(hand,allowed)=>hand.map((id,i)=>({i,c:resolve(id)})).filter(x=>x.c?.type==='Instant'&&allowed.has(x.c.id)).sort((a,b)=>(E.hasEffect(a.c,'counter-stack-target','resolve')?-1:0)-(E.hasEffect(b.c,'counter-stack-target','resolve')?-1:0))[0]||null;
  const selectionCases=[
    {hand:['a','b','d'],allowed:['a','b','d']},
    {hand:['a','d'],allowed:['a','d']},
    {hand:['c','a'],allowed:['c','a']},
    {hand:['b','a'],allowed:['a']},
    {hand:['b','e','a'],allowed:['b','e','a']},
    {hand:[],allowed:[]}
  ];
  for(const x of selectionCases){const allowed=new Set(x.allowed),a=oldPick(x.hand,allowed),b=E.preferredResponseCard(x.hand,resolve,c=>allowed.has(c.id));assert(JSON.stringify(a)===JSON.stringify(b),`selector mismatch ${JSON.stringify(x)} :: ${JSON.stringify(a)} / ${JSON.stringify(b)}`);compared++}

  function setup(H,{hand=['mist','counter','spark'],crystals={U:2,R:1,G:0,W:0,B:0},modal=null,responder='enemy'}={}){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(modal);M.enemy.hand=[...hand];M.enemy.battlefield=[];M.enemy.powerCounters=[];M.enemy.summonedOn=[];M.enemy.crystals={...crystals};M.player.hand=[];M.stack=[{id:'target',cardId:'spark',owner:'player'}];M.responseWindow={stackId:'target',responder};M.pendingResolution=false;M.active='enemy-response';M.phase='Prioridad rival';M.log=[];return M}
  function snap(H,M){const m=H.getModal();return JSON.stringify({hand:M.enemy.hand,crystals:M.enemy.crystals,responseWindow:M.responseWindow,pendingResolution:M.pendingResolution,active:M.active,phase:M.phase,modal:m?{type:m.type,stage:m.stage,owner:m.owner,idx:m.idx,cardId:m.cardId,dc:m.dc,roll:m.roll,reactive:m.reactive,targetStackId:m.targetStackId,ai:m.ai,payment:m.payment}:null,log:M.log.map(x=>[x.t,x.m])})}
  const runtimeCases=[
    {name:'counter preferred',options:{hand:['mist','counter','spark']}},
    {name:'first payable non-counter',options:{hand:['spark','mist'],crystals:{U:2,R:1,G:0,W:0,B:0}}},
    {name:'no payable response',options:{hand:['counter','mist','spark'],crystals:{U:0,R:0,G:0,W:0,B:0}}},
    {name:'existing modal blocks response',options:{hand:['counter'],modal:{type:'sentinel'}}}
  ];
  for(const x of runtimeCases){const OM=setup(o,x.options),NM=setup(n,x.options);o.enemyRespondV070();n.enemyRespondV070();const a=snap(o,OM),b=snap(n,NM);assert(a===b,`${x.name} mismatch :: ${a} / ${b}`);compared++}

  o.setModal(null);n.setModal(null);
  const arena=N.window.SIZA.runArenaCriticalV071();
  for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);
  assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS priority response old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared priority response selector',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
