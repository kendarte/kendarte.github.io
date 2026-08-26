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
 const oldFn="function resolveStackAll(){const M=state.match;let guard=0;while(M.stack.length&&!M.pendingChoice&&!M.over&&guard++<30)resolveTopStack()}";
 const newFn="function resolveStackAll(){const M=state.match;let resolved=0;while(SizaCardEffects.shouldContinueStackResolution(M,resolved,30)){resolveTopStack();resolved++}}";
 assert(live.text.includes(oldFn),'resolveStackAll anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__STACK_LOOP_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,resolveStackAll};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__STACK_LOOP_COMPARE__,n=N.window.__STACK_LOOP_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 const predicateCases=[
  [{stack:['x'],pendingChoice:null,over:false},0,30,true],
  [{stack:['x'],pendingChoice:null,over:false},29,30,true],
  [{stack:['x'],pendingChoice:null,over:false},30,30,false],
  [{stack:[],pendingChoice:null,over:false},0,30,false],
  [{stack:['x'],pendingChoice:{type:'discard'},over:false},0,30,false],
  [{stack:['x'],pendingChoice:null,over:true},0,30,false],
  [{stack:['x'],pendingChoice:null,over:false},2,2,false]
 ];
 for(const [M,count,limit,expected] of predicateCases){const old=!!(M.stack.length&&!M.pendingChoice&&!M.over&&count<limit),next=E.shouldContinueStackResolution(M,count,limit);assert(old===next&&next===expected,`predicate mismatch ${JSON.stringify([M,count,limit])}`);compared++}
 function base(H){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);for(const P of[M.player,M.enemy]){P.hand=[];P.library=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.artifacts=[];P.equipment=[];P.exile=[]}M.player.life=20;M.enemy.life=20;M.pendingChoice=null;M.over=false;M.winner=null;M.log=[];return M}
 function setup(H,name){const M=base(H);if(name==='empty')M.stack=[];if(name==='limit'){M.stack=Array.from({length:31},(_,i)=>({id:'w'+i,cardId:'watcher',owner:'player'}))}if(name==='pre-choice'){M.pendingChoice={type:'discard'};M.stack=[{id:'w',cardId:'watcher',owner:'player'}]}if(name==='pre-over'){M.over=true;M.stack=[{id:'w',cardId:'watcher',owner:'player'}]}if(name==='observe-pause'){M.player.library=['mist'];M.stack=[{id:'below',cardId:'watcher',owner:'player'},{id:'top',cardId:'servitor',owner:'player'}]}if(name==='lethal'){M.stack=Array.from({length:11},(_,i)=>({id:'s'+i,cardId:'spark',owner:'player'}))}return M}
 function snap(M){return JSON.stringify({stack:M.stack.map(x=>[x.id,x.cardId,x.owner]),pendingChoice:M.pendingChoice,over:M.over,winner:M.winner,player:{life:M.player.life,hand:M.player.hand,library:M.player.library,graveyard:M.player.graveyard,battlefield:M.player.battlefield,powerCounters:M.player.powerCounters,summonedOn:M.player.summonedOn,artifacts:M.player.artifacts,equipment:M.player.equipment},enemy:{life:M.enemy.life,hand:M.enemy.hand,library:M.enemy.library,graveyard:M.enemy.graveyard,battlefield:M.enemy.battlefield},log:M.log.map(x=>[x.t,x.m])})}
 for(const name of ['empty','limit','pre-choice','pre-over','observe-pause','lethal']){const A=setup(o,name),B=setup(n,name);o.resolveStackAll();n.resolveStackAll();const a=snap(A),b=snap(B);assert(a===b,`${name} runtime mismatch :: ${a} / ${b}`);if(name==='limit')assert(A.stack.length===1&&A.player.battlefield.length===30,'historical 30-resolution limit changed');if(name==='observe-pause')assert(A.stack.length===1&&A.pendingChoice?.type==='observe','observe pause contract changed');if(name==='lethal')assert(A.over===true&&A.stack.length===1&&A.enemy.life===0,'lethal stop contract changed');compared++}
 o.setModal(null);n.setModal(null);
 const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS Stack loop old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared Stack continuation predicate',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
