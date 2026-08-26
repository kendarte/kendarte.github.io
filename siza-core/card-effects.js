(function(global){
'use strict';

const VERSION='1.6.0';
const EVENTS=Object.freeze(['resolve','enter','attack-declared','combat-damage','manifest-roll','equipped']);
const TYPES=Object.freeze(['draw','damage-character','counter-stack-target','observe-top','bounce-other-permanent','discard','add-power-counter','manifest-bonus','modify-power']);
const TARGETS=Object.freeze(['self','opponent']);
const COLORS=Object.freeze(['U','R','G','W','B']);

function text(value,fallback=''){return String(value??fallback);}
function integer(value,fallback=0){const n=Number(value);return Number.isFinite(n)?Math.trunc(n):fallback;}
function normalizeEffect(input={}){const type=TYPES.includes(input.type)?input.type:text(input.type,''),event=EVENTS.includes(input.event)?input.event:'resolve',effect={type,event};if(input.target!=null)effect.target=TARGETS.includes(input.target)?input.target:text(input.target);if(input.amount!=null)effect.amount=Math.max(0,integer(input.amount,0));if(input.choice!=null)effect.choice=text(input.choice);if(input.requiresPip!=null)effect.requiresPip=text(input.requiresPip).toUpperCase();if(input.exhaustSource!=null)effect.exhaustSource=!!input.exhaustSource;return effect;}
function normalizeEffects(input=[]){return Array.isArray(input)?input.map(normalizeEffect):[];}
function validateEffects(input=[]){const effects=normalizeEffects(input),errors=[],warnings=[];effects.forEach((effect,index)=>{const p=`effects[${index}]`;if(!TYPES.includes(effect.type))errors.push(`${p}: tipo de efecto inválido (${effect.type||'vacío'}).`);if(!EVENTS.includes(effect.event))errors.push(`${p}: evento inválido (${effect.event||'vacío'}).`);if(['draw','damage-character','discard','add-power-counter','manifest-bonus','modify-power'].includes(effect.type)&&(!Number.isInteger(effect.amount)||effect.amount<=0))errors.push(`${p}: ${effect.type} requiere amount > 0.`);if(['draw','damage-character','discard'].includes(effect.type)&&effect.target&&!TARGETS.includes(effect.target))errors.push(`${p}: target inválido (${effect.target}).`);if(effect.type==='discard'&&effect.amount!==1)errors.push(`${p}: el runtime actual sólo admite discard amount=1.`);if(effect.type==='discard'&&effect.choice&&effect.choice!=='owner')errors.push(`${p}: discard sólo admite choice=owner.`);if(effect.type==='manifest-bonus'&&effect.event!=='manifest-roll')errors.push(`${p}: manifest-bonus requiere event=manifest-roll.`);if(effect.type==='modify-power'&&effect.event!=='equipped')errors.push(`${p}: modify-power requiere event=equipped.`);if(effect.requiresPip&&!COLORS.includes(effect.requiresPip))errors.push(`${p}: requiresPip inválido (${effect.requiresPip}).`);if(effect.type==='damage-character'&&!effect.target)warnings.push(`${p}: damage-character sin target usa opponent por contrato runtime.`);if(effect.type==='draw'&&!effect.target)warnings.push(`${p}: draw sin target usa self por contrato runtime.`);});return{valid:errors.length===0,errors,warnings,effects};}
function forEvent(card,event){return normalizeEffects(card?.effects).filter(effect=>effect.event===event);}
function hasEffect(card,type,event=null){const list=event?forEvent(card,event):normalizeEffects(card?.effects);return list.some(effect=>effect.type===type);}
function sumAmount(card,event,type){return forEvent(card,event).filter(effect=>effect.type===type).reduce((sum,effect)=>sum+(effect.amount||0),0);}
function effectSide(target,selfSide,opponentSide,defaultTarget='self'){const resolved=target||defaultTarget;return resolved==='opponent'?opponentSide:selfSide;}
function otherPermanentTargets(match,sourceOwner,entryIndex=null){
  const targets=[];
  for(const owner of ['player','enemy']){
    const player=match[owner];
    player.battlefield.forEach((id,index)=>{if(!(owner===sourceOwner&&index===entryIndex))targets.push({owner,zone:'battlefield',index,id});});
    player.artifacts.forEach((id,index)=>targets.push({owner,zone:'artifacts',index,id}));
    player.equipment.forEach((entry,index)=>targets.push({owner,zone:'equipment',index,id:entry.id}));
  }
  return targets;
}
function stackTargetIndex(stack,targetStackId){
  const index=stack.findIndex(entry=>entry.id===targetStackId);
  return index>=0?index:stack.length-1;
}
global.SizaCardEffects=Object.freeze({VERSION,EVENTS,TYPES,TARGETS,COLORS,normalizeEffect,normalizeEffects,validateEffects,forEvent,hasEffect,sumAmount,effectSide,otherPermanentTargets,stackTargetIndex});
})(window);
