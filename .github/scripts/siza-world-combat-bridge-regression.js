'use strict';
const fs=require('fs');
const vm=require('vm');

const events=[];
class FakeCustomEvent{constructor(type,init){this.type=type;this.detail=init?.detail}}
const guardDeck={id:'deck_guard',name:'Guard Deck',counts:{GUARD_A:4,GUARD_B:4,GUARD_C:4}};
const sandbox={
  console,
  CustomEvent:FakeCustomEvent,
  dispatchEvent(event){events.push(event)},
  SizaDeckCatalog:{
    get(id){return id==='deck_guard'?guardDeck:null},
    copy(id){const d=this.get(id);return d?{...d,counts:{...d.counts}}:null}
  },
  window:null
};
sandbox.window=sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('siza-mobile-test/world-combat-bridge-v01.js','utf8'),sandbox,{filename:'world-combat-bridge-v01.js'});
const B=sandbox.SizaWorldCombatBridgeV01;
if(!B)throw new Error('SizaWorldCombatBridgeV01 missing');

function assert(cond,msg){if(!cond)throw new Error(msg)}
function match(){return{
  id:'match-test',rulesVersion:'0.7.0',over:false,winner:null,
  player:{life:20,mf:2,prow:2,eva:2,hand:['OLD_PLAYER'],library:['OLD_PLAYER']},
  enemy:{life:20,mf:2,prow:2,eva:2,hand:['OLD_ENEMY'],library:['OLD_ENEMY']}
}}
const encounter={
  encounter_id:'COMBAT-CAR-KAL-001',
  encounter_type:'COMBAT_CONFRONTATION',
  site:{room_id:'CAR-KAL-CITY-DAR-001',dbref:9,name:'Dársenas de Campana'},
  initiator:{entity_id:'PLAYER-1',name:'Nereida',deck_id:'deck_tide_crimson',tcg_profile:{life:18,mf:3}},
  opponents:[{npc_id:'NPC-GUARD-1',name:'Guardia de Dársena',deck_id:'deck_guard',tcg_profile:{life:12,mf:1}}],
  stakes:{on_player_win:['GUARD_DEFEATED'],on_player_loss:['PLAYER_DEFEATED']},
  world_context_tags:['DARSENA','SECURITY'],
  source_action_id:'ACT-ATTACK-GUARD-1'
};

const invalid=B.validateEncounter({...encounter,opponents:[]});
assert(!invalid.valid&&invalid.errors.includes('MISSING_OPPONENT'),'missing opponent must fail closed');
const tooMany=B.validateEncounter({...encounter,opponents:[...encounter.opponents,{npc_id:'NPC-2'}]});
assert(!tooMany.valid&&tooMany.errors.includes('UNSUPPORTED_OPPONENT_COUNT'),'current 1v1 runtime must reject multi-opponent encounter');

const M=match();
const attached=B.attachEncounter(M,encounter);
assert(attached.ok&&B.isWorldMatch(M),'valid encounter did not attach');
assert(M.player.life===18&&M.player.mf===3,'initiator tcg_profile not applied');
assert(M.enemy.life===12&&M.enemy.mf===1,'opponent tcg_profile not applied');
assert(attached.deck_load.enemy.applied&&attached.deck_load.enemy.deck_id==='deck_guard','authored opponent deck was not applied');
assert(M.enemy.hand.length===7&&M.enemy.library.length===5,'fresh opponent hand/library not created from authored deck');
assert(M.enemy.hand.every(id=>id.startsWith('GUARD_'))&&M.enemy.library.every(id=>id.startsWith('GUARD_')),'opponent deck contains stale cards');
assert(M.enemy.deck_id==='deck_guard','resolved deck id not stored on enemy duelist');
const meta=B.presentationMeta(M);
assert(meta.location==='Dársenas de Campana'&&meta.opponent_name==='Guardia de Dársena','presentation meta not grounded in encounter');
assert(meta.opponent_deck_id==='deck_guard','presentation meta missing opponent deck id');

assert(B.buildResult(M).status==='ENCOUNTER_NOT_RESOLVED','unresolved encounter produced result');
M.player.life=11;
M.enemy.life=0;
M.over=true;
M.winner='player';
const built=B.buildResult(M);
assert(built.ok&&built.result.outcome==='PLAYER_WIN','winner mapping failed');
assert(JSON.stringify(built.result.winner_ids)===JSON.stringify(['PLAYER-1']),'winner id incorrect');
assert(JSON.stringify(built.result.defeated_ids)===JSON.stringify(['NPC-GUARD-1']),'defeated id incorrect');
assert(built.result.participants[0].damage===7,'player damage delta incorrect');
assert(built.result.participants[1].damage===12,'enemy damage delta incorrect');
assert(built.result.source_action_id==='ACT-ATTACK-GUARD-1','source action provenance missing');
assert(!('stakes' in built.result),'TCG result must not reinterpret authored world stakes');

const emitted=B.emitResult(M);
assert(emitted.status==='COMBAT_RESULT_EMITTED','first result did not emit');
assert(events.length===1&&events[0].type==='siza:combat-result','combat result event missing');
const again=B.emitResult(M);
assert(again.status==='RESULT_ALREADY_EMITTED','duplicate result was not idempotent');
assert(events.length===1,'duplicate result emitted twice');
assert(B.getResult(M).encounter_id==='COMBAT-CAR-KAL-001','stored result unavailable');

console.log('PASS World Combat Bridge v0.2: validation, profiles, authored NPC deck load, result authority boundary, provenance, idempotent emit');
