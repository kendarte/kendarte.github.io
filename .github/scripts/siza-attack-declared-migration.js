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
  const oldFn="function attackDeclaredDamageV1(P,indices){let amount=0,sources=[];for(const i of indices){const c=cardById(P.battlefield[i]);for(const effect of SizaCardEffects.forEvent(c,'attack-declared'))if(effect.type==='damage-character'&&(effect.target||'opponent')==='opponent'&&effect.amount>0){amount+=effect.amount;sources.push(c.name)}}return{amount,source:sources.length&&sources.every(x=>x===sources[0])?sources[0]:'Efectos de ataque'}}";
  const newFn="function attackDeclaredDamageV1(P,indices){return SizaCreatureRules.attackDeclaredDamage(P,indices,cardById,SizaCardEffects.forEvent)}";
  assert(live.text.includes(oldFn),'attackDeclaredDamageV1 anchor changed');
  const candidate=live.text.replace(oldFn,newFn),marker='window.SIZA={';
  const probe=`window.__ATTACK_DECLARED_COMPARE__={cardById,TEST_CARD_DB_V1,createMatch,setMatch:m=>state.match=m,attackDeclaredDamageV1,declarePlayerCombat,enemyAfterMain};\n`;
  assert(live.text.includes(marker),'SIZA export marker missing');
  const O=makeDom(inlineCore(live.text).replace(marker,probe+marker),'old'),N=makeDom(inlineCore(candidate).replace(marker,probe+marker),'new');
  const o=O.window.__ATTACK_DECLARED_COMPARE__,n=N.window.__ATTACK_DECLARED_COMPARE__;
  const generated=[
    {id:'ad_two',name:'Attack Two',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:2}]},
    {id:'ad_three',name:'Attack Three',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:3}]},
    {id:'ad_default',name:'Attack Default',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',amount:1}]},
    {id:'ad_self',name:'Attack Self',type:'Creature',power:1,toughness:2,effects:[{event:'attack-declared',type:'damage-character',target:'self',amount:4}]},
    {id:'ad_none',name:'Attack None',type:'Creature',power:1,toughness:2,effects:[]}
  ];
  o.TEST_CARD_DB_V1.push(...generated.map(x=>({...x})));n.TEST_CARD_DB_V1.push(...generated.map(x=>({...x})));
  const cases=[
    {battlefield:['smuggler'],indices:[0]},
    {battlefield:['ad_two'],indices:[0]},
    {battlefield:['ad_two','ad_three'],indices:[0,1]},
    {battlefield:['ad_default','ad_self'],indices:[0,1]},
    {battlefield:['ad_two','ad_two'],indices:[0,1]},
    {battlefield:['ad_none','ad_self'],indices:[0,1]}
  ];
  let compared=0;
  for(const c of cases){const P={battlefield:[...c.battlefield]},a=o.attackDeclaredDamageV1(P,c.indices),b=n.attackDeclaredDamageV1(P,c.indices);assert(JSON.stringify(a)===JSON.stringify(b),`attack-declared mismatch ${JSON.stringify(c)} :: ${JSON.stringify(a)}/${JSON.stringify(b)}`);compared++}
  function fresh(H){const M=H.createMatch(false,'immediate');H.setMatch(M);for(const P of[M.player,M.enemy]){P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.equipment=[];P.combatUsed=false}M.player.life=20;M.enemy.life=20;M.log=[];M.combat=null;M.active='player';return M}
  function snap(M){return JSON.stringify({playerLife:M.player.life,enemyLife:M.enemy.life,playerExhausted:M.player.exhausted,enemyExhausted:M.enemy.exhausted,playerCombatUsed:M.player.combatUsed,combat:M.combat,active:M.active,phase:M.phase,logs:M.log.map(x=>[x.t,x.m])})}
  {
    const OM=fresh(o),NM=fresh(n);for(const M of[OM,NM]){M.player.battlefield=['ad_two','ad_three'];M.player.powerCounters=[0,0];M.player.summonedOn=[0,0]}
    o.declarePlayerCombat([0,1]);n.declarePlayerCombat([0,1]);assert(snap(OM)===snap(NM),`player declaration mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  {
    const OM=fresh(o),NM=fresh(n);for(const M of[OM,NM]){M.enemy.battlefield=['ad_default'];M.enemy.powerCounters=[0];M.enemy.summonedOn=[0];M.active='enemy'}
    o.enemyAfterMain();n.enemyAfterMain();assert(snap(OM)===snap(NM),`enemy declaration mismatch :: ${snap(OM)} / ${snap(NM)}`);compared++;
  }
  const arena=N.window.SIZA.runArenaCriticalV071();assert(arena.passed===arena.total,`Arena ${arena.passed}/${arena.total}`);
  console.log(`PASS attack-declared old/new ${compared} comparisons; Arena ${arena.passed}/${arena.total}`);O.window.close();N.window.close();
  const latest=await get('siza-mobile-test/index.html');assert(latest.sha===live.sha&&latest.text===live.text,'Runtime changed during guarded migration');
  const put=await fetch(`${api}/contents/siza-mobile-test/index.html`,{method:'PUT',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({message:'Use shared attack-declared damage plan',content:Buffer.from(candidate).toString('base64'),sha:latest.sha,branch:'main'})});if(!put.ok)throw new Error(`PUT ${put.status}: ${await put.text()}`);const result=await put.json();console.log('COMMIT '+result.commit.sha);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
