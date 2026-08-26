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
 const oldFn="function enemyResolveManifestRoll(){const m=state.modal,M=state.match,E=M.enemy,c=cardById(m.cardId);let need=deficitV070(m,E),bonus=manifestBonusSourcesV1(E,c)[0];if(need===1&&bonus){applyManifestBonusSourceV1(m,E,bonus);need=Math.max(0,need-bonus.effect.amount)}const lands=E.hand.map((id,i)=>cardById(id)?.type==='Land'&&i!==m.idx?i:-1).filter(i=>i>=0);if(need<=lands.length)m.burnSelected=lands.slice(0,need);else m.aiFailure=true;save();render()}";
 const newFn="function enemyResolveManifestRoll(){const m=state.modal,M=state.match,E=M.enemy,c=cardById(m.cardId),bonus=manifestBonusSourcesV1(E,c)[0],lands=E.hand.map((id,i)=>cardById(id)?.type==='Land'&&i!==m.idx?i:-1).filter(i=>i>=0),plan=SizaManifestRules.aiManifestRollPlan(m,E,lands,bonus);if(plan.bonus)applyManifestBonusSourceV1(m,E,plan.bonus);if(plan.aiFailure)m.aiFailure=true;else m.burnSelected=plan.burnSelected;save();render()}";
 assert(live.text.includes(oldFn),'enemyResolveManifestRoll anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__AI_MANIFEST_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getModal:()=>state.modal,enemyResolveManifestRoll,cardById,manifestBonusSourcesV1};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__AI_MANIFEST_COMPARE__,n=N.window.__AI_MANIFEST_COMPARE__,R=N.window.SizaManifestRules;
 let compared=0;
 function oldPlan(modal,player,lands,bonus){let need=R.deficit(modal,player),use=need===1&&bonus?bonus:null;if(use)need=Math.max(0,need-use.effect.amount);return need<=lands.length?{bonus:use,burnSelected:lands.slice(0,need),aiFailure:false}:{bonus:use,burnSelected:null,aiFailure:true}}
 const fakeBonus={index:0,id:'prism',source:{id:'prism'},effect:{type:'manifest-bonus',amount:1,exhaustSource:true}};
 const pureCases=[
  [{dc:2,roll:2,prismBonus:0,burnSelected:[]},{mf:0},[],null],
  [{dc:3,roll:2,prismBonus:0,burnSelected:[]},{mf:0},[],fakeBonus],
  [{dc:4,roll:2,prismBonus:0,burnSelected:[]},{mf:0},[1,2],fakeBonus],
  [{dc:5,roll:1,prismBonus:0,burnSelected:[9]},{mf:0},[1],null],
  [{dc:3,roll:1,prismBonus:1,burnSelected:[]},{mf:0},[],fakeBonus]
 ];
 for(const [m,p,lands,b] of pureCases){const a=oldPlan(m,p,lands,b),z=R.aiManifestRollPlan(m,p,lands,b);assert(JSON.stringify(a)===JSON.stringify(z),`pure plan mismatch ${JSON.stringify([m,p,lands])} :: ${JSON.stringify(a)} / ${JSON.stringify(z)}`);compared++}
 function setup(H,x){const M=H.createMatch(false,'prepare');H.setMatch(M);M.active='enemy';const E=M.enemy;E.mf=x.mf??0;E.hand=[...(x.hand||['mist'])];E.artifacts=[...(x.artifacts||[])];E.artifactExhausted=[...(x.artifactExhausted||[])];const modal={type:'manifest',stage:'roll',owner:'enemy',idx:x.idx??0,cardId:x.cardId||'mist',dc:x.dc,roll:x.roll,prismBonus:x.prismBonus||0,burnSelected:[...(x.burnSelected||[])],ai:true};if(x.aiFailure)modal.aiFailure=true;H.setModal(modal);return{M,E,modal}}
 function snap(H,E){const m=H.getModal();return JSON.stringify({prismBonus:m.prismBonus,burnSelected:m.burnSelected,aiFailure:m.aiFailure??null,artifactExhausted:E.artifactExhausted})}
 const runtimeCases=[
  {name:'already successful',dc:2,roll:2,hand:['mist']},
  {name:'uses Prism at exact deficit one',dc:3,roll:2,hand:['mist'],artifacts:['prism']},
  {name:'uses one Land without Prism',dc:3,roll:2,hand:['mist','dock']},
  {name:'does not use Prism at deficit two',dc:4,roll:2,hand:['mist','dock','cinder'],artifacts:['prism']},
  {name:'failure preserves previous Burn and sets aiFailure',dc:5,roll:1,hand:['mist','dock'],burnSelected:[9]},
  {name:'success does not clear historical aiFailure',dc:2,roll:2,hand:['mist'],aiFailure:true,burnSelected:[9]},
  {name:'visible bonus preserves historical failed apply semantics',dc:3,roll:1,prismBonus:1,hand:['mist'],artifacts:['prism']}
 ];
 for(const x of runtimeCases){const A=setup(o,x),B=setup(n,x);o.enemyResolveManifestRoll();n.enemyResolveManifestRoll();const a=snap(o,A.E),b=snap(n,B.E);assert(a===b,`${x.name} mismatch :: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS rival Manafestation roll old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared rival Manafestation roll plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
