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
 const oldFn="function passPriorityV070(owner){const M=state.match;if(M?.responseWindow?.responder!==owner)return;M.responseWindow=null;M.pendingResolution=true;M.active='resolving';M.phase='Stack listo';save();render()}";
 const newFn="function passPriorityV070(owner){const M=state.match,plan=SizaCardEffects.priorityPassPlan(M?.responseWindow,owner);if(!plan)return;M.responseWindow=plan.responseWindow;M.pendingResolution=plan.pendingResolution;M.active=plan.active;M.phase=plan.phase;save();render()}";
 assert(live.text.includes(oldFn),'passPriorityV070 anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__PRIORITY_PASS_COMPARE__={createMatch,setMatch:m=>state.match=m,getMatch:()=>state.match,setModal:v=>state.modal=v,passPriorityV070};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__PRIORITY_PASS_COMPARE__,n=N.window.__PRIORITY_PASS_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 const patch={responseWindow:null,pendingResolution:true,active:'resolving',phase:'Stack listo'};
 const planCases=[
   [{responder:'player'},'player',patch],
   [{responder:'enemy'},'enemy',patch],
   [{responder:'player'},'enemy',null],
   [null,'player',null],
   [undefined,'enemy',null]
 ];
 for(const [window,owner,expected] of planCases){const actual=E.priorityPassPlan(window,owner);assert(JSON.stringify(actual)===JSON.stringify(expected),`priority pass plan mismatch ${owner} :: ${JSON.stringify(actual)} / ${JSON.stringify(expected)}`);compared++}
 function setup(H,{responder='player',owner='player',responseWindow={stackId:'x',responder}}={}){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.responseWindow=responseWindow;M.pendingResolution=false;M.active=responder==='player'?'response':'enemy-response';M.phase=responder==='player'?'Tu prioridad':'Prioridad rival';M.log=[];return{M,owner}}
 function snap(M){return JSON.stringify({responseWindow:M.responseWindow,pendingResolution:M.pendingResolution,active:M.active,phase:M.phase,stack:M.stack,log:M.log.map(x=>[x.t,x.m])})}
 const runtimeCases=[
   {name:'player passes own window',options:{responder:'player',owner:'player'}},
   {name:'enemy passes own window',options:{responder:'enemy',owner:'enemy'}},
   {name:'wrong owner is no-op',options:{responder:'player',owner:'enemy'}},
   {name:'missing response window is no-op',options:{responder:'player',owner:'player',responseWindow:null}}
 ];
 for(const x of runtimeCases){const A=setup(o,x.options),B=setup(n,x.options);o.passPriorityV070(A.owner);n.passPriorityV070(B.owner);const a=snap(A.M),b=snap(B.M);assert(a===b,`${x.name} mismatch :: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);
 const arena=N.window.SIZA.runArenaCriticalV071();
 for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);
 assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS priority pass old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared priority pass plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
