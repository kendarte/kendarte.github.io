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
  const oldBranch="if(effect.type==='counter-stack-target'){let i=M.stack.findIndex(x=>x.id===s.targetStackId);if(i<0)i=M.stack.length-1;if(i>=0){const t=M.stack.splice(i,1)[0];M[t.owner].graveyard.push(t.cardId);addLog('Negación',c.name+' anula '+cardById(t.cardId).name+'.')}return{terminal:true}}";
  const newBranch="if(effect.type==='counter-stack-target'){const i=SizaCardEffects.stackTargetIndex(M.stack,s.targetStackId);if(i>=0){const t=M.stack.splice(i,1)[0];M[t.owner].graveyard.push(t.cardId);addLog('Negación',c.name+' anula '+cardById(t.cardId).name+'.')}return{terminal:true}}";
  assert(live.text.includes(oldBranch),'counter stack target anchor changed');
  const candidate=live.text.replace(oldBranch,newBranch),marker='window.SIZA={';
  const probe=`window.__STACK_TARGET_COMPARE__={createMatch,setMatch:m=>state.match=m,resolveTopStack};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__STACK_TARGET_COMPARE__,n=N.window.__STACK_TARGET_COMPARE__,E=N.window.SizaCardEffects;
  let compared=0;
  const indexCases=[
    {stack:[{id:'a'},{id:'b'},{id:'c'}],target:'b'},
    {stack:[{id:'a'},{id:'b'}],target:'missing'},
    {stack:[{id:'a'},{id:'b'}],target:undefined},
    {stack:[{cardId:'x'},{id:'b'}],target:undefined},
    {stack:[{id:null},{id:'b'}],target:null},
    {stack:[],target:'missing'}
  ];
  for(const x of indexCases){let old=x.stack.findIndex(entry=>entry.id===x.target);if(old<0)old=x.stack.length-1;const fresh=x.stack.map(entry=>({...entry})),next=E.stackTargetIndex(fresh,x.target);assert(old===next,`stack index mismatch ${JSON.stringify(x)} :: old=${old} new=${next}`);compared++}
  function fresh(H){const M=H.createMatch(false,'prepare');H.setMatch(M);M.player.hand=[];M.enemy.hand=[];M.player.graveyard=[];M.enemy.graveyard=[];M.log=[];return M}
  function snap(M){return JSON.stringify({stack:M.stack,playerGraveyard:M.player.graveyard,enemyGraveyard:M.enemy.graveyard,log:M.log.map(x=>[x.t,x.m])})}
  {
    const OM=fresh(o),NM=fresh(n);for(const M of[OM,NM])M.stack=[{id:'target',cardId:'spark',owner:'enemy'},{id:'other',cardId:'mist',owner:'enemy'},{id:'counter',cardId:'counter',owner:'player',targetStackId:'target'}];o.resolveTopStack();n.resolveTopStack();assert(snap(OM)===snap(NM),`explicit counter target mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  {
    const OM=fresh(o),NM=fresh(n);for(const M of[OM,NM])M.stack=[{id:'lower',cardId:'mist',owner:'enemy'},{id:'top',cardId:'spark',owner:'enemy'},{id:'counter',cardId:'counter',owner:'player',targetStackId:'missing'}];o.resolveTopStack();n.resolveTopStack();assert(snap(OM)===snap(NM),`fallback counter target mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS stack target old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared stack target query',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
