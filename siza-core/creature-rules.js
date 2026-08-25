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

global.SizaCreatureRules=Object.freeze({
  counter:counterValue,
  equipmentFor:equipmentForIndex,
  equipmentPowerBonus:equipmentPowerBonusValue,
  effectivePower:effectivePowerValue,
  toughness:toughnessValue
});
})(window);
