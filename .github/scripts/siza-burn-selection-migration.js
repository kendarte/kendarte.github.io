const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');
const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`,headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'},assert=(v,m)=>{if(!v)throw new Error(m)};
async function get(path){const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});if(!r.ok)throw new Error(`${path}: GET ${r.status}`);const f=await r.json();return{sha:f.sha,text:Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8')}}
function inlineCore(html){let out=html;for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js','entry-rules.js','creature-rules.js']){const tag=`<script src="../siza-core/${name}"></script>`;assert(out.includes(tag),`Missing ${tag}`);out=out.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`)}return out}
function dom(html,label){const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[${label}]`,e.message));return new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc})}
(async()=>{
 const live=await get('siza-mobile-test/index.html');
 const oldFn="function selectBurn(i){const m=state.modal,P=state.match?.[m?.owner];if(!m||m.roll==null||m.ai||cardById(P.hand[i])?.type!=='Land'||i===m.idx)return;const need=Math.max(0,m.dc-(P.mf+m.roll+m.prismBonus)),at=m.burnSelected.indexOf(i);if(at>=0)m.burnSelected.splice(at,1);else if(m.burnSelected.length<need)m.burnSelected.push(i);render()}";
 const newFn="function selectBurn(i){const m=state.modal,P=state.match?.[m?.owner],selected=SizaManifestRules.burnSelectionPlan(m,P,i,cardById(P?.hand?.[i])?.type==='Land');if(!selected)return;m.burnSelected=selected;render()}";
 assert(live.text.includes(oldFn),'selectBurn anchor changed');const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={',probe=`window.__BURN_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,getModal:()=>state.modal,selectBurn};\n`;
 const O=dom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=dom(inlineCore(candidate).replace(marker,probe+marker),'new'),o=O.window.__BURN_COMPARE__,n=N.window.__BURN_COMPARE__,R=N.window.SizaManifestRules;O.window.setTimeout=N.window.setTimeout=()=>0;let compared=0;
 const pure=[
  [{dc:6,roll:3,prismBonus:0,burnSelected:[],idx:0,ai:false},{mf:2},1,true],
  [{dc:6,roll:3,prismBonus:0,burnSelected:[1],idx:0,ai:false},{mf:2},1,true],
  [{dc:5,roll:3,prismBonus:0,burnSelected:[],idx:0,ai:false},{mf:2},1,true],
  [{dc:6,roll:3,prismBonus:0,burnSelected:[],idx:0,ai:false},{mf:2},1,false],
  [{dc:6,roll:null,prismBonus:0,burnSelected:[],idx:0,ai:false},{mf:2},1,true],
  [{dc:6,roll:3,prismBonus:0,burnSelected:[],idx:1,ai:false},{mf:2},1,true],
  [{dc:6,roll:3,prismBonus:0,burnSelected:[],idx:0,ai:true},{mf:2},1,true]
 ];
 function oldPlan(m,p,i,isLand){if(!m||m.roll==null||m.ai||!isLand||i===m.idx)return null;const a=m.burnSelected.slice(),need=Math.max(0,m.dc-(p.mf+m.roll+m.prismBonus)),at=a.indexOf(i);if(at>=0)a.splice(at,1);else if(a.length<need)a.push(i);return a}
 for(const [m,p,i,l] of pure){const a=oldPlan(m,p,i,l),b=R.burnSelectionPlan(m,p,i,l);assert(JSON.stringify(a)===JSON.stringify(b),`plan mismatch ${JSON.stringify([m,p,i,l])}`);compared++}
 function setup(H,{selected=[],roll=3,dc=6,mf=2,idx=0,ai=false,hand=['mist','dock','cinder']}={}){const M=H.createMatch(false,'prepare');H.setMatch(M);M.player.mf=mf;M.player.hand=[...hand];H.setModal({type:'manifest',owner:'player',idx,cardId:M.player.hand[idx],dc,roll,prismBonus:0,burnSelected:[...selected],ai,stage:'roll'});return M}
 for(const x of [{},{selected:[1]},{dc:5},{hand:['mist','spark']},{idx:1,hand:['dock','cinder']},{ai:true}]){const A=setup(o,x),B=setup(n,x);o.selectBurn(1);n.selectBurn(1);assert(JSON.stringify(o.getModal().burnSelected)===JSON.stringify(n.getModal().burnSelected),'runtime burn mismatch');compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);console.log(`PASS Burn selection old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during migration');const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared Mana Burn selection plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);console.log('COMMIT '+(await put.json()).commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
