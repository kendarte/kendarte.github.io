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
  const oldAi="else bounceV070(targets.find(x=>x.owner==='player')||targets[0])";
  const newAi="else bounceV070(SizaCardEffects.preferredPermanentTarget(targets,'player'))";
  const oldBounce="function bounceV070(t){const P=state.match[t.owner],zone=t.zone||'battlefield';let id=null;if(zone==='battlefield')id=removeBattlefieldAt(P,t.index,'hand');else if(zone==='artifacts')id=P.artifacts.splice(t.index,1)[0];else if(zone==='equipment')id=P.equipment.splice(t.index,1)[0]?.id;if(!id)return;if(zone!=='battlefield')P.hand.push(id);addLog('Leviatán',`${cardById(id).name} vuelve a la mano desde ${zone==='equipment'?'Equipo':zone==='artifacts'?'Reliquias':'Invocaciones'}.`)}";
  const newBounce="function bounceV070(t){const plan=SizaCardEffects.bouncePlan(t),P=state.match[plan.owner];let id=null;if(plan.zone==='battlefield')id=removeBattlefieldAt(P,plan.index,plan.destination);else if(plan.zone==='artifacts')id=P.artifacts.splice(plan.index,1)[0];else if(plan.zone==='equipment')id=P.equipment.splice(plan.index,1)[0]?.id;if(!id)return;if(plan.zone!=='battlefield')P.hand.push(id);addLog('Leviatán',`${cardById(id).name} vuelve a la mano desde ${plan.zoneLabel}.`)}";
  assert(live.text.includes(oldAi),'AI bounce preference anchor changed');
  assert(live.text.includes(oldBounce),'bounceV070 anchor changed');
  const candidate=live.text.replace(oldAi,newAi).replace(oldBounce,newBounce),marker='window.SIZA={';
  const probe=`window.__BOUNCE_PLAN_COMPARE__={createMatch,setMatch:m=>state.match=m,bounceV070,resolveTopStack};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__BOUNCE_PLAN_COMPARE__,n=N.window.__BOUNCE_PLAN_COMPARE__,E=N.window.SizaCardEffects;
  let compared=0;

  const planCases=[
    {owner:'player',index:2},
    {owner:'enemy',zone:'artifacts',index:1},
    {owner:'enemy',zone:'equipment',index:0},
    {owner:'player',zone:'unexpected',index:4}
  ];
  for(const t of planCases){const zone=t.zone||'battlefield',old={owner:t.owner,zone,index:t.index,destination:'hand',zoneLabel:zone==='equipment'?'Equipo':zone==='artifacts'?'Reliquias':'Invocaciones'},next=E.bouncePlan({...t});assert(JSON.stringify(old)===JSON.stringify(next),`bounce plan mismatch ${JSON.stringify(t)} :: ${JSON.stringify(old)} / ${JSON.stringify(next)}`);compared++}

  const targetCases=[
    [{owner:'enemy',id:'a'},{owner:'player',id:'b'},{owner:'player',id:'c'}],
    [{owner:'enemy',id:'a'},{owner:'enemy',id:'b'}],
    []
  ];
  for(const targets of targetCases){const old=targets.find(x=>x.owner==='player')||targets[0]||null,next=E.preferredPermanentTarget(targets,'player');assert(JSON.stringify(old)===JSON.stringify(next),`preferred target mismatch ${JSON.stringify(targets)}`);compared++}

  function fresh(H){const M=H.createMatch(false,'prepare');H.setMatch(M);M.player.hand=[];M.enemy.hand=[];M.player.graveyard=[];M.enemy.graveyard=[];M.player.artifacts=[];M.enemy.artifacts=[];M.player.equipment=[];M.enemy.equipment=[];M.player.battlefield=[];M.enemy.battlefield=[];M.player.powerCounters=[];M.enemy.powerCounters=[];M.player.summonedOn=[];M.enemy.summonedOn=[];M.log=[];M.ui={hand:-1,creature:-1,attackMode:false,attackers:[],fieldFocus:null};return M}
  function snap(M){return JSON.stringify({player:{battlefield:M.player.battlefield,powerCounters:M.player.powerCounters,summonedOn:M.player.summonedOn,artifacts:M.player.artifacts,equipment:M.player.equipment,hand:M.player.hand},enemy:{battlefield:M.enemy.battlefield,powerCounters:M.enemy.powerCounters,summonedOn:M.enemy.summonedOn,artifacts:M.enemy.artifacts,equipment:M.enemy.equipment,hand:M.enemy.hand},ui:M.ui,log:M.log.map(x=>[x.t,x.m])})}
  const runtimeCases=[
    {name:'battlefield',setup:M=>{M.player.battlefield=['servitor','ignimite','watcher'];M.player.powerCounters=[0,2,1];M.player.summonedOn=[0,0,0];M.player.exhausted=[1,2];M.player.equipment=[{id:'tideblade',target:2}];M.ui.attackers=[0,1,2];M.ui.creature=2;M.ui.fieldFocus={owner:'player',index:2}},target:{owner:'player',zone:'battlefield',index:1,id:'ignimite'}},
    {name:'artifacts',setup:M=>{M.enemy.artifacts=['prism','prism']},target:{owner:'enemy',zone:'artifacts',index:0,id:'prism'}},
    {name:'equipment',setup:M=>{M.enemy.equipment=[{id:'tideblade',target:0},{id:'tideblade',target:null}]},target:{owner:'enemy',zone:'equipment',index:1,id:'tideblade'}},
    {name:'unexpected',setup:M=>{M.enemy.artifacts=['prism']},target:{owner:'enemy',zone:'unexpected',index:0,id:'prism'}}
  ];
  for(const x of runtimeCases){const OM=fresh(o),NM=fresh(n);x.setup(OM);x.setup(NM);o.bounceV070({...x.target});n.bounceV070({...x.target});assert(snap(OM)===snap(NM),`${x.name} bounce mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++}

  {
    const OM=fresh(o),NM=fresh(n);for(const M of[OM,NM]){M.player.artifacts=['prism'];M.enemy.battlefield=[];M.enemy.powerCounters=[];M.enemy.summonedOn=[];M.stack=[{id:'lev-ai',cardId:'leviathan',owner:'enemy'}]}o.resolveTopStack();n.resolveTopStack();assert(snap(OM)===snap(NM),`AI Leviathan preference mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }

  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS bounce plan old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared bounce planning queries',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
