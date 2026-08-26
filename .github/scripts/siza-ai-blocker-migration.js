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
function makeDom(html,label){
  const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error(`[JSDOM ${label}]`,e.message));
  const d=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});d.window.setTimeout=()=>0;return d;
}

(async()=>{
  const live=await get('siza-mobile-test/index.html');
  const oldFn="function assignAiBlockersV600(){const M=state.match,C=M.combat,D=M.enemy,slots=C.attackers.map((a,s)=>({s,p:effectivePower(M.player,a.index)})).sort((a,b)=>b.p-a.p),bs=legalBlockersV070(D).sort((a,b)=>toughV070(D,b)-toughV070(D,a));for(let i=0;i<Math.min(slots.length,bs.length);i++)C.blockers[slots[i].s]=bs[i]}";
  const newFn="function assignAiBlockersV600(){const M=state.match,C=M.combat;Object.assign(C.blockers,SizaCreatureRules.aiBlockers(C,M.player,M.enemy,cardById,SizaCardEffects.forEvent))}";
  assert(live.text.includes(oldFn),'assignAiBlockersV600 anchor changed');
  const candidate=live.text.replace(oldFn,newFn);
  const marker='window.SIZA={';
  const probe=`window.__AI_BLOCKER_COMPARE__={createMatch,setMatch:m=>state.match=m,assignAiBlockersV600,TEST_CARD_DB_V1};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old');
  const N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__AI_BLOCKER_COMPARE__,n=N.window.__AI_BLOCKER_COMPARE__;
  const generated=[
    {id:'ab_a1',name:'A1',type:'Creature',power:1,toughness:1,effects:[]},
    {id:'ab_a2',name:'A2',type:'Creature',power:2,toughness:2,effects:[]},
    {id:'ab_a3',name:'A3',type:'Creature',power:3,toughness:3,effects:[]},
    {id:'ab_d1',name:'D1',type:'Creature',power:1,toughness:1,effects:[]},
    {id:'ab_d2',name:'D2',type:'Creature',power:1,toughness:2,effects:[]},
    {id:'ab_d4',name:'D4',type:'Creature',power:1,toughness:4,effects:[]},
    {id:'ab_eq',name:'EQ',type:'Artifact',equipCost:1,effects:[{event:'equipped',type:'modify-power',amount:3}]}
  ];
  o.TEST_CARD_DB_V1.push(...generated.map(x=>({...x})));n.TEST_CARD_DB_V1.push(...generated.map(x=>({...x})));
  const scenarios=[
    {attackers:['ab_a1','ab_a3','ab_a2'],defenders:['ab_d1','ab_d4','ab_d2'],exhausted:[],equipment:[],initial:{}},
    {attackers:['ab_a1','ab_a3','ab_a2'],defenders:['ab_d1','ab_d4','ab_d2'],exhausted:[1],equipment:[],initial:{}},
    {attackers:['ab_a1','ab_a2'],defenders:['ab_d4','ab_d2'],exhausted:[],equipment:[{id:'ab_eq',target:0}],initial:{}},
    {attackers:['ab_a3','ab_a2','ab_a1'],defenders:['ab_d4'],exhausted:[],equipment:[],initial:{}},
    {attackers:['ab_a3'],defenders:['ab_d1','ab_d4','ab_d2'],exhausted:[],equipment:[],initial:{}},
    {attackers:['ab_a2','ab_a1'],defenders:['ab_d2','ab_d1'],exhausted:[],equipment:[],initial:{'9':9}}
  ];
  function setup(H,s){
    const M=H.createMatch(false,'immediate');H.setMatch(M);const A=M.player,D=M.enemy;
    A.battlefield=[...s.attackers];A.powerCounters=s.attackers.map(()=>0);A.summonedOn=s.attackers.map(()=>0);A.equipment=s.equipment.map(x=>({...x}));A.exhausted=[];
    D.battlefield=[...s.defenders];D.powerCounters=s.defenders.map(()=>0);D.summonedOn=s.defenders.map(()=>0);D.exhausted=[...s.exhausted];D.equipment=[];
    M.combat={owner:'player',attackers:s.attackers.map((id,index)=>({index,id})),blockers:{...s.initial}};
    return M;
  }
  let compared=0;
  for(const s of scenarios){
    const OM=setup(o,s),NM=setup(n,s);o.assignAiBlockersV600();n.assignAiBlockersV600();
    const a=JSON.stringify(OM.combat.blockers),b=JSON.stringify(NM.combat.blockers);
    assert(a===b,`AI blockers mismatch ${JSON.stringify(s)} :: old=${a} new=${b}`);compared++;
  }
  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS AI blocker old/new ${compared} scenarios; Arena ${arena.passed}/${arena.total}`);
  O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared AI blocker assignments',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});
  if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);
  const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
