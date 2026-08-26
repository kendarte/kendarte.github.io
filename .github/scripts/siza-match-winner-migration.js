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
 const oldFn="function checkWin(){const M=state.match;if(M.player.life<=0||M.enemy.life<=0){M.over=true;M.winner=M.player.life>0?'player':'enemy';addLog('Match',`${M.winner==='player'?'Victoria':'Derrota'}.`);if(M.adventure&&M.winner==='player'){state.adventure.flags.smugglersResolved=true;state.adventure.advance=Math.min(5,state.adventure.advance+2);journal('Siza Encounter','Derrotaste al Magistócrata contrabandista. La escalera inferior quedó abierta.');state.adventure.currentEvent=null;chooseAdventureEvent()}}}";
 const newFn="function checkWin(){const M=state.match,winner=SizaCardEffects.matchWinner(M.player.life,M.enemy.life);if(winner){M.over=true;M.winner=winner;addLog('Match',`${M.winner==='player'?'Victoria':'Derrota'}.`);if(M.adventure&&M.winner==='player'){state.adventure.flags.smugglersResolved=true;state.adventure.advance=Math.min(5,state.adventure.advance+2);journal('Siza Encounter','Derrotaste al Magistócrata contrabandista. La escalera inferior quedó abierta.');state.adventure.currentEvent=null;chooseAdventureEvent()}}}";
 assert(live.text.includes(oldFn),'checkWin anchor changed');
 const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
 const probe=`window.__MATCH_WINNER_COMPARE__={createMatch,setMatch:m=>state.match=m,setModal:v=>state.modal=v,checkWin};\n`;
 assert(live.text.includes(marker),'SIZA export marker missing');
 const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
 const o=O.window.__MATCH_WINNER_COMPARE__,n=N.window.__MATCH_WINNER_COMPARE__,E=N.window.SizaCardEffects;
 let compared=0;
 const cases=[[20,20,null],[20,1,null],[20,0,'player'],[1,-2,'player'],[0,20,'enemy'],[-2,1,'enemy'],[0,0,'enemy'],[-1,-1,'enemy']];
 for(const [p,e,expected] of cases){const old=p<=0||e<=0?(p>0?'player':'enemy'):null,next=E.matchWinner(p,e);assert(old===next&&next===expected,`winner mismatch ${p}/${e}: ${old}/${next}`);compared++}
 function setup(H,p,e){const M=H.createMatch(false,'prepare');H.setMatch(M);H.setModal(null);M.adventure=false;M.player.life=p;M.enemy.life=e;M.over=false;M.winner=null;M.log=[];return M}
 function snap(M){return JSON.stringify({playerLife:M.player.life,enemyLife:M.enemy.life,over:M.over,winner:M.winner,log:M.log.map(x=>[x.t,x.m])})}
 for(const [p,e] of [[20,20],[20,0],[0,20],[0,0],[-2,3],[3,-2]]){const A=setup(o,p,e),B=setup(n,p,e);o.checkWin();n.checkWin();const a=snap(A),b=snap(B);assert(a===b,`runtime winner mismatch ${p}/${e}: ${a} / ${b}`);compared++}
 o.setModal(null);n.setModal(null);const arena=N.window.SIZA.runArenaCriticalV071();for(const r of arena.results.filter(x=>!x.pass))console.error(`ARENA FAIL ${r.name}${r.error?` :: ${r.error}`:''}`);assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
 console.log(`PASS match winner old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
 const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
 const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared match winner selector',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
