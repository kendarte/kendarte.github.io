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
 const oldFn="function completeStackV070(){const M=state.match;resolveStackAll();if(M.over){save();return render()}if(M.pendingChoice){M.active='choice';save();return render()}const owner=M.stackReturnOwner||'player';M.stackReturnOwner=null;if(owner==='enemy'){M.active='enemy';M.phase='Main rival';save();render();setTimeout(enemyChoosePlay,420)}else{M.active='player';M.phase='Main';save();render()}}";
 const newFn="function completeStackV070(){const M=state.match;resolveStackAll();const plan=SizaCardEffects.stackCompletionPlan(M);if(plan.kind==='over'){save();return render()}if(plan.kind==='choice'){M.active=plan.active;save();return render()}M.stackReturnOwner=plan.stackReturnOwner;M.active=plan.active;M.phase=plan.phase;save();render();if(plan.scheduleEnemy)setTimeout(enemyChoosePlay,420)}";
 assert(live.text.includes(oldFn),'completeStackV070 anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__STACK_COMPLETION_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,completeStackV070};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__STACK_COMPLETION_COMPARE__,n=N.window.__STACK_COMPLETION_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 const planCases=[
   {over:true,pendingChoice:{type:'discard'},stackReturnOwner:'enemy'},
   {over:false,pendingChoice:{type:'discard'},stackReturnOwner:'enemy'},
   {over:false,pendingChoice:null,stackReturnOwner:'enemy'},
   {over:false,pendingChoice:null,stackReturnOwner:'player'},
   {over:false,pendingChoice:null,stackReturnOwner:null},
   {over:false,pendingChoice:null,stackReturnOwner:'unexpected'}
 ];
 function oldPlan(M){if(M.over)return{kind:'over'};if(M.pendingChoice)return{kind:'choice',active:'choice'};const owner=M.stackReturnOwner||'player',enemy=owner==='enemy';return{kind:'return',stackReturnOwner:null,active:enemy?'enemy':'player',phase:enemy?'Main rival':'Main',scheduleEnemy:enemy}}
 for(const x of planCases){const a=oldPlan(x),b=E.stackCompletionPlan(x);assert(JSON.stringify(a)===JSON.stringify(b),`stack completion plan mismatch ${JSON.stringify(x)} :: ${JSON.stringify(a)} / ${JSON.stringify(b)}`);compared++}
 function setup(H,x){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.stack=[];M.over=!!x.over;M.pendingChoice=x.pendingChoice?{...x.pendingChoice}:null;M.stackReturnOwner=x.stackReturnOwner;M.active='resolving';M.phase='Stack listo';M.log=[];return M}
 function snap(dom,M){return JSON.stringify({over:M.over,pendingChoice:M.pendingChoice,stackReturnOwner:M.stackReturnOwner,active:M.active,phase:M.phase,stack:M.stack,scheduled:dom.window.__scheduled.slice()})}
 for(const x of planCases){O.window.__scheduled.length=0;N.window.__scheduled.length=0;const A=setup(o,x),B=setup(n,x);o.completeStackV070();n.completeStackV070();const a=snap(O,A),b=snap(N,B);assert(a===b,`complete stack mismatch ${JSON.stringify(x)} :: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);
 const arena=N.window.SIZA.runArenaCriticalV071();
 for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);
 assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS stack completion old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared stack completion plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
