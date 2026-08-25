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

global.SizaCreatureRules=Object.freeze({
  counter:counterValue,
  equipmentFor:equipmentForIndex,
  equipmentPowerBonus:equipmentPowerBonusValue,
  effectivePower:effectivePowerValue,
  toughness:toughnessValue,
  addCreature:addBattlefieldCreature,
  removeAt:removeBattlefieldCreature
});
})(window);
