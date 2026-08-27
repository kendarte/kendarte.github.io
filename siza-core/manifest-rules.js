(function(global){
'use strict';

function affinityInfo(card,mag){
  let penalty=0,unsupported=[];
  for(const [key,value] of Object.entries(card?.pips||{})){
    if(value<=0)continue;
    const affinity=mag?.aff?.[key]||0;
    if(affinity===0)unsupported.push(key);
    else if(value>affinity)penalty+=value-affinity;
  }
  return {penalty,unsupported};
}

function dcFor(card,mag){
  const info=affinityInfo(card,mag);
  if(info.unsupported.length)return Infinity;
  if(card?.type==='Land')return 0;
  const difficulty=Number(card?.difficulty);
  return Number.isFinite(difficulty)&&difficulty>0?difficulty:Infinity;
}

function naturalChance(card,mag){
  if(card?.type==='Land')return 100;
  const dc=dcFor(card,mag);
  if(!isFinite(dc))return 0;
  const need=dc-(mag?.mf||0);
  if(need<=1)return 100;
  if(need>6)return 0;
  return Math.round((7-need)/6*100);
}

function manifestRequirement(card,mag){
  const dc=dcFor(card,mag);
  if(!isFinite(dc))return {unsupported:true,text:'SIN AFINIDAD',die:0,minBurn:0};
  const raw=dc-(mag?.mf||0),minBurn=Math.max(0,raw-6),die=Math.max(1,Math.min(6,raw));
  return {unsupported:false,die,minBurn,text:minBurn?`${die}+ · Burn mínimo ${minBurn}`:`${die}+`};
}

function deficit(modal,player){
  return Math.max(0,modal.dc-(player.mf+(modal.roll||0)+(modal.prismBonus||0)+(modal.burnSelected?.length||0)));
}

function bonusSources(player,card,resolveCard,effectsForEvent){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const effectResolver=typeof effectsForEvent==='function'?effectsForEvent:()=>[];
  const spent=new Set(player?.artifactExhausted||[]),out=[];
  (player?.artifacts||[]).forEach((id,index)=>{
    if(spent.has(index))return;
    const source=cardResolver(id);
    for(const effect of effectResolver(source,'manifest-roll')){
      if(effect.type!=='manifest-bonus'||!(effect.amount>0))continue;
      if(effect.requiresPip&&!(card?.pips?.[effect.requiresPip]>0))continue;
      out.push({index,id,source,effect});
    }
  });
  return out;
}

function aiManifestRollPlan(modal,player,landIndexes=[],bonusSource=null){
  let need=deficit(modal,player);
  const bonus=need===1&&bonusSource?bonusSource:null;
  if(bonus)need=Math.max(0,need-bonus.effect.amount);
  const lands=Array.isArray(landIndexes)?landIndexes:[];
  return need<=lands.length
    ?{bonus,burnSelected:lands.slice(0,need),aiFailure:false}
    :{bonus,burnSelected:null,aiFailure:true};
}

function burnSelectionPlan(modal,player,handIndex,isLand){
  if(!modal||modal.roll==null||modal.ai||!isLand||handIndex===modal.idx)return null;
  const selected=Array.isArray(modal.burnSelected)?modal.burnSelected.slice():[];
  const need=Math.max(0,modal.dc-(player.mf+modal.roll+(modal.prismBonus||0)));
  const at=selected.indexOf(handIndex);
  if(at>=0)selected.splice(at,1);
  else if(selected.length<need)selected.push(handIndex);
  return selected;
}

function burnConsumptionPlan(modal){
  const indices=modal.burnSelected.slice().sort((a,b)=>b-a);
  let manifestIndex=modal.idx;
  for(const index of indices)if(index<manifestIndex)manifestIndex--;
  return {indices,manifestIndex};
}

function manifestOutcome(modal,player){
  const burn=modal.burnSelected.length;
  const total=player.mf+modal.roll+modal.prismBonus+burn;
  return {burn,total,success:total>=modal.dc};
}

function manifestStackPlan(modal,player,card,hasEffect){
  return {
    cardId:player.hand[modal.idx],
    owner:modal.owner,
    targetStackId:modal.reactive&&hasEffect(card,'counter-stack-target','resolve')?modal.targetStackId:null
  };
}

function manifestFailurePlan(modal,player){
  const total=player.mf+modal.roll+modal.prismBonus;
  return {
    total,
    resume:modal.reactive?'priority':modal.owner==='enemy'?'enemy':'none'
  };
}

global.SizaManifestRules=Object.freeze({affinityInfo,dcFor,naturalChance,manifestRequirement,deficit,bonusSources,aiManifestRollPlan,burnSelectionPlan,burnConsumptionPlan,manifestOutcome,manifestStackPlan,manifestFailurePlan});
})(window);
