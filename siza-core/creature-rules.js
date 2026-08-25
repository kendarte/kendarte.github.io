(function(global){
'use strict';

function counter(player,index){
  return player?.powerCounters?.[index]||0;
}

function equipmentFor(player,index){
  return (player?.equipment||[]).filter(entry=>entry.target===index);
}

function equipmentPowerBonus(player,index,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const effectResolver=typeof effectsForEvent==='function'?effectsForEvent:()=>[];
  return equipmentFor(player,index).reduce((sum,entry)=>{
    const card=cardResolver(entry.id);
    return sum+effectResolver(card,'equipped')
      .filter(effect=>effect.type==='modify-power')
      .reduce((subtotal,effect)=>subtotal+(effect.amount||0),0);
  },0);
}

function effectivePower(player,index,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const card=cardResolver(player?.battlefield?.[index]);
  return (card?.power||0)+counter(player,index)+equipmentPowerBonus(player,index,cardResolver,effectsForEvent);
}

function toughness(player,index,resolveCard){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const card=cardResolver(player?.battlefield?.[index]);
  return (card?.toughness||0)+counter(player,index);
}

global.SizaCreatureRules=Object.freeze({counter,equipmentFor,equipmentPowerBonus,effectivePower,toughness});
})(window);
