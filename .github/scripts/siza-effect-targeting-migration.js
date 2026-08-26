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
  const oldTargets="function bounceTargetsForEffectV1(M,s,entryIndex){const targets=[];for(const owner of ['player','enemy']){M[owner].battlefield.forEach((id,j)=>{if(!(owner===s.owner&&j===entryIndex))targets.push({owner,zone:'battlefield',index:j,id})});M[owner].artifacts.forEach((id,j)=>targets.push({owner,zone:'artifacts',index:j,id}));M[owner].equipment.forEach((e,j)=>targets.push({owner,zone:'equipment',index:j,id:e.id}))}return targets}";
  const oldSide="function effectSideV1(target,P,O,defaultTarget='self'){const t=target||defaultTarget;return t==='opponent'?O:P}";
  const newTargets="function bounceTargetsForEffectV1(M,s,entryIndex){return SizaCardEffects.otherPermanentTargets(M,s.owner,entryIndex)}";
  const newSide="function effectSideV1(target,P,O,defaultTarget='self'){return SizaCardEffects.effectSide(target,P,O,defaultTarget)}";
  assert(live.text.includes(oldTargets)&&live.text.includes(oldSide),'Effect targeting anchors changed');
  const candidate=live.text.replace(oldTargets,newTargets).replace(oldSide,newSide),marker='window.SIZA={';
  const probe=`window.__EFFECT_TARGET_COMPARE__={createMatch,setMatch:m=>state.match=m,bounceTargetsForEffectV1,effectSideV1,resolveTopStack};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__EFFECT_TARGET_COMPARE__,n=N.window.__EFFECT_TARGET_COMPARE__;
  let compared=0;
  for(const [target,def] of [[null,'self'],['self','opponent'],['opponent','self'],['unexpected','opponent']]){
    const OP={tag:'P'},OO={tag:'O'},NP={tag:'P'},NO={tag:'O'};
    const a=o.effectSideV1(target,OP,OO,def).tag,b=n.effectSideV1(target,NP,NO,def).tag;
    assert(a===b,`effectSide mismatch ${target}/${def}: ${a}/${b}`);compared++;
  }
  const targetCases=[
    {owner:'player',entryIndex:1},
    {owner:'enemy',entryIndex:0},
    {owner:'player',entryIndex:null}
  ];
  function targetMatch(H){const M=H.createMatch(false,'immediate');M.player.battlefield=['servitor','leviathan'];M.player.artifacts=['prism'];M.player.equipment=[{id:'tideblade',target:0}];M.enemy.battlefield=['ignimite','watcher'];M.enemy.artifacts=['prism'];M.enemy.equipment=[{id:'tideblade',target:1}];return M}
  for(const c of targetCases){const OM=targetMatch(o),NM=targetMatch(n),a=o.bounceTargetsForEffectV1(OM,{owner:c.owner},c.entryIndex),b=n.bounceTargetsForEffectV1(NM,{owner:c.owner},c.entryIndex);assert(JSON.stringify(a)===JSON.stringify(b),`targets mismatch ${JSON.stringify(c)} :: ${JSON.stringify(a)} / ${JSON.stringify(b)}`);compared++}
  function snap(M){return JSON.stringify({player:{battlefield:M.player.battlefield,artifacts:M.player.artifacts,equipment:M.player.equipment,hand:M.player.hand,graveyard:M.player.graveyard},enemy:{battlefield:M.enemy.battlefield,artifacts:M.enemy.artifacts,equipment:M.enemy.equipment,hand:M.enemy.hand,graveyard:M.enemy.graveyard},pendingChoice:M.pendingChoice,log:M.log.map(x=>[x.t,x.m])})}
  {
    const OM=o.createMatch(false,'immediate'),NM=n.createMatch(false,'immediate');for(const M of[OM,NM]){M.player.battlefield=[];M.player.powerCounters=[];M.player.summonedOn=[];M.player.artifacts=[];M.player.equipment=[];M.enemy.battlefield=['ignimite'];M.enemy.powerCounters=[0];M.enemy.summonedOn=[0];M.enemy.artifacts=['prism'];M.enemy.equipment=[{id:'tideblade',target:0}];M.stack=[{id:'s1',cardId:'leviathan',owner:'player'}];M.log=[]}o.setMatch(OM);n.setMatch(NM);o.resolveTopStack();n.resolveTopStack();assert(snap(OM)===snap(NM),`player Leviathan mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  {
    const OM=o.createMatch(false,'immediate'),NM=n.createMatch(false,'immediate');for(const M of[OM,NM]){M.player.battlefield=['servitor'];M.player.powerCounters=[0];M.player.summonedOn=[0];M.player.artifacts=['prism'];M.player.equipment=[];M.enemy.battlefield=[];M.enemy.powerCounters=[];M.enemy.summonedOn=[];M.enemy.artifacts=[];M.enemy.equipment=[];M.stack=[{id:'s2',cardId:'leviathan',owner:'enemy'}];M.log=[]}o.setMatch(OM);n.setMatch(NM);o.resolveTopStack();n.resolveTopStack();assert(snap(OM)===snap(NM),`enemy Leviathan mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS effect targeting old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared effect targeting queries',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
