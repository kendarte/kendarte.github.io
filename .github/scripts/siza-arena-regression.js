const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

function inlineCore(html){
  let out=html;
  for(const name of ['card-effects.js','card-schema.js','cards.js','card-renderer.js','manifest-rules.js','crystal-rules.js']){
    const tag=`<script src="../siza-core/${name}"></script>`;
    if(!out.includes(tag))throw new Error(`Missing shared core tag ${name}`);
    const source=fs.readFileSync(`siza-core/${name}`,'utf8');
    out=out.replace(tag,`<script>${source}</script>`);
  }
  return out;
}

function makeDom(html,label){
  const virtualConsole=new VirtualConsole();
  virtualConsole.on('jsdomError',error=>console.error(`[JSDOM ${label}]`,error.message));
  return new JSDOM(html,{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole});
}

const original=inlineCore(fs.readFileSync('siza-mobile-test/index.html','utf8'));

function runCore(){
  const dom=makeDom(original,'core');
  dom.window.setTimeout=()=>0;
  const runner=dom.window.SIZA?.runArenaCriticalV071;
  if(typeof runner!=='function')throw new Error('SIZA.runArenaCriticalV071 is not available.');
  const report=runner();
  console.log(`SIZA Arena contract ${report.version}: ${report.passed}/${report.total}`);
  for(const result of report.results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
  dom.window.close();
  if(report.passed!==report.total)throw new Error(`Arena core ${report.passed}/${report.total}`);
}

function runCombat(){
  const marker='window.SIZA={';
  if(!original.includes(marker))throw new Error('SIZA export marker not found');
  const probe=`window.__SIZA_COMBAT_TEST__={createMatch,setMatch:m=>state.match=m,getMatch:()=>state.match,addCreatureV070,assignAiBlockersV600,assignBlocker,resolveCombatV600,declarePlayerCombat};\n`;
  const dom=makeDom(original.replace(marker,probe+marker),'combat');
  dom.window.setTimeout=()=>0;
  const H=dom.window.__SIZA_COMBAT_TEST__;
  if(!H)throw new Error('Combat test hooks were not exposed');
  const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
  const fresh=mode=>{const M=H.createMatch(false,mode);H.setMatch(M);return M};

  test('IA excluye bloqueadores agotados en combate real',()=>{
    const M=fresh('immediate');H.addCreatureV070(M.player,'leviathan');H.addCreatureV070(M.enemy,'watcher');H.addCreatureV070(M.enemy,'servitor');M.enemy.exhausted=[0];M.combat={owner:'player',attackers:[{index:0,id:'leviathan'}],blockers:{}};H.assignAiBlockersV600();return M.combat.blockers['0']===1;
  });
  test('Jugador no puede asignar una agotada como bloqueador',()=>{
    const M=fresh('immediate');H.addCreatureV070(M.enemy,'leviathan');H.addCreatureV070(M.player,'watcher');H.addCreatureV070(M.player,'servitor');M.player.exhausted=[0];M.combat={owner:'enemy',attackers:[{index:0,id:'leviathan'}],blockers:{}};M.active='defense';H.assignBlocker(0,0);const rejected=M.combat.blockers['0']==null;H.assignBlocker(0,1);return rejected&&M.combat.blockers['0']===1;
  });
  test('Daño simultáneo destruye ambos 2/2 y los manda al Cementerio',()=>{
    const M=fresh('immediate');H.addCreatureV070(M.player,'servitor');H.addCreatureV070(M.enemy,'servitor');M.combat={owner:'player',attackers:[{index:0,id:'servitor'}],blockers:{'0':0}};M.active='enemy-defense';H.resolveCombatV600();return M.player.battlefield.length===0&&M.enemy.battlefield.length===0&&M.player.graveyard.includes('servitor')&&M.enemy.graveyard.includes('servitor')&&M.combat===null&&M.active==='player';
  });
  test('Contrabandista aplica +1 al declarar y queda agotado con combate usado',()=>{
    const M=fresh('immediate');H.addCreatureV070(M.player,'smuggler');const before=M.enemy.life;H.declarePlayerCombat([0]);return M.enemy.life===before-1&&M.player.combatUsed===true&&M.player.exhausted.includes(0)&&M.combat?.owner==='player'&&M.combat.attackers.length===1;
  });
  for(const result of results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
  const passed=results.filter(result=>result.pass).length;
  console.log(`SIZA live combat regression: ${passed}/${results.length}`);
  dom.window.close();
  if(passed!==results.length)throw new Error(`Combat ${passed}/${results.length}`);
}

function runStack(){
  const marker='window.SIZA={';
  if(!original.includes(marker))throw new Error('SIZA export marker not found');
  const probe=`window.__SIZA_STACK_TEST__={createMatch,setMatch:m=>state.match=m,resolveTopStack,resolveStackAll,TEST_CARD_DB_V1};\n`;
  const dom=makeDom(original.replace(marker,probe+marker),'stack');
  dom.window.setTimeout=()=>0;
  const H=dom.window.__SIZA_STACK_TEST__;
  if(!H)throw new Error('Stack test hooks were not exposed');
  const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
  const fresh=()=>{const M=H.createMatch(false,'prepare');H.setMatch(M);return M};

  test('Chispa resuelve 2 daño y va al Cementerio',()=>{
    const M=fresh();M.player.graveyard=[];M.enemy.life=20;M.stack=[{id:'spark-test',cardId:'spark',owner:'player'}];H.resolveTopStack();return M.enemy.life===18&&M.stack.length===0&&M.player.graveyard.includes('spark');
  });
  test('Niebla roba una carta y va al Cementerio',()=>{
    const M=fresh();M.player.hand=[];M.player.library=['spark'];M.player.graveyard=[];M.stack=[{id:'mist-test',cardId:'mist',owner:'player'}];H.resolveTopStack();return M.player.hand.length===1&&M.player.hand[0]==='spark'&&M.player.graveyard.includes('mist');
  });
  test('Servidor entra con estado de criatura y abre Observar',()=>{
    const M=fresh();M.player.hand=[];M.player.library=['spark'];M.stack=[{id:'servitor-test',cardId:'servitor',owner:'player'}];H.resolveTopStack();return M.player.battlefield[0]==='servitor'&&M.player.powerCounters[0]===0&&M.player.summonedOn[0]===M.player.ownTurn&&M.pendingChoice?.type==='observe'&&M.pendingChoice.cardId==='spark';
  });
  test('Negación retira el objetivo y ambas cartas van al Cementerio',()=>{
    const M=fresh();M.player.graveyard=[];M.enemy.graveyard=[];M.enemy.life=20;M.stack=[{id:'target',cardId:'spark',owner:'enemy'},{id:'counter-test',cardId:'counter',owner:'player',targetStackId:'target'}];H.resolveTopStack();return M.stack.length===0&&M.player.graveyard.includes('counter')&&M.enemy.graveyard.includes('spark')&&M.enemy.life===20;
  });
  test('resolveStackAll se detiene ante una elección pendiente',()=>{
    const M=fresh();M.player.hand=[];M.player.library=['spark'];M.enemy.life=20;M.stack=[{id:'lower',cardId:'spark',owner:'player'},{id:'top',cardId:'servitor',owner:'player'}];H.resolveStackAll();return M.pendingChoice?.type==='observe'&&M.stack.length===1&&M.stack[0].id==='lower'&&M.enemy.life===20;
  });
  test('Carta temporal desconocida ejecuta draw 2 sólo por effects',()=>{
    H.TEST_CARD_DB_V1.push({id:'regression_generated_draw2',name:'Regression Draw Two',type:'Instant',cost:1,difficulty:1,pips:{},text:'Draw two.',art:'multi',glyph:'G',effects:[{event:'resolve',type:'draw',target:'self',amount:2}]});
    const M=fresh();M.player.hand=[];M.player.library=['spark','mist','watcher'];M.player.graveyard=[];M.stack=[{id:'generated',cardId:'regression_generated_draw2',owner:'player'}];H.resolveTopStack();return M.player.hand.join(',')==='spark,mist'&&M.player.graveyard.includes('regression_generated_draw2');
  });
  for(const result of results)console.log(`${result.pass?'PASS':'FAIL'} ${result.name}${result.error?` :: ${result.error}`:''}`);
  const passed=results.filter(result=>result.pass).length;
  console.log(`SIZA live stack regression: ${passed}/${results.length}`);
  dom.window.close();
  if(passed!==results.length)throw new Error(`Stack ${passed}/${results.length}`);
}

function reportDuplicates(){
  const matches=[...fs.readFileSync('siza-mobile-test/index.html','utf8').matchAll(/\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g)];
  const counts=new Map();for(const match of matches)counts.set(match[1],(counts.get(match[1])||0)+1);
  const duplicates=[...counts.entries()].filter(([,count])=>count>1).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));
  console.log(`Named function declarations: ${matches.length}`);
  console.log(`Duplicate names: ${duplicates.length}`);
  for(const[name,count]of duplicates)console.log(`${count}x ${name}`);
}

runCore();
runCombat();
runStack();
reportDuplicates();
