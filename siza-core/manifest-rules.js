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
  const cost=card?.cost||0;
  return card?.difficulty??(4+Math.ceil((cost+1)/2));
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

global.SizaManifestRules=Object.freeze({affinityInfo,dcFor,naturalChance,manifestRequirement,deficit,bonusSources});
})(window);
