const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
if(!repo||!token)throw new Error('GH_REPOSITORY/GH_TOKEN required');
const api=`https://api.github.com/repos/${repo}`;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
const assert=(value,message)=>{if(!value)throw new Error(message)};

async function getLive(path){
  const r=await fetch(`${api}/contents/${path}?ref=main`,{headers});
  if(!r.ok)throw new Error(`${path}: GET ${r.status}`);
  const file=await r.json();
  return {sha:file.sha,text:Buffer.from(file.content.replace(/\n/g,''),'base64').toString('utf8')};
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
  const vc=new VirtualConsole();
  vc.on('jsdomError',error=>console.error(`[JSDOM ${label}]`,error.message));
  const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
  dom.window.setTimeout=()=>0;
  return dom;
}

(async()=>{
  const live=await getLive('siza-mobile-test/index.html');
  const original=live.text;
  const oldResolve="function resolveCombatV600(){const M=state.match,C=M.combat,A=M[C.owner],D=C.owner==='player'?M.enemy:M.player,ad=new Set,dd=new Set,ai=new Map,di=new Map;let damage=0;for(let s=0;s<C.attackers.length;s++){const a=C.attackers[s],ac=cardById(A.battlefield[a.index]),ap=effectivePower(A,a.index),at=toughV070(A,a.index),bi=C.blockers[String(s)],bc=bi==null?null:cardById(D.battlefield[bi]);if(bc){const bp=effectivePower(D,bi),bt=toughV070(D,bi);if(ap>=bt)dd.add(bi);if(bp>=at)ad.add(a.index);const ag=ap>0?combatPowerCounterGainV1(ac):0,bg=bp>0?combatPowerCounterGainV1(bc):0;if(ag)ai.set(a.index,(ai.get(a.index)||0)+ag);if(bg)di.set(bi,(di.get(bi)||0)+bg);addLog('Daño simultáneo',ac.name+' '+ap+'/'+at+' ↔ '+bc.name+' '+bp+'/'+bt+'.')}else{damage+=ap;const ag=ap>0?combatPowerCounterGainV1(ac):0;if(ag)ai.set(a.index,(ai.get(a.index)||0)+ag)}}if(damage){D.life-=damage;addLog('Daño de combate',damage+' daño al Personaje.')}for(const[i,gain]of ai)if(!ad.has(i))A.powerCounters[i]=(A.powerCounters[i]||0)+gain;for(const[i,gain]of di)if(!dd.has(i))D.powerCounters[i]=(D.powerCounters[i]||0)+gain;[...dd].sort((a,b)=>b-a).forEach(i=>removeBattlefieldAt(D,i));[...ad].sort((a,b)=>b-a).forEach(i=>removeBattlefieldAt(A,i));M.combat=null;checkWin();if(!M.over&&C.owner==='player'){M.active='player';M.phase='Main'}else if(!M.over){M.active='enemy';setTimeout(finishEnemyTurn,500)}save();render()}";
  const newResolve="function resolveCombatV600(){const M=state.match,C=M.combat,A=M[C.owner],D=C.owner==='player'?M.enemy:M.player,plan=SizaCreatureRules.combatPlan(C,A,D,cardById,SizaCardEffects.forEvent);for(const x of plan.exchanges)addLog('Daño simultáneo',x.attackerName+' '+x.attackerPower+'/'+x.attackerToughness+' ↔ '+x.defenderName+' '+x.defenderPower+'/'+x.defenderToughness+'.');if(plan.damage){D.life-=plan.damage;addLog('Daño de combate',plan.damage+' daño al Personaje.')}for(const[i,gain]of plan.attackerCounterGains)A.powerCounters[i]=(A.powerCounters[i]||0)+gain;for(const[i,gain]of plan.defenderCounterGains)D.powerCounters[i]=(D.powerCounters[i]||0)+gain;[...plan.defenderDeaths].sort((a,b)=>b-a).forEach(i=>removeBattlefieldAt(D,i));[...plan.attackerDeaths].sort((a,b)=>b-a).forEach(i=>removeBattlefieldAt(A,i));M.combat=null;checkWin();if(!M.over&&C.owner==='player'){M.active='player';M.phase='Main'}else if(!M.over){M.active='enemy';setTimeout(finishEnemyTurn,500)}save();render()}";
  assert(original.includes(oldResolve),'resolveCombatV600 anchor changed');
  const candidate=original.replace(oldResolve,newResolve);
  const marker='window.SIZA={';
  const probe=`window.__COMBAT_PLAN_COMPARE__={createMatch,setMatch:m=>state.match=m,resolveCombatV600,TEST_CARD_DB_V1};\n`;
  assert(original.includes(marker),'SIZA export marker missing');
  const oldDom=makeDom(inlineCore(original).replace(marker,probe+marker),'old');
  const newDom=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const O=oldDom.window.__COMBAT_PLAN_COMPARE__,N=newDom.window.__COMBAT_PLAN_COMPARE__;
  const generated=[
    {id:'guard_2_2',name:'Guard 2/2',type:'Creature',power:2,toughness:2,effects:[]},
    {id:'guard_1_1',name:'Guard 1/1',type:'Creature',power:1,toughness:1,effects:[]},
    {id:'guard_3_3',name:'Guard 3/3',type:'Creature',power:3,toughness:3,effects:[]},
    {id:'guard_grow_1_3',name:'Guard Grow 1/3',type:'Creature',power:1,toughness:3,effects:[{event:'combat-damage',type:'add-power-counter',amount:2}]},
    {id:'guard_grow_1_1',name:'Guard Grow 1/1',type:'Creature',power:1,toughness:1,effects:[{event:'combat-damage',type:'add-power-counter',amount:2}]},
    {id:'guard_def_grow',name:'Guard Defender Grow',type:'Creature',power:1,toughness:3,effects:[{event:'combat-damage',type:'add-power-counter',amount:1}]}
  ];
  O.TEST_CARD_DB_V1.push(...generated.map(card=>({...card})));
  N.TEST_CARD_DB_V1.push(...generated.map(card=>({...card})));
  const scenarios=[
    {owner:'player',attackers:['guard_grow_1_3'],defenders:[],blockers:{},attackerEquipment:[]},
    {owner:'player',attackers:['guard_2_2'],defenders:['guard_2_2'],blockers:{'0':0},attackerEquipment:[]},
    {owner:'player',attackers:['guard_grow_1_3'],defenders:['guard_1_1'],blockers:{'0':0},attackerEquipment:[]},
    {owner:'player',attackers:['guard_grow_1_1'],defenders:['guard_2_2'],blockers:{'0':0},attackerEquipment:[]},
    {owner:'player',attackers:['guard_1_1','guard_2_2'],defenders:['guard_def_grow'],blockers:{'0':0},attackerEquipment:[{id:'tideblade',target:1}]},
    {owner:'enemy',attackers:['guard_3_3'],defenders:['guard_def_grow'],blockers:{'0':0},attackerEquipment:[]}
  ];
  function setup(H,s){
    const M=H.createMatch(false,'immediate');H.setMatch(M);
    const A=M[s.owner],D=s.owner==='player'?M.enemy:M.player;
    for(const P of [M.player,M.enemy]){P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.equipment=[];P.graveyard=[];P.life=20;}
    A.battlefield=[...s.attackers];A.powerCounters=s.attackers.map(()=>0);A.summonedOn=s.attackers.map(()=>0);A.equipment=s.attackerEquipment.map(x=>({...x}));
    D.battlefield=[...s.defenders];D.powerCounters=s.defenders.map(()=>0);D.summonedOn=s.defenders.map(()=>0);
    M.combat={owner:s.owner,attackers:s.attackers.map((id,index)=>({index,id})),blockers:{...s.blockers}};
    M.active=s.owner==='player'?'enemy-defense':'defense';M.phase=s.owner==='player'?'Defensa rival':'Tu Defensa';M.ui={hand:-1,creature:-1,attackMode:false,attackers:[],fieldFocus:null};
    return M;
  }
  function snapshot(M,s){
    const A=M[s.owner],D=s.owner==='player'?M.enemy:M.player;
    return JSON.stringify({
      A:{life:A.life,battlefield:A.battlefield,powerCounters:A.powerCounters,summonedOn:A.summonedOn,graveyard:A.graveyard,exhausted:A.exhausted,equipment:A.equipment},
      D:{life:D.life,battlefield:D.battlefield,powerCounters:D.powerCounters,summonedOn:D.summonedOn,graveyard:D.graveyard,exhausted:D.exhausted,equipment:D.equipment},
      combat:M.combat,active:M.active,phase:M.phase,ui:M.ui,over:M.over,winner:M.winner,logs:M.log.map(x=>[x.t,x.m])
    });
  }
  let compared=0;
  for(const scenario of scenarios){
    const oldMatch=setup(O,scenario),newMatch=setup(N,scenario);
    O.resolveCombatV600();N.resolveCombatV600();
    const a=snapshot(oldMatch,scenario),b=snapshot(newMatch,scenario);
    assert(a===b,`combat mismatch ${JSON.stringify(scenario)}\nOLD ${a}\nNEW ${b}`);compared++;
  }
  const arena=newDom.window.SIZA.runArenaCriticalV071();
  assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS combat plan old/new ${compared} scenarios; Arena ${arena.passed}/${arena.total}`);
  oldDom.window.close();newDom.window.close();

  const latest=await getLive('siza-mobile-test/index.html');
  assert(latest.sha===live.sha&&latest.text===original,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared pure combat plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});
  if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);
  const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(error=>{console.error(error.stack||error.message);process.exit(1)});
