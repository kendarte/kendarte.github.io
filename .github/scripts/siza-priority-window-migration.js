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
 const oldFn="function openPriorityV070(obj){const M=state.match,responder=obj.owner==='player'?'enemy':'player';M.responseWindow={stackId:obj.id,responder};M.active=responder==='player'?'response':'enemy-response';M.phase=responder==='player'?'Tu prioridad':'Prioridad rival';addLog('Prioridad',`${responder==='player'?'Puedes responder':'El rival puede responder'} a ${cardById(obj.cardId).name}.`);if(responder==='enemy')setTimeout(enemyRespondV070,420)}";
 const newFn="function openPriorityV070(obj){const M=state.match,plan=SizaCardEffects.priorityWindowPlan(obj.owner),responder=plan.responder;M.responseWindow={stackId:obj.id,responder};M.active=plan.active;M.phase=plan.phase;addLog('Prioridad',`${responder==='player'?'Puedes responder':'El rival puede responder'} a ${cardById(obj.cardId).name}.`);if(responder==='enemy')setTimeout(enemyRespondV070,420)}";
 assert(live.text.includes(oldFn),'openPriorityV070 anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__PRIORITY_WINDOW_COMPARE__={createMatch,setMatch:m=>state.match=m,openPriorityV070};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__PRIORITY_WINDOW_COMPARE__,n=N.window.__PRIORITY_WINDOW_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 for(const owner of ['player','enemy','unexpected']){
   const responder=owner==='player'?'enemy':'player',old={responder,active:responder==='player'?'response':'enemy-response',phase:responder==='player'?'Tu prioridad':'Prioridad rival'},next=E.priorityWindowPlan(owner);
   assert(JSON.stringify(old)===JSON.stringify(next),`priority plan mismatch ${owner} :: ${JSON.stringify(old)} / ${JSON.stringify(next)}`);compared++;
 }
 function fresh(H){const M=H.createMatch(false,'prepare');H.setMatch(M);M.responseWindow=null;M.active='player';M.phase='Main';M.log=[];return M}
 function snap(M){return JSON.stringify({responseWindow:M.responseWindow,active:M.active,phase:M.phase,log:M.log.map(x=>[x.t,x.m])})}
 const runtimeCases=[
   {owner:'player',id:'p',cardId:'mist'},
   {owner:'enemy',id:'e',cardId:'spark'},
   {owner:'unexpected',id:'u',cardId:'counter'}
 ];
 for(const obj of runtimeCases){const OM=fresh(o),NM=fresh(n);o.openPriorityV070({...obj});n.openPriorityV070({...obj});const a=snap(OM),b=snap(NM);assert(a===b,`open priority mismatch ${obj.owner} :: ${a} / ${b}`);compared++}
 const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS priority window old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared priority window plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
