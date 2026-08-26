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
  const oldFn="function assignBlocker(slot,i){const M=state.match,C=M?.combat;if(!C||C.owner!=='enemy'||!legalBlockersV070(M.player).includes(i))return toast('Una Invocación agotada no puede bloquear.','bad');for(const k of Object.keys(C.blockers))if(C.blockers[k]===i)delete C.blockers[k];C.blockers[String(slot)]=i;render()}";
  const newFn="function assignBlocker(slot,i){const M=state.match,C=M?.combat,plan=C?.owner==='enemy'?SizaCreatureRules.blockerAssignmentPlan(C.blockers,slot,i,legalBlockersV070(M.player)):null;if(!plan)return toast('Una Invocación agotada no puede bloquear.','bad');for(const k of plan.removeSlots)delete C.blockers[k];C.blockers[plan.slot]=plan.blockerIndex;render()}";
  assert(live.text.includes(oldFn),'assignBlocker anchor changed');
  const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
  const probe=`window.__PLAYER_BLOCKER_COMPARE__={createMatch,setMatch:m=>state.match=m,assignBlocker};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__PLAYER_BLOCKER_COMPARE__,n=N.window.__PLAYER_BLOCKER_COMPARE__;
  const scenarios=[
    {slot:0,index:0,owner:'enemy',battlefield:['servitor','ignimite','watcher'],exhausted:[],blockers:{}},
    {slot:1,index:0,owner:'enemy',battlefield:['servitor','ignimite','watcher'],exhausted:[],blockers:{'0':0}},
    {slot:2,index:1,owner:'enemy',battlefield:['servitor','ignimite','watcher'],exhausted:[],blockers:{'0':0,'1':2}},
    {slot:0,index:2,owner:'enemy',battlefield:['servitor','ignimite','watcher'],exhausted:[],blockers:{'0':1,'1':0}},
    {slot:1,index:1,owner:'enemy',battlefield:['servitor','ignimite','watcher'],exhausted:[1],blockers:{'0':0}},
    {slot:0,index:0,owner:'player',battlefield:['servitor'],exhausted:[],blockers:{}},
    {slot:3,index:9,owner:'enemy',battlefield:['servitor'],exhausted:[],blockers:{'0':0}}
  ];
  function setup(H,s){const M=H.createMatch(false,'immediate');H.setMatch(M);M.player.battlefield=[...s.battlefield];M.player.powerCounters=s.battlefield.map(()=>0);M.player.summonedOn=s.battlefield.map(()=>0);M.player.exhausted=[...s.exhausted];M.combat={owner:s.owner,attackers:[{index:0,id:'servitor'},{index:1,id:'ignimite'},{index:2,id:'watcher'}],blockers:{...s.blockers}};M.active='defense';return M}
  let compared=0;
  for(const s of scenarios){const OM=setup(o,s),NM=setup(n,s),oldRef=OM.combat.blockers,newRef=NM.combat.blockers;o.assignBlocker(s.slot,s.index);n.assignBlocker(s.slot,s.index);const a=JSON.stringify(OM.combat.blockers),b=JSON.stringify(NM.combat.blockers);assert(a===b,`blocker mismatch ${JSON.stringify(s)} :: old=${a} new=${b}`);assert(OM.combat.blockers===oldRef&&NM.combat.blockers===newRef,`blocker object identity changed ${JSON.stringify(s)}`);compared++}
  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS player blocker old/new ${compared} scenarios; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared player blocker assignment plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
