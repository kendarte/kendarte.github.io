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
 const oldPart="const attackers=E.battlefield.map((_,i)=>canAttackV070(E,i)?{index:i,id:E.battlefield[i]}:null).filter(Boolean);";
 const newPart="const attackers=SizaEntryRules.availableAttackers(E,M.rules.entryMode||'prepare',cardById,spellCostV070).map(i=>({index:i,id:E.battlefield[i]}));";
 assert(live.text.includes(oldPart),'enemyAfterMain attacker anchor changed');
 const candidate=live.text.replace(oldPart,newPart),marker='window.SIZA={';
 const probe=`window.__ENEMY_ATTACKERS_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,enemyAfterMain};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__ENEMY_ATTACKERS_COMPARE__,n=N.window.__ENEMY_ATTACKERS_COMPARE__;
 let compared=0;
 function setup(H,x){const M=H.createMatch(false,x.mode||'prepare');H.setMatch(M);H.setModal(null);M.rules.entryMode=x.mode||'prepare';M.active='enemy';M.phase='Main rival';M.combat=null;M.over=false;M.winner=null;M.log=[];M.player.life=x.playerLife??20;const E=M.enemy;E.battlefield=[...(x.battlefield||[])];E.powerCounters=E.battlefield.map(()=>0);E.ownTurn=x.ownTurn??2;E.summonedOn=x.summonedOn?[...x.summonedOn]:E.battlefield.map(()=>0);E.exhausted=[...(x.exhausted||[])];E.combatUsed=false;return M}
 function snap(dom,M){return JSON.stringify({active:M.active,phase:M.phase,combat:M.combat,over:M.over,winner:M.winner,playerLife:M.player.life,enemyExhausted:M.enemy.exhausted,log:M.log.map(x=>[x.t,x.m]),scheduled:dom.window.__scheduled.slice()})}
 const cases=[
  {name:'empty',battlefield:[]},
  {name:'two legal',battlefield:['servitor','watcher'],summonedOn:[0,0],ownTurn:2},
  {name:'exhausted excluded',battlefield:['servitor','watcher'],summonedOn:[0,0],ownTurn:2,exhausted:[0]},
  {name:'fresh prepare excluded',mode:'prepare',battlefield:['servitor'],summonedOn:[2],ownTurn:2},
  {name:'fresh immediate included',mode:'immediate',battlefield:['servitor'],summonedOn:[2],ownTurn:2},
  {name:'attack trigger lethal',battlefield:['smuggler'],summonedOn:[0],ownTurn:2,playerLife:1}
 ];
 for(const x of cases){O.window.__scheduled.length=0;N.window.__scheduled.length=0;const A=setup(o,x),B=setup(n,x);o.enemyAfterMain();n.enemyAfterMain();const a=snap(O,A),b=snap(N,B);assert(a===b,`${x.name} mismatch :: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS rival attacker selection old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Reuse shared rival attacker selection',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
