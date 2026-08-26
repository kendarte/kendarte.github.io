(function(global){
'use strict';

const VERSION='1.16.0';
const EVENTS=Object.freeze(['resolve','enter','attack-declared','combat-damage','manifest-roll','equipped']);
const TYPES=Object.freeze(['draw','damage-character','counter-stack-target','observe-top','bounce-other-permanent','discard','add-power-counter','manifest-bonus','modify-power']);
const TARGETS=Object.freeze(['self','opponent']);
const COLORS=Object.freeze(['U','R','G','W','B']);
const EVENT_LABELS=Object.freeze({
 resolve:'Al resolverse',
 enter:'Al entrar en juego',
 'attack-declared':'Al declarar ataque',
 'combat-damage':'Al hacer daño de combate',
 'manifest-roll':'En una tirada de Manafestación',
 equipped:'Mientras está equipado'
});
const TARGET_LABELS=Object.freeze({self:'Propietario',opponent:'Rival'});
const COLOR_LABELS=Object.freeze({U:'Azul',R:'Rojo',G:'Verde',W:'Blanco',B:'Negro'});
const EDITOR_DEFINITIONS=Object.freeze({
 draw:Object.freeze({label:'Robar cartas',description:'Roba una cantidad de cartas.',defaultEvent:'resolve',defaults:Object.freeze({target:'self',amount:1}),fields:Object.freeze([
  Object.freeze({key:'target',kind:'target',label:'Quién roba'}),
  Object.freeze({key:'amount',kind:'number',label:'Cantidad',min:1,max:20,step:1})
 ])}),
 'damage-character':Object.freeze({label:'Daño a personaje',description:'Inflige daño directamente a un personaje.',defaultEvent:'resolve',defaults:Object.freeze({target:'opponent',amount:1}),fields:Object.freeze([
  Object.freeze({key:'target',kind:'target',label:'Objetivo'}),
  Object.freeze({key:'amount',kind:'number',label:'Daño',min:1,max:99,step:1})
 ])}),
 'counter-stack-target':Object.freeze({label:'Contrarrestar spell',description:'Contrarresta el objetivo actual del Stack.',defaultEvent:'resolve',defaults:Object.freeze({}),fields:Object.freeze([])}),
 'observe-top':Object.freeze({label:'Observar carta superior',description:'Observa la primera carta de la Library elegida.',defaultEvent:'enter',defaults:Object.freeze({target:'self'}),fields:Object.freeze([
  Object.freeze({key:'target',kind:'target',label:'Library'}),
 ])}),
 'bounce-other-permanent':Object.freeze({label:'Devolver otro permanente',description:'Devuelve otro permanente a la mano de su dueño.',defaultEvent:'enter',defaults:Object.freeze({}),fields:Object.freeze([])}),
 discard:Object.freeze({label:'Descartar carta',description:'Hace descartar una carta; el dueño elige cuando corresponde.',defaultEvent:'enter',defaults:Object.freeze({target:'self',amount:1,choice:'owner'}),fields:Object.freeze([
  Object.freeze({key:'target',kind:'target',label:'Quién descarta'})
 ])}),
 'add-power-counter':Object.freeze({label:'Ganar contador +1/+1',description:'Añade contadores permanentes de poder/resistencia.',defaultEvent:'combat-damage',defaults:Object.freeze({amount:1}),fields:Object.freeze([
  Object.freeze({key:'amount',kind:'number',label:'Contadores',min:1,max:20,step:1})
 ])}),
 'manifest-bonus':Object.freeze({label:'Bonificación de Manafestación',description:'Suma un bono a una tirada de Manafestación que cumpla el requisito.',defaultEvent:'manifest-roll',lockedEvent:true,defaults:Object.freeze({amount:1,requiresPip:'U',exhaustSource:true}),fields:Object.freeze([
  Object.freeze({key:'amount',kind:'number',label:'Bonificación',min:1,max:20,step:1}),
  Object.freeze({key:'requiresPip',kind:'color',label:'Requiere cristal'}),
  Object.freeze({key:'exhaustSource',kind:'boolean',label:'Agotar la fuente'})
 ])}),
 'modify-power':Object.freeze({label:'Modificar ataque equipado',description:'Modifica el ataque de la criatura equipada.',defaultEvent:'equipped',lockedEvent:true,defaults:Object.freeze({amount:1}),fields:Object.freeze([
  Object.freeze({key:'amount',kind:'number',label:'Ataque adicional',min:1,max:20,step:1})
 ])})
});

function text(value,fallback=''){return String(value??fallback);}
function integer(value,fallback=0){const n=Number(value);return Number.isFinite(n)?Math.trunc(n):fallback;}
function normalizeEffect(input={}){const type=TYPES.includes(input.type)?input.type:text(input.type,''),event=EVENTS.includes(input.event)?input.event:'resolve',effect={type,event};if(input.target!=null)effect.target=TARGETS.includes(input.target)?input.target:text(input.target);if(input.amount!=null)effect.amount=Math.max(0,integer(input.amount,0));if(input.choice!=null)effect.choice=text(input.choice);if(input.requiresPip!=null)effect.requiresPip=text(input.requiresPip).toUpperCase();if(input.exhaustSource!=null)effect.exhaustSource=!!input.exhaustSource;return effect;}
function normalizeEffects(input=[]){return Array.isArray(input)?input.map(normalizeEffect):[];}
function validateEffects(input=[]){const effects=normalizeEffects(input),errors=[],warnings=[];effects.forEach((effect,index)=>{const p=`effects[${index}]`;if(!TYPES.includes(effect.type))errors.push(`${p}: tipo de efecto inválido (${effect.type||'vacío'}).`);if(!EVENTS.includes(effect.event))errors.push(`${p}: evento inválido (${effect.event||'vacío'}).`);if(['draw','damage-character','discard','add-power-counter','manifest-bonus','modify-power'].includes(effect.type)&&(!Number.isInteger(effect.amount)||effect.amount<=0))errors.push(`${p}: ${effect.type} requiere amount > 0.`);if(['draw','damage-character','discard'].includes(effect.type)&&effect.target&&!TARGETS.includes(effect.target))errors.push(`${p}: target inválido (${effect.target}).`);if(effect.type==='discard'&&effect.amount!==1)errors.push(`${p}: el runtime actual sólo admite discard amount=1.`);if(effect.type==='discard'&&effect.choice&&effect.choice!=='owner')errors.push(`${p}: discard sólo admite choice=owner.`);if(effect.type==='manifest-bonus'&&effect.event!=='manifest-roll')errors.push(`${p}: manifest-bonus requiere event=manifest-roll.`);if(effect.type==='modify-power'&&effect.event!=='equipped')errors.push(`${p}: modify-power requiere event=equipped.`);if(effect.requiresPip&&!COLORS.includes(effect.requiresPip))errors.push(`${p}: requiresPip inválido (${effect.requiresPip}).`);if(effect.type==='damage-character'&&!effect.target)warnings.push(`${p}: damage-character sin target usa opponent por contrato runtime.`);if(effect.type==='draw'&&!effect.target)warnings.push(`${p}: draw sin target usa self por contrato runtime.`);});return{valid:errors.length===0,errors,warnings,effects};}
function editorDefinition(type){return EDITOR_DEFINITIONS[type]||null;}
function newEffect(type,event=null){
 const def=editorDefinition(type);if(!def)return normalizeEffect({type,event:event||'resolve'});
 return normalizeEffect({type,event:event||def.defaultEvent,...def.defaults});
}
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
function preferredPermanentTarget(targets=[],preferredOwner='player'){return targets.find(target=>target.owner===preferredOwner)||targets[0]||null;}
function bouncePlan(target={}){
  const zone=target.zone||'battlefield';
  return{owner:target.owner,zone,index:target.index,destination:'hand',zoneLabel:zone==='equipment'?'Equipo':zone==='artifacts'?'Reliquias':'Invocaciones'};
}
function stackTargetIndex(stack,targetStackId){
  const index=stack.findIndex(entry=>entry.id===targetStackId);
  return index>=0?index:stack.length-1;
}
function runtimePlan(effect,context={}){
  const match=context.match,sourceOwner=context.sourceOwner,opponentOwner=sourceOwner==='player'?'enemy':'player';
  const targetOwner=defaultTarget=>effectSide(effect.target,sourceOwner,opponentOwner,defaultTarget);
  if(effect.type==='counter-stack-target')return{kind:'counter-stack-target',terminal:true,stackIndex:stackTargetIndex(match.stack,context.targetStackId)};
  if(effect.type==='draw')return{kind:'draw',terminal:false,targetOwner:targetOwner('self'),amount:effect.amount||1,logResolve:effect.event==='resolve'};
  if(effect.type==='damage-character')return{kind:'damage-character',terminal:false,targetOwner:targetOwner('opponent'),amount:effect.amount||1};
  if(effect.type==='observe-top'){
    const owner=targetOwner('self'),topCardId=match[owner].library[0];
    return{kind:'observe-top',terminal:false,targetOwner:owner,topCardId,action:topCardId?(sourceOwner==='player'&&owner===sourceOwner?'choice':'log'):'none'};
  }
  if(effect.type==='bounce-other-permanent'){
    const targets=otherPermanentTargets(match,sourceOwner,context.entryIndex),action=!targets.length?'none':sourceOwner==='player'?'choice':'bounce';
    return{kind:'bounce-other-permanent',terminal:false,targets,action,preferredTarget:action==='bounce'?preferredPermanentTarget(targets,'player'):null};
  }
  if(effect.type==='discard'){
    const owner=targetOwner('self'),target=match[owner],action=effect.amount!==1?'none':sourceOwner==='player'&&owner===sourceOwner?'choice':target.hand.length?'discard-last':'none';
    return{kind:'discard',terminal:false,targetOwner:owner,amount:effect.amount,action};
  }
  return{kind:effect.type,terminal:false};
}
function preferredResponseCard(hand=[],resolveCard,canPay){
  return hand.map((id,index)=>({i:index,c:resolveCard(id)}))
    .filter(entry=>entry.c?.type==='Instant'&&canPay(entry.c))
    .sort((a,b)=>(hasEffect(a.c,'counter-stack-target','resolve')?-1:0)-(hasEffect(b.c,'counter-stack-target','resolve')?-1:0))[0]||null;
}
function preferredMainPhaseCard(hand=[],resolveCard,canPay){
  return hand.map((id,index)=>({i:index,c:resolveCard(id)}))
    .filter(entry=>entry.c?.type!=='Land'&&!hasEffect(entry.c,'counter-stack-target','resolve')&&canPay(entry.c))
    .sort((a,b)=>a.c.difficulty-b.c.difficulty)[0];
}
function priorityWindowPlan(sourceOwner){
  const responder=sourceOwner==='player'?'enemy':'player';
  return{responder,active:responder==='player'?'response':'enemy-response',phase:responder==='player'?'Tu prioridad':'Prioridad rival'};
}
function priorityPassPlan(responseWindow,owner){
  if(responseWindow?.responder!==owner)return null;
  return{responseWindow:null,pendingResolution:true,active:'resolving',phase:'Stack listo'};
}
function stackCompletionPlan(match={}){
  if(match.over)return{kind:'over'};
  if(match.pendingChoice)return{kind:'choice',active:'choice'};
  const owner=match.stackReturnOwner||'player',enemy=owner==='enemy';
  return{kind:'return',stackReturnOwner:null,active:enemy?'enemy':'player',phase:enemy?'Main rival':'Main',scheduleEnemy:enemy};
}
function shouldContinueStackResolution(match,resolvedCount,limit=30){return !!(match.stack.length&&!match.pendingChoice&&!match.over&&resolvedCount<limit);}
function matchWinner(playerLife,enemyLife){return playerLife<=0||enemyLife<=0?(playerLife>0?'player':'enemy'):null;}
global.SizaCardEffects=Object.freeze({VERSION,EVENTS,TYPES,TARGETS,COLORS,EVENT_LABELS,TARGET_LABELS,COLOR_LABELS,EDITOR_DEFINITIONS,editorDefinition,newEffect,normalizeEffect,normalizeEffects,validateEffects,forEvent,hasEffect,sumAmount,effectSide,otherPermanentTargets,preferredPermanentTarget,bouncePlan,stackTargetIndex,runtimePlan,preferredResponseCard,preferredMainPhaseCard,priorityWindowPlan,priorityPassPlan,stackCompletionPlan,shouldContinueStackResolution,matchWinner});
})(window);
