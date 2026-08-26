'use strict';
const fs=require('fs');
const path='siza-mobile-test/index.html';
let html=fs.readFileSync(path,'utf8');

function fail(message){throw new Error(message)}
function replaceOnce(source,oldText,newText,label){
  const count=source.split(oldText).length-1;
  if(count!==1)fail(`${label}: expected exactly one anchor, found ${count}`);
  return source.replace(oldText,newText);
}
function replaceFunction(source,name,newText){
  const token=`function ${name}(`;
  const start=source.indexOf(token);
  if(start<0)fail(`${name}: function start not found`);
  const next=source.indexOf('\nfunction ',start+token.length);
  if(next<0)fail(`${name}: next function boundary not found`);
  return source.slice(0,start)+newText+source.slice(next);
}

const bridgeTag='<script src="world-combat-bridge-v01.js"></script>';
if(!html.includes(bridgeTag)){
  html=replaceOnce(
    html,
    '<script src="adventure-book-shell-renderer-v01.js"></script>',
    '<script src="adventure-book-shell-renderer-v01.js"></script>\n'+bridgeTag,
    'bridge script tag'
  );
}

html=replaceFunction(html,'createMatch',`function createMatch(adventure=false,mode='prepare',worldEncounter=null){
  const p=makeDuelistV070(makeLibrary(),true),e=makeDuelistV070(makeLibrary(),false),entry=SizaEntryRules.normalizeMode(mode);
  const M={id:'match_'+Date.now(),rulesVersion:RULES_VERSION,rules:{entryMode:entry,offering:true},turn:1,phase:'Main',active:'player',player:p,enemy:e,stack:[],log:[{t:'Reglas',m:\`Arena v\${RULES_VERSION}. Cristales U/U/R. \${ENTRY_V070[entry].short} está EN PRUEBA.\`},{t:'Mano',m:'Cada lado toma siete cartas aleatorias; el primer jugador no roba.'}],pendingEquip:null,pendingChoice:null,combat:null,responseWindow:null,stackReturnOwner:null,enemyStage:null,ui:{hand:-1,creature:-1,attackMode:false,attackers:[],fieldFocus:null},adventure,over:false,winner:null};
  if(worldEncounter){
    const bridge=SizaWorldCombatBridgeV01.attachEncounter(M,worldEncounter);
    if(!bridge.ok)throw new Error('World Combat Encounter inválido: '+bridge.status+' '+(bridge.errors||[]).join(','));
    M.log.push({t:'World Engine',m:'Encounter '+bridge.encounter.encounter_id+' autorizado.'});
  }
  return M;
}`);

const configuredAnchor="function startConfiguredV070(mode){return state.pendingAdventureDuel?startAdventureDuel(mode):startPractice(mode)}";
if(!html.includes('function startWorldEncounter(')){
  html=replaceOnce(html,configuredAnchor,configuredAnchor+`\nfunction startWorldEncounter(encounter,mode='prepare'){
  const validation=SizaWorldCombatBridgeV01.validateEncounter(encounter);
  if(!validation.valid)return{ok:false,status:validation.status,errors:validation.errors};
  if(totalDeck()!==60)return{ok:false,status:'INVALID_PLAYER_DECK',errors:['PLAYER_DECK_MUST_HAVE_60_CARDS']};
  try{
    state.match=createMatch(false,mode,validation.encounter);
  }catch(error){
    return{ok:false,status:'ENCOUNTER_START_FAILED',error:String(error?.message||error)};
  }
  state.pendingAdventureDuel=false;
  state.route='match';
  save();
  render();
  return{ok:true,status:'WORLD_ENCOUNTER_STARTED',encounter_id:validation.encounter.encounter_id,match_id:state.match.id};
}
function getWorldCombatResult(){return SizaWorldCombatBridgeV01.getResult(state.match)}`,'world encounter entrypoint');
}

html=replaceFunction(html,'checkWin',`function checkWin(){
  const M=state.match,winner=SizaCardEffects.matchWinner(M.player.life,M.enemy.life);
  if(!winner)return;
  M.over=true;
  M.winner=winner;
  addLog('Match',\`\${M.winner==='player'?'Victoria':'Derrota'}.\`);
  if(SizaWorldCombatBridgeV01.isWorldMatch(M)){
    const packet=SizaWorldCombatBridgeV01.emitResult(M);
    if(!packet.ok)addLog('Bridge','No se pudo producir Combat Result: '+packet.status);
    return;
  }
  if(M.adventure&&M.winner==='player'){
    state.adventure.flags.smugglersResolved=true;
    state.adventure.advance=Math.min(5,state.adventure.advance+2);
    journal('Siza Encounter','Derrotaste al Magistócrata contrabandista. La escalera inferior quedó abierta.');
    state.adventure.currentEvent=null;
    chooseAdventureEvent();
  }
}`);

// replaceFunction() ends at the next named function. ENTRY_V070 originally lived
// between checkWin() and crystalReqV070(), so restore that declaration explicitly.
if(!html.includes('const ENTRY_V070=SizaEntryRules.MODES;')){
  html=replaceOnce(
    html,
    '\nfunction crystalReqV070(c)',
    '\nconst ENTRY_V070=SizaEntryRules.MODES;\nfunction crystalReqV070(c)',
    'Arena entry mode declaration'
  );
}

if(!html.includes('startWorldEncounter,getWorldCombatResult')){
  html=replaceOnce(
    html,
    'resetDeck,startPractice,startAdventureDuel,startConfiguredV070,playHand',
    'resetDeck,startPractice,startAdventureDuel,startConfiguredV070,startWorldEncounter,getWorldCombatResult,playHand',
    'SIZA bridge exports'
  );
}

const required=[
  bridgeTag,
  "function createMatch(adventure=false,mode='prepare',worldEncounter=null)",
  'SizaWorldCombatBridgeV01.attachEncounter',
  'function startWorldEncounter(',
  'function getWorldCombatResult()',
  'SizaWorldCombatBridgeV01.emitResult(M)',
  'const ENTRY_V070=SizaEntryRules.MODES;',
  'startWorldEncounter,getWorldCombatResult'
];
for(const token of required)if(!html.includes(token))fail(`postcondition missing: ${token}`);

fs.writeFileSync(path,html);
console.log('PASS patched siza-mobile-test/index.html for World Combat Bridge v0.1');
