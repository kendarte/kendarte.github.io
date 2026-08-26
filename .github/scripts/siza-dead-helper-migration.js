const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
const assert=(value,message)=>{if(!value)throw new Error(message)};

async function get(path){
  const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});
  if(!r.ok)throw new Error(`${path}: GET ${r.status}`);
  const f=await r.json();
  return{sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')};
}
function inlineCore(html){
  let out=html;
  for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js','creature-rules.js']){
    const tag=`<script src="../siza-core/${name}"></script>`;
    if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);
    out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
  }
  return out;
}
function dom(html){
  const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM dead-helper]',e.message));
  const d=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});d.window.setTimeout=()=>0;return d;
}

(async()=>{
  const live=await get('siza-mobile-test/index.html');
  const dead="function combatPowerCounterGainV1(c){return SizaCardEffects.sumAmount(c,'combat-damage','add-power-counter')}\n";
  const count=live.text.split('combatPowerCounterGainV1').length-1;
  assert(count===1,`Expected exactly one combatPowerCounterGainV1 reference, found ${count}`);
  assert(live.text.includes(dead),'Dead helper anchor changed');
  const candidate=live.text.replace(dead,'');
  assert(!candidate.includes('combatPowerCounterGainV1'),'Dead helper still referenced after cleanup');
  const D=dom(inlineCore(candidate));
  const arena=D.window.SIZA.runArenaCriticalV071();
  assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS dead helper removal; Arena ${arena.passed}/${arena.total}`);
  D.window.close();
  const latest=await get('siza-mobile-test/index.html');
  assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded cleanup');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Remove dead combat counter helper',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});
  if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);
  const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
