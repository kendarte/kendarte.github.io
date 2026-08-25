(function(global){
'use strict';

const MODES=Object.freeze({
  immediate:Object.freeze({short:'ENTRADA INMEDIATA',text:'Todas pueden atacar al entrar.'}),
  prepare:Object.freeze({short:'PREPARACIÓN UNIVERSAL',text:'Esperan hasta el próximo turno propio.'}),
  oneCrystal:Object.freeze({short:'IMPULSO DE 1 CRISTAL',text:'Las de un cristal atacan al entrar.'})
});

function normalizeMode(mode){
  return Object.prototype.hasOwnProperty.call(MODES,mode)?mode:'prepare';
}

function isPreparing(player,index,mode,resolveCard,spellCost){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const costResolver=typeof spellCost==='function'?spellCost:()=>0;
  const card=cardResolver(player?.battlefield?.[index]);
  const born=player?.summonedOn?.[index]??player?.ownTurn;
  const activeMode=mode||'prepare';
  if(born<player?.ownTurn||activeMode==='immediate')return false;
  if(activeMode==='oneCrystal'&&costResolver(card)===1)return false;
  return true;
}

function canAttack(player,index,mode,resolveCard,spellCost){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  const card=cardResolver(player?.battlefield?.[index]);
  return card?.type==='Creature'&&!(player?.exhausted||[]).includes(index)&&!isPreparing(player,index,mode,cardResolver,spellCost);
}

function availableAttackers(player,mode,resolveCard,spellCost){
  return (player?.battlefield||[]).map((_,index)=>canAttack(player,index,mode,resolveCard,spellCost)?index:-1).filter(index=>index>=0);
}

function legalBlockers(player,resolveCard){
  const cardResolver=typeof resolveCard==='function'?resolveCard:()=>null;
  return (player?.battlefield||[]).map((id,index)=>cardResolver(id)?.type==='Creature'&&!(player?.exhausted||[]).includes(index)?index:-1).filter(index=>index>=0);
}

global.SizaEntryRules=Object.freeze({MODES,normalizeMode,isPreparing,canAttack,availableAttackers,legalBlockers});
})(window);
