(function (root) {
  'use strict';

  const VERSION='0.1.0';
  const BUILD='world-combat-bridge-v0.1';
  const ENCOUNTER_TYPE='COMBAT_CONFRONTATION';

  function clone(value){
    if(value===undefined)return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function text(value){return String(value===undefined||value===null?'':value).trim()}
  function finite(value){const n=Number(value);return Number.isFinite(n)?n:null}
  function entityId(row){return text(row?.entity_id||row?.npc_id||row?.id)}

  function validateEncounter(raw){
    const errors=[];
    const src=raw&&typeof raw==='object'?raw:{};
    const encounterId=text(src.encounter_id);
    const encounterType=text(src.encounter_type||ENCOUNTER_TYPE);
    const initiator=src.initiator&&typeof src.initiator==='object'?src.initiator:null;
    const opponents=Array.isArray(src.opponents)?src.opponents.filter(x=>x&&typeof x==='object'):[];

    if(!encounterId)errors.push('MISSING_ENCOUNTER_ID');
    if(encounterType!==ENCOUNTER_TYPE)errors.push('UNSUPPORTED_ENCOUNTER_TYPE');
    if(!initiator||!entityId(initiator))errors.push('MISSING_INITIATOR_ID');
    if(opponents.length!==1)errors.push(opponents.length?'UNSUPPORTED_OPPONENT_COUNT':'MISSING_OPPONENT');
    if(opponents.length===1&&!entityId(opponents[0]))errors.push('MISSING_OPPONENT_ID');

    const initiatorId=initiator?entityId(initiator):'';
    const opponentId=opponents.length===1?entityId(opponents[0]):'';
    if(initiatorId&&opponentId&&initiatorId===opponentId)errors.push('DUPLICATE_PARTICIPANT_ID');

    if(errors.length)return{valid:false,status:'INVALID_ENCOUNTER',errors};

    const normalized={
      encounter_id:encounterId,
      encounter_type:ENCOUNTER_TYPE,
      site:{
        room_id:text(src.site?.room_id||src.location_id),
        dbref:finite(src.site?.dbref),
        name:text(src.site?.name||src.location_name)
      },
      initiator:{
        entity_id:initiatorId,
        name:text(initiator.name)||initiatorId,
        deck_id:text(initiator.deck_id),
        loadout:clone(initiator.loadout||{}),
        world_status:clone(initiator.world_status||{}),
        tcg_profile:clone(initiator.tcg_profile||{})
      },
      opponents:[{
        entity_id:opponentId,
        name:text(opponents[0].name)||opponentId,
        deck_id:text(opponents[0].deck_id),
        loadout:clone(opponents[0].loadout||{}),
        world_status:clone(opponents[0].world_status||{}),
        tcg_profile:clone(opponents[0].tcg_profile||{})
      }],
      allies:Array.isArray(src.allies)?clone(src.allies):[],
      stakes:clone(src.stakes||{}),
      world_modifiers:Array.isArray(src.world_modifiers)?clone(src.world_modifiers):[],
      world_context_tags:Array.isArray(src.world_context_tags)?src.world_context_tags.map(text).filter(Boolean):[],
      source_action_id:text(src.source_action_id),
      created_at:text(src.created_at)
    };
    return{valid:true,status:'VALID_ENCOUNTER',errors:[],encounter:normalized};
  }

  function applyProfile(duelist,profile){
    if(!duelist||!profile||typeof profile!=='object')return;
    const fields=['life','mf','prow','eva'];
    for(const field of fields){
      const n=finite(profile[field]);
      if(n!==null)duelist[field]=n;
    }
  }

  function attachEncounter(match,raw){
    if(!match||typeof match!=='object')return{ok:false,status:'NO_MATCH'};
    const validation=validateEncounter(raw);
    if(!validation.valid)return{ok:false,...validation};
    const encounter=validation.encounter;

    applyProfile(match.player,encounter.initiator.tcg_profile);
    applyProfile(match.enemy,encounter.opponents[0].tcg_profile);

    match.worldBridge={
      version:VERSION,
      build:BUILD,
      encounter,
      initial:{
        player_life:finite(match.player?.life),
        enemy_life:finite(match.enemy?.life)
      },
      result:null,
      emitted:false
    };
    return{ok:true,status:'ENCOUNTER_ATTACHED',encounter:clone(encounter),match};
  }

  function isWorldMatch(match){
    return !!(match&&match.worldBridge&&match.worldBridge.encounter&&text(match.worldBridge.encounter.encounter_id));
  }

  function resultState(owner,winner){return owner===winner?'ACTIVE':'DEFEATED'}

  function participantResult(entity,owner,match,startLife){
    const current=finite(match?.[owner]?.life);
    const start=finite(startLife);
    return{
      entity_id:entity.entity_id,
      name:entity.name,
      result_state:resultState(owner,match.winner),
      life_start:start,
      life_remaining:current,
      damage:start!==null&&current!==null?Math.max(0,start-current):null
    };
  }

  function buildResult(match){
    if(!isWorldMatch(match))return{ok:false,status:'NO_WORLD_ENCOUNTER'};
    if(!match.over||!['player','enemy'].includes(match.winner))return{ok:false,status:'ENCOUNTER_NOT_RESOLVED'};

    const bridge=match.worldBridge;
    const encounter=bridge.encounter;
    const initiator=encounter.initiator;
    const opponent=encounter.opponents[0];
    const playerWon=match.winner==='player';
    const winnerId=playerWon?initiator.entity_id:opponent.entity_id;
    const defeatedId=playerWon?opponent.entity_id:initiator.entity_id;
    const result={
      bridge_version:VERSION,
      bridge_build:BUILD,
      result_id:`${encounter.encounter_id}:RESULT:1`,
      encounter_id:encounter.encounter_id,
      status:'RESOLVED',
      outcome:playerWon?'PLAYER_WIN':'PLAYER_LOSS',
      winner_ids:[winnerId],
      defeated_ids:[defeatedId],
      participants:[
        participantResult(initiator,'player',match,bridge.initial.player_life),
        participantResult(opponent,'enemy',match,bridge.initial.enemy_life)
      ],
      fled_ids:[],
      surrendered_ids:[],
      killed_ids:[],
      tags:[],
      tcg_build:text(match.rulesVersion||''),
      source_action_id:encounter.source_action_id||'',
      site:clone(encounter.site)
    };
    return{ok:true,status:'COMBAT_RESULT_READY',result};
  }

  function emitResult(match){
    const packet=buildResult(match);
    if(!packet.ok)return packet;
    const bridge=match.worldBridge;
    if(bridge.result){
      return{ok:true,status:'RESULT_ALREADY_EMITTED',result:clone(bridge.result)};
    }
    bridge.result=clone(packet.result);
    bridge.emitted=true;
    if(root&&typeof root.dispatchEvent==='function'&&typeof root.CustomEvent==='function'){
      root.dispatchEvent(new root.CustomEvent('siza:combat-result',{detail:clone(packet.result)}));
    }
    return{ok:true,status:'COMBAT_RESULT_EMITTED',result:clone(packet.result)};
  }

  function getResult(match){
    return clone(match?.worldBridge?.result||null);
  }

  function presentationMeta(match){
    if(!isWorldMatch(match))return null;
    const encounter=match.worldBridge.encounter;
    return{
      encounter_id:encounter.encounter_id,
      location:encounter.site?.name||encounter.site?.room_id||'',
      opponent_name:encounter.opponents?.[0]?.name||'Rival',
      player_name:text(match?.player?.name)||encounter.initiator?.name||'',
      world_context_tags:clone(encounter.world_context_tags||[])
    };
  }

  root.SizaWorldCombatBridgeV01=Object.freeze({
    VERSION,BUILD,ENCOUNTER_TYPE,
    validateEncounter,
    attachEncounter,
    isWorldMatch,
    buildResult,
    emitResult,
    getResult,
    presentationMeta
  });
})(typeof window!=='undefined'?window:globalThis);
