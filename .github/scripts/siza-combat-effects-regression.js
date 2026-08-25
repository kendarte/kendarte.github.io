const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

let html=fs.readFileSync('siza-mobile-test/index.html','utf8');
for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js']){
  const tag=`<script src="../siza-core/${name}"></script>`;
  if(!html.includes(tag))throw new Error(`Missing shared core tag ${name}`);
  html=html.replace(tag,`<script>${fs.readFileSync(`siza-core/${name}`,'utf8')}</script>`);
}
const marker='window.SIZA={';
if(!html.includes(marker))throw new Error('SIZA export marker missing');
const probe=`window.__COMBAT_EFFECTS_REGRESSION__={createMatch,setMatch:m=>state.match=m,addCreatureV070,declarePlayerCombat,resolveCombatV600,enemyAfterMain,TEST_CARD_DB_V1};\n`;
const vc=new VirtualConsole();vc.on('jsdomError',e=>console.error('[JSDOM combat-effects]',e.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole:vc});
dom.window.setTimeout=()=>0;
const H=dom.window.__COMBAT_EFFECTS_REGRESSION__;
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
function fresh(){const M=H.createMatch(false,'immediate');H.setMatch(M);for(const P of[M.player,M.enemy]){P.battlefield=[];P.powerCounters=[];P.summonedOn=[];P.exhausted=[];P.combatUsed=false}M.player.life=20;M.enemy.life=20;M.combat=null;M.active='player';return M}

test('Ignimite gana +1/+1 al hacer daño de combate',()=>{const M=fresh();H.addCreatureV070(M.player,'ignimite');M.combat={owner:'player',attackers:[{index:0,id:'ignimite'}],blockers:{}};M.active='enemy-defense';H.resolveCombatV600();return M.enemy.life===19&&M.player.powerCounters[0]===1});
test('Contrabandista inflige 1 al declarar ataque desde effect data',()=>{const M=fresh();H.addCreatureV070(M.player,'smuggler');H.declarePlayerCombat([0]);return M.enemy.life===19&&M.player.exhausted.includes(0)});
test('Carta desconocida ejecuta attack-declared damage 2',()=>{H.TEST_CARD_DB_V1.push({id:'reg_attack_ping',name:'Regression Attack Ping',type:'Creature',cost:1,difficulty:1,pips:{},power:2,toughness:2,text:'Ping.',art:'multi',glyph:'A',effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:2}]});const M=fresh();H.addCreatureV070(M.player,'reg_attack_ping');H.declarePlayerCombat([0]);return M.enemy.life===18});
test('Carta desconocida ejecuta combat-damage counter +2',()=>{H.TEST_CARD_DB_V1.push({id:'reg_grower',name:'Regression Grower',type:'Creature',cost:1,difficulty:1,pips:{},power:1,toughness:3,text:'Grow.',art:'multi',glyph:'G',effects:[{event:'combat-damage',type:'add-power-counter',amount:2}]});const M=fresh();H.addCreatureV070(M.player,'reg_grower');M.combat={owner:'player',attackers:[{index:0,id:'reg_grower'}],blockers:{}};M.active='enemy-defense';H.resolveCombatV600();return M.player.powerCounters[0]===2});

for(const result of results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
const passed=results.filter(x=>x.pass).length;console.log(`SIZA combat effects regression: ${passed}/${results.length}`);dom.window.close();if(passed!==results.length)process.exit(1);
