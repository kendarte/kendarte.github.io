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
  const oldFn="function resolveTopStack(){const M=state.match,s=M.stack.pop();if(!s)return;const P=M[s.owner],O=s.owner==='player'?M.enemy:M.player,c=cardById(s.cardId);if(c.type==='Creature'){const i=addCreatureV070(P,c.id);addLog('Materialización',c.name+' entra en Invocaciones.');applyCardEffectsV1(c,'enter',s,P,O,i);return}if(c.type==='Artifact'){if(isEquipmentCardV1(c))P.equipment.push({id:c.id,target:null});else P.artifacts.push(c.id);addLog('Permanente',c.name+' entra en su zona propia.');applyCardEffectsV1(c,'enter',s,P,O,null);return}const result=applyCardEffectsV1(c,'resolve',s,P,O,null);P.graveyard.push(c.id);if(result.terminal)return;checkWin()}";
  const newFn="function resolveTopStack(){const M=state.match,s=M.stack.pop();if(!s)return;const P=M[s.owner],O=s.owner==='player'?M.enemy:M.player,c=cardById(s.cardId),kind=SizaCardSchema.resolutionKind(c);if(kind==='creature'){const i=addCreatureV070(P,c.id);addLog('Materialización',c.name+' entra en Invocaciones.');applyCardEffectsV1(c,'enter',s,P,O,i);return}if(kind==='artifact'||kind==='equipment'){if(kind==='equipment')P.equipment.push({id:c.id,target:null});else P.artifacts.push(c.id);addLog('Permanente',c.name+' entra en su zona propia.');applyCardEffectsV1(c,'enter',s,P,O,null);return}const result=applyCardEffectsV1(c,'resolve',s,P,O,null);P.graveyard.push(c.id);if(result.terminal)return;checkWin()}";
  assert(live.text.includes(oldFn),'resolveTopStack anchor changed');
  const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
  const probe=`window.__RESOLUTION_KIND_COMPARE__={createMatch,setMatch:m=>state.match=m,resolveTopStack,cardById,TEST_CARD_DB_V1};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__RESOLUTION_KIND_COMPARE__,n=N.window.__RESOLUTION_KIND_COMPARE__,S=N.window.SizaCardSchema;
  let compared=0;

  const classifyCases=[
    {card:{type:'Creature'},old:'creature'},
    {card:{type:'Artifact'},old:'artifact'},
    {card:{type:'Artifact',equipCost:1},old:'equipment'},
    {card:{type:'Artifact',effects:[{event:'equipped',type:'modify-power',amount:2}]},old:'equipment'},
    {card:{type:'Instant'},old:'spell'},
    {card:{type:'Land'},old:'spell'},
    {card:{type:'artifact',equipCost:1},old:'spell'},
    {card:{},old:'spell'}
  ];
  for(const x of classifyCases){const got=S.resolutionKind(x.card);assert(got===x.old,`resolutionKind mismatch ${JSON.stringify(x.card)} :: ${got}/${x.old}`);compared++}

  const generated=[
    {id:'reg_resolution_artifact',name:'Generated Artifact',type:'Artifact',cost:1,difficulty:1,pips:{},text:'Artifact.',effects:[]},
    {id:'reg_resolution_equipment',name:'Generated Equipment',type:'Artifact',cost:1,difficulty:1,pips:{},equipCost:1,text:'Equipment.',effects:[{event:'equipped',type:'modify-power',amount:3}]},
    {id:'reg_resolution_creature',name:'Generated Creature',type:'Creature',cost:1,difficulty:1,pips:{},power:2,toughness:3,text:'Creature.',effects:[]},
    {id:'reg_resolution_spell',name:'Generated Spell',type:'Instant',cost:1,difficulty:1,pips:{},text:'Draw.',effects:[{event:'resolve',type:'draw',target:'self',amount:1}]}
  ];
  o.TEST_CARD_DB_V1.push(...generated.map(x=>({...x,effects:x.effects.map(e=>({...e}))})));
  n.TEST_CARD_DB_V1.push(...generated.map(x=>({...x,effects:x.effects.map(e=>({...e}))})));

  function fresh(H){const M=H.createMatch(false,'prepare');H.setMatch(M);for(const P of[M.player,M.enemy]){P.hand=[];P.library=[];P.graveyard=[];P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.artifacts=[];P.equipment=[];P.exile=[]}M.player.life=20;M.enemy.life=20;M.pendingChoice=null;M.log=[];return M}
  function snap(M){return JSON.stringify({player:{life:M.player.life,hand:M.player.hand,graveyard:M.player.graveyard,battlefield:M.player.battlefield,powerCounters:M.player.powerCounters,summonedOn:M.player.summonedOn,artifacts:M.player.artifacts,equipment:M.player.equipment},enemy:{life:M.enemy.life,hand:M.enemy.hand,graveyard:M.enemy.graveyard,battlefield:M.enemy.battlefield,powerCounters:M.enemy.powerCounters,summonedOn:M.enemy.summonedOn,artifacts:M.enemy.artifacts,equipment:M.enemy.equipment},pendingChoice:M.pendingChoice,stack:M.stack,log:M.log.map(x=>[x.t,x.m])})}
  const runtimeCases=[
    {id:'servitor',owner:'player'},
    {id:'prism',owner:'player'},
    {id:'tideblade',owner:'player'},
    {id:'spark',owner:'player'},
    {id:'reg_resolution_artifact',owner:'enemy'},
    {id:'reg_resolution_equipment',owner:'enemy'},
    {id:'reg_resolution_creature',owner:'enemy'},
    {id:'reg_resolution_spell',owner:'player',setup:M=>{M.player.library=['mist']}}
  ];
  for(const x of runtimeCases){const OM=fresh(o),NM=fresh(n);if(x.setup){x.setup(OM);x.setup(NM)}OM.stack=[{id:'old-'+x.id,cardId:x.id,owner:x.owner}];NM.stack=[{id:'old-'+x.id,cardId:x.id,owner:x.owner}];o.resolveTopStack();n.resolveTopStack();const a=snap(OM),b=snap(NM);assert(a===b,`resolve mismatch ${x.id}/${x.owner} :: ${a} / ${b}`);compared++}

  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS resolution kind old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared resolution classification',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
