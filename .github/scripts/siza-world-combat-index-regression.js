'use strict';
const fs=require('fs');
const {JSDOM,VirtualConsole}=require('jsdom');

const html=fs.readFileSync('siza-mobile-test/index.html','utf8');
const marker='window.SIZA={';
if(!html.includes(marker))throw new Error('SIZA export marker not found');
const probe=`window.__SIZA_WORLD_BRIDGE_TEST__={getState:()=>state,getMatch:()=>state.match,checkWin,createMatch};\n`;
const virtualConsole=new VirtualConsole();
virtualConsole.on('jsdomError',error=>console.error('[JSDOM world-bridge]',error.message));
const dom=new JSDOM(html.replace(marker,probe+marker),{runScripts:'dangerously',url:'https://siza.local/siza-mobile-test/',virtualConsole});
const w=dom.window;
w.setTimeout=()=>0;

function assert(cond,msg){if(!cond)throw new Error(msg)}
const H=w.__SIZA_WORLD_BRIDGE_TEST__;
const S=w.SIZA;
assert(H&&S,'SIZA world bridge hooks missing');
assert(typeof S.startWorldEncounter==='function','startWorldEncounter export missing');
assert(typeof S.getWorldCombatResult==='function','getWorldCombatResult export missing');

const encounter={
  encounter_id:'COMBAT-REGRESSION-001',
  encounter_type:'COMBAT_CONFRONTATION',
  site:{room_id:'CAR-KAL-CITY-DAR-001',dbref:9,name:'Dársenas de Campana'},
  initiator:{entity_id:'PLAYER-REGRESSION',name:'Nereida',tcg_profile:{life:17,mf:3}},
  opponents:[{npc_id:'NPC-GUARD-REGRESSION',name:'Guardia de Dársena',tcg_profile:{life:9,mf:1}}],
  source_action_id:'ACT-REGRESSION-ATTACK'
};

const beforeAdventure=JSON.stringify(H.getState().adventure);
const emitted=[];
w.addEventListener('siza:combat-result',event=>emitted.push(event.detail));
const started=S.startWorldEncounter(encounter,'prepare');
assert(started.ok&&started.status==='WORLD_ENCOUNTER_STARTED','external encounter did not start');
let M=H.getMatch();
assert(M&&M.worldBridge?.encounter?.encounter_id===encounter.encounter_id,'encounter not attached to real match');
assert(M.player.life===17&&M.player.mf===3,'player encounter TCG profile not applied');
assert(M.enemy.life===9&&M.enemy.mf===1,'enemy encounter TCG profile not applied');
assert(S.getWorldCombatResult()===null,'result exists before resolution');

M.enemy.life=0;
H.checkWin();
const result=S.getWorldCombatResult();
assert(result?.encounter_id===encounter.encounter_id,'resolved external encounter did not expose result');
assert(result.outcome==='PLAYER_WIN','external win mapped incorrectly');
assert(result.winner_ids[0]==='PLAYER-REGRESSION','external winner identity lost');
assert(result.defeated_ids[0]==='NPC-GUARD-REGRESSION','external defeated identity lost');
assert(result.source_action_id==='ACT-REGRESSION-ATTACK','source action provenance lost');
assert(emitted.length===1,'external result event must emit exactly once');
assert(JSON.stringify(H.getState().adventure)===beforeAdventure,'external TCG result illegally mutated standalone Adventure/world state');

H.checkWin();
assert(emitted.length===1,'repeated win check emitted World result twice');

H.getState().adventure.flags={};
H.getState().adventure.advance=0;
H.getState().adventure.currentEvent=null;
H.getState().match=H.createMatch(true,'prepare');
M=H.getState().match;
M.enemy.life=0;
H.checkWin();
assert(H.getState().adventure.flags.smugglersResolved===true,'legacy standalone Adventure win no longer resolves its old flag');
assert(H.getState().adventure.advance===2,'legacy standalone Adventure win no longer advances by two');
assert(!M.worldBridge,'legacy standalone match unexpectedly became World encounter');

console.log('PASS integrated World Combat Bridge: external result-only authority + legacy standalone compatibility');
dom.window.close();
