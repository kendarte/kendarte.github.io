(function(global){
'use strict';

function counterValue(player,index){
  return player?.powerCounters?.[index]||0;
}

function equipmentForIndex(player,index){
  return (player?.equipment||[]).filter(entry=>entry.target===index);
}

function equipmentPowerBonusValue(player,index,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const effectResolver=typeof effectsForEvent==='function'?effectsForEvent:()=>[];
  return equipmentForIndex(player,index).reduce((sum,entry)=>{
    const card=cardResolver(entry.id);
    return sum+effectResolver(card,'equipped')
      .filter(effect=>effect.type==='modify-power')
      .reduce((subtotal,effect)=>subtotal+(effect.amount||0),0);
  },0);
}

function effectivePowerValue(player,index,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const card=cardResolver(player?.battlefield?.[index]);
  return (card?.power||0)+counterValue(player,index)+equipmentPowerBonusValue(player,index,cardResolver,effectsForEvent);
}

function toughnessValue(player,index,resolveCard){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const card=cardResolver(player?.battlefield?.[index]);
  return (card?.toughness||0)+counterValue(player,index);
}

function addBattlefieldCreature(player,id){
  player.battlefield.push(id);
  player.powerCounters.push(0);
  player.summonedOn.push(player.ownTurn);
  return player.battlefield.length-1;
}

function removeBattlefieldCreature(player,index,dest='graveyard'){
  if(index<0||index>=player.battlefield.length)return null;
  const id=player.battlefield.splice(index,1)[0];
  player[dest].push(id);
  player.powerCounters.splice(index,1);
  player.summonedOn.splice(index,1);
  player.exhausted=(player.exhausted||[]).filter(value=>value!==index).map(value=>value>index?value-1:value);
  for(const equipment of player.equipment||[]){
    if(equipment.target===index)equipment.target=null;
    else if(equipment.target>index)equipment.target--;
  }
  return id;
}

function combatCounterGain(card,effectsForEvent){
  const effectResolver=typeof effectsForEvent==='function'?effectsForEvent:()=>[];
  return effectResolver(card,'combat-damage')
    .filter(effect=>effect.type==='add-power-counter')
    .reduce((sum,effect)=>sum+(effect.amount||0),0);
}

function combatPlan(combat,attackerPlayer,defenderPlayer,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const effectResolver=typeof effectsForEvent==='function'?effectsForEvent:()=>[];
  const attackerDeaths=new Set(),defenderDeaths=new Set(),attackerGains=new Map(),defenderGains=new Map(),exchanges=[];
  let damage=0;
  for(let slot=0;slot<(combat?.attackers||[]).length;slot++){
    const attacker=combat.attackers[slot],attackerCard=cardResolver(attackerPlayer?.battlefield?.[attacker.index]);
    const attackerPower=effectivePowerValue(attackerPlayer,attacker.index,cardResolver,effectResolver),attackerToughness=toughnessValue(attackerPlayer,attacker.index,cardResolver);
    const blockerIndex=combat?.blockers?.[String(slot)],blockerCard=blockerIndex==null?null:cardResolver(defenderPlayer?.battlefield?.[blockerIndex]);
    if(blockerCard){
      const blockerPower=effectivePowerValue(defenderPlayer,blockerIndex,cardResolver,effectResolver),blockerToughness=toughnessValue(defenderPlayer,blockerIndex,cardResolver);
      if(attackerPower>=blockerToughness)defenderDeaths.add(blockerIndex);
      if(blockerPower>=attackerToughness)attackerDeaths.add(attacker.index);
      const attackerGain=attackerPower>0?combatCounterGain(attackerCard,effectResolver):0,defenderGain=blockerPower>0?combatCounterGain(blockerCard,effectResolver):0;
      if(attackerGain)attackerGains.set(attacker.index,(attackerGains.get(attacker.index)||0)+attackerGain);
      if(defenderGain)defenderGains.set(blockerIndex,(defenderGains.get(blockerIndex)||0)+defenderGain);
      exchanges.push({attackerIndex:attacker.index,defenderIndex:blockerIndex,attackerName:attackerCard?.name||'',defenderName:blockerCard?.name||'',attackerPower,attackerToughness,defenderPower:blockerPower,defenderToughness:blockerToughness});
    }else{
      damage+=attackerPower;
      const attackerGain=attackerPower>0?combatCounterGain(attackerCard,effectResolver):0;
      if(attackerGain)attackerGains.set(attacker.index,(attackerGains.get(attacker.index)||0)+attackerGain);
    }
  }
  return {
    damage,
    exchanges,
    attackerDeaths:[...attackerDeaths],
    defenderDeaths:[...defenderDeaths],
    attackerCounterGains:[...attackerGains].filter(([index])=>!attackerDeaths.has(index)),
    defenderCounterGains:[...defenderGains].filter(([index])=>!defenderDeaths.has(index))
  };
}

global.SizaCreatureRules=Object.freeze({
  counter:counterValue,
  equipmentFor:equipmentForIndex,
  equipmentPowerBonus:equipmentPowerBonusValue,
  effectivePower:effectivePowerValue,
  toughness:toughnessValue,
  addCreature:addBattlefieldCreature,
  removeAt:removeBattlefieldCreature,
  combatPlan
});
})(window);
