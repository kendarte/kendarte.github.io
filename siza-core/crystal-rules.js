(function(global){
'use strict';

const COLORS=Object.freeze(['U','R','G','W','B']);

function crystalReq(card){
  const req={};
  for(const [key,count] of Object.entries(card?.pips||{}))if(count>0)req[key]=count;
  return req;
}

function spellCost(card){
  if(card?.type==='Land')return 0;
  return Math.max(1,Object.values(crystalReq(card)).reduce((sum,count)=>sum+count,0));
}

function directPlan(player,card){
  const req=crystalReq(card),spent={};
  for(const [key,count] of Object.entries(req)){
    if((player?.crystals?.[key]||0)<count)return null;
    spent[key]=count;
  }
  if(!Object.keys(req).length){
    const options=COLORS.filter(key=>(player?.crystals?.[key]||0)>0);
    return options.length?{kind:'flex',options}:null;
  }
  return {kind:'direct',spent};
}

function offeringPlan(player,card,resolveCard){
  const req=crystalReq(card),spent={},missing=[];
  let need=0;
  for(const [key,count] of Object.entries(req)){
    need+=count;
    const have=player?.crystals?.[key]||0;
    spent[key]=Math.min(have,count);
    for(let i=have;i<count;i++)missing.push(key);
  }
  if(missing.length!==1||Object.values(player?.crystals||{}).reduce((sum,count)=>sum+count,0)<need||player?.offeringUsed)return null;
  const missingColor=missing[0];
  const substitute=COLORS.find(key=>key!==missingColor&&(player?.crystals?.[key]||0)>(spent[key]||0));
  if(!substitute)return null;
  spent[substitute]=(spent[substitute]||0)+1;
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const candidates=(player?.battlefield||[])
    .map((id,index)=>({id,index,c:cardResolver(id)}))
    .filter(entry=>(entry.c?.pips?.[missingColor]||0)>0&&(player?.summonedOn?.[entry.index]??player?.ownTurn)<player?.ownTurn&&!(player?.exhausted||[]).includes(entry.index));
  return candidates.length?{kind:'offering',spent,missing:missingColor,candidates}:null;
}

function paymentPlan(player,card,resolveCard){
  return directPlan(player,card)||offeringPlan(player,card,resolveCard);
}

function resetPool(player){
  player.crystals={};
  for(const [key,count] of Object.entries(player?.aff||{}))if(count>0)player.crystals[key]=count;
  player.offeringUsed=false;
  player.artifactExhausted=[];
}

function spend(player,spent){
  for(const [key,count] of Object.entries(spent||{}))if((player?.crystals?.[key]||0)<count)return false;
  for(const [key,count] of Object.entries(spent||{}))player.crystals[key]-=count;
  return true;
}

global.SizaCrystalRules=Object.freeze({COLORS,crystalReq,spellCost,directPlan,offeringPlan,paymentPlan,resetPool,spend});
})(window);
