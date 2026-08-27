(function(global){
'use strict';

const VERSION='1.21.0';
const EVENTS=Object.freeze(['resolve','enter','leave','dies','cast','attack-declared','block-declared','becomes-blocked','combat-damage','upkeep','draw-step','end-step','card-drawn','card-discarded','life-gained','life-lost','permanent-tapped','permanent-untapped','manifest-roll','equipped']);
const TARGETS=Object.freeze(['self','opponent']);
const COLORS=Object.freeze(['U','R','G','W','B']);
const EVENT_LABELS=Object.freeze({resolve:'Al resolverse',enter:'Al entrar en juego',leave:'Al dejar el campo',dies:'Al morir',cast:'Al lanzarse','attack-declared':'Al declarar ataque','block-declared':'Al declarar bloqueo','becomes-blocked':'Al ser bloqueado','combat-damage':'Al hacer daño de combate',upkeep:'En mantenimiento','draw-step':'En paso de robo','end-step':'Al final del turno','card-drawn':'Al robar una carta','card-discarded':'Al descartar una carta','life-gained':'Al ganar vida','life-lost':'Al perder vida','permanent-tapped':'Al agotarse un permanente','permanent-untapped':'Al enderezarse un permanente','manifest-roll':'En una tirada de Manafestación',equipped:'Mientras está equipado'});
const TARGET_LABELS=Object.freeze({self:'Propietario',opponent:'Rival'});
const COLOR_LABELS=Object.freeze({U:'Azul',R:'Rojo',G:'Verde',W:'Blanco',B:'Negro'});
const KEYWORDS=Object.freeze(['flying','first-strike','double-strike','deathtouch','lifelink','vigilance','trample','haste','reach','menace','hexproof','indestructible','defender','flash','ward','protection','prowess']);
const KEYWORD_LABELS=Object.freeze({'flying':'Volar','first-strike':'Dañar primero','double-strike':'Dañar dos veces',deathtouch:'Toque mortal',lifelink:'Vínculo vital',vigilance:'Vigilancia',trample:'Arrollar',haste:'Prisa',reach:'Alcance',menace:'Amenaza',hexproof:'Antimaleficio',indestructible:'Indestructible',defender:'Defensor',flash:'Destello',ward:'Ward / Salvaguarda',protection:'Protección',prowess:'Destreza'});
const ZONES=Object.freeze(['library','hand','battlefield','graveyard','exile']);
const ZONE_LABELS=Object.freeze({library:'Library',hand:'Mano',battlefield:'Campo',graveyard:'Cementerio',exile:'Exilio'});
const TARGET_SCOPES=Object.freeze(['source','target-creature','target-permanent','target-artifact','target-player','each-creature-self','each-creature-opponent','each-creature','random-creature-opponent']);
const TARGET_SCOPE_LABELS=Object.freeze({source:'Esta carta','target-creature':'Criatura objetivo','target-permanent':'Permanente objetivo','target-artifact':'Artefacto objetivo','target-player':'Jugador objetivo','each-creature-self':'Todas tus criaturas','each-creature-opponent':'Todas las criaturas rivales','each-creature':'Todas las criaturas','random-creature-opponent':'Criatura rival aleatoria'});
const CARD_FILTERS=Object.freeze(['any','creature','artifact','instant','land','nonland','basic-land']);
const CARD_FILTER_LABELS=Object.freeze({any:'Cualquier carta',creature:'Criatura',artifact:'Artefacto',instant:'Reacción / Instant',land:'Reserva / Land',nonland:'No-Land','basic-land':'Land básica'});
const DURATIONS=Object.freeze(['permanent','end-of-turn','while-equipped','until-source-leaves']);
const DURATION_LABELS=Object.freeze({permanent:'Permanente','end-of-turn':'Hasta fin de turno','while-equipped':'Mientras esté equipado','until-source-leaves':'Hasta que la fuente deje el campo'});
const COUNTERS=Object.freeze(['plus1-plus1','minus1-minus1','charge','shield','stun','custom']);
const COUNTER_LABELS=Object.freeze({'plus1-plus1':'+1/+1','minus1-minus1':'-1/-1',charge:'Carga',shield:'Escudo',stun:'Aturdimiento',custom:'Personalizado'});

const WIRED_TYPES=new Set(['draw','damage-character','counter-stack-target','observe-top','bounce-other-permanent','discard','add-power-counter','manifest-bonus','modify-power']);
const def=(label,category,description,defaultEvent,fields=[],defaults={},extra={})=>Object.freeze({label,category,description,defaultEvent,fields:Object.freeze(fields.map(Object.freeze)),defaults:Object.freeze(defaults),runtime:WIRED_TYPES.has(extra.type)?'wired':(extra.runtime||'authoring'),...extra});
const numField=(key,label,min=1,max=99)=>({key,kind:'number',label,min,max,step:1});
const targetField=(label='Jugador')=>({key:'target',kind:'target',label});
const scopeField=(label='Objetivo')=>({key:'targetScope',kind:'select',label,options:TARGET_SCOPE_LABELS});
const zoneField=(key,label)=>({key,kind:'select',label,options:ZONE_LABELS});
const filterField=(label='Filtro de carta')=>({key:'cardFilter',kind:'select',label,options:CARD_FILTER_LABELS});
const durationField=()=>({key:'duration',kind:'select',label:'Duración',options:DURATION_LABELS});

const EDITOR_DEFINITIONS=Object.freeze({
 draw:def('Robar cartas','Cartas','Roba una cantidad de cartas.','resolve',[targetField('Quién roba'),numField('amount','Cantidad',1,20)],{target:'self',amount:1},{type:'draw'}),
 discard:def('Descartar cartas','Cartas','Hace descartar cartas.','resolve',[targetField('Quién descarta'),numField('amount','Cantidad',1,20)],{target:'opponent',amount:1,choice:'owner'},{type:'discard'}),
 mill:def('Moler / enviar Library al cementerio','Cartas','Mueve cartas superiores de la Library al cementerio.','resolve',[targetField('Library de'),numField('amount','Cartas',1,100)],{target:'opponent',amount:3}),
 scry:def('Scry / adivinar','Cartas','Mira cartas superiores y permite reordenar/mandar al fondo.','resolve',[targetField('Quién hace Scry'),numField('amount','Cartas',1,10)],{target:'self',amount:1}),
 surveil:def('Surveil / escrutar','Cartas','Mira cartas superiores y permite mandarlas al cementerio.','resolve',[targetField('Quién hace Surveil'),numField('amount','Cartas',1,10)],{target:'self',amount:1}),
 loot:def('Robar y luego descartar','Cartas','Roba cartas y luego descarta cartas.','resolve',[targetField('Jugador'),numField('amount','Cantidad',1,10)],{target:'self',amount:1}),
 rummage:def('Descartar y luego robar','Cartas','Descarta cartas y después roba la misma cantidad.','resolve',[targetField('Jugador'),numField('amount','Cantidad',1,10)],{target:'self',amount:1}),
 tutor:def('Buscar en Library','Cartas','Busca una carta con filtro y la mueve al destino.','resolve',[targetField('Library de'),filterField(),zoneField('destination','Destino'),numField('amount','Cantidad',1,10)],{target:'self',cardFilter:'any',destination:'hand',amount:1}),
 'reveal-top':def('Revelar cartas superiores','Cartas','Revela cartas de la parte superior de una Library.','resolve',[targetField('Library de'),numField('amount','Cartas',1,20)],{target:'self',amount:1}),
 'observe-top':def('Observar carta superior','Cartas','Observa la primera carta de una Library.','enter',[targetField('Library de')],{target:'self'},{type:'observe-top'}),
 'reorder-top':def('Reordenar cartas superiores','Cartas','Permite ordenar las primeras cartas de una Library.','resolve',[targetField('Library de'),numField('amount','Cartas',2,20)],{target:'self',amount:3}),
 'shuffle-library':def('Barajar Library','Cartas','Baraja la Library indicada.','resolve',[targetField('Library de')],{target:'self'}),

 'damage-character':def('Daño a personaje','Vida y daño','Inflige daño directamente a un personaje.','resolve',[targetField('Objetivo'),numField('amount','Daño',1,99)],{target:'opponent',amount:1},{type:'damage-character'}),
 'damage-target':def('Daño a objetivo','Vida y daño','Inflige daño a criatura, permanente o jugador según objetivo.','resolve',[scopeField(),numField('amount','Daño',1,99)],{targetScope:'target-creature',amount:1}),
 'gain-life':def('Ganar vida','Vida y daño','Un jugador gana vida.','resolve',[targetField('Jugador'),numField('amount','Vida',1,99)],{target:'self',amount:3}),
 'lose-life':def('Perder vida','Vida y daño','Un jugador pierde vida sin tratarse como daño.','resolve',[targetField('Jugador'),numField('amount','Vida',1,99)],{target:'opponent',amount:1}),
 'prevent-damage':def('Prevenir daño','Vida y daño','Previene la próxima cantidad de daño.','resolve',[scopeField(),numField('amount','Previene',1,99),durationField()],{targetScope:'source',amount:1,duration:'end-of-turn'}),
 fight:def('Pelear','Vida y daño','Dos criaturas se hacen daño igual a su ataque.','resolve',[scopeField('Primera criatura'),{key:'secondTargetScope',kind:'select',label:'Segunda criatura',options:TARGET_SCOPE_LABELS}],{targetScope:'source',secondTargetScope:'target-creature'}),

 'destroy-target':def('Destruir objetivo','Permanentes','Destruye una criatura/permanente objetivo.','resolve',[scopeField()],{targetScope:'target-creature'}),
 'exile-target':def('Exiliar objetivo','Permanentes','Exilia una criatura/permanente objetivo.','resolve',[scopeField()],{targetScope:'target-creature'}),
 'bounce-other-permanent':def('Devolver otro permanente','Permanentes','Devuelve otro permanente a la mano de su dueño.','enter',[],{},{type:'bounce-other-permanent'}),
 'return-target-to-hand':def('Devolver objetivo a la mano','Permanentes','Devuelve un objetivo desde el campo a la mano.','resolve',[scopeField()],{targetScope:'target-creature'}),
 sacrifice:def('Sacrificar','Permanentes','Hace sacrificar permanentes.','resolve',[targetField('Controlador'),filterField(),numField('amount','Cantidad',1,20)],{target:'self',cardFilter:'creature',amount:1}),
 'tap-target':def('Agotar / girar objetivo','Permanentes','Agota uno o más permanentes.','resolve',[scopeField(),numField('amount','Cantidad',1,20)],{targetScope:'target-creature',amount:1}),
 'untap-target':def('Enderezar objetivo','Permanentes','Endereza uno o más permanentes.','resolve',[scopeField(),numField('amount','Cantidad',1,20)],{targetScope:'target-creature',amount:1}),
 'freeze-target':def('No se endereza próximo turno','Permanentes','El objetivo no se endereza en el próximo paso normal.','resolve',[scopeField()],{targetScope:'target-creature'}),
 'gain-control':def('Ganar control','Permanentes','Cambia el controlador de un permanente.','resolve',[scopeField(),durationField()],{targetScope:'target-creature',duration:'permanent'}),

 'create-token':def('Crear token','Tokens','Crea tokens de criatura configurables.','resolve',[numField('amount','Cantidad',1,50),{key:'tokenName',kind:'text',label:'Nombre del token'},{key:'tokenPower',kind:'number',label:'Ataque',min:0,max:99,step:1},{key:'tokenToughness',kind:'number',label:'Defensa',min:0,max:99,step:1}],{amount:1,tokenName:'Token',tokenPower:1,tokenToughness:1}),
 'create-resource-token':def('Crear token de recurso','Tokens','Crea fichas de recurso tipo Tesoro/Pista/Comida o equivalente Siza.','resolve',[numField('amount','Cantidad',1,50),{key:'tokenName',kind:'text',label:'Tipo de recurso'}],{amount:1,tokenName:'Tesoro'}),
 'copy-permanent':def('Copiar permanente','Tokens','Crea una copia de un permanente.','resolve',[scopeField(),numField('amount','Copias',1,20)],{targetScope:'target-creature',amount:1}),

 'add-power-counter':def('Ganar contador +1/+1','Contadores','Añade contadores permanentes +1/+1.','combat-damage',[numField('amount','Contadores',1,20)],{amount:1},{type:'add-power-counter'}),
 'add-counter':def('Agregar contador','Contadores','Añade un tipo de contador a un objetivo.','resolve',[scopeField(),{key:'counterType',kind:'select',label:'Tipo de contador',options:COUNTER_LABELS},numField('amount','Cantidad',1,50)],{targetScope:'target-creature',counterType:'plus1-plus1',amount:1}),
 'remove-counter':def('Quitar contador','Contadores','Quita contadores de un objetivo.','resolve',[scopeField(),{key:'counterType',kind:'select',label:'Tipo de contador',options:COUNTER_LABELS},numField('amount','Cantidad',1,50)],{targetScope:'target-creature',counterType:'plus1-plus1',amount:1}),

 'modify-stats':def('Modificar Ataque/Defensa','Combate','Da +X/+Y o valores negativos a un objetivo.','resolve',[scopeField(),{key:'powerDelta',kind:'number',label:'Ataque ±',min:-99,max:99,step:1},{key:'toughnessDelta',kind:'number',label:'Defensa ±',min:-99,max:99,step:1},durationField()],{targetScope:'target-creature',powerDelta:1,toughnessDelta:1,duration:'end-of-turn'}),
 'set-power-toughness':def('Fijar Ataque/Defensa','Combate','Fija los stats base a valores concretos.','resolve',[scopeField(),{key:'powerValue',kind:'number',label:'Ataque',min:0,max:99,step:1},{key:'toughnessValue',kind:'number',label:'Defensa',min:0,max:99,step:1},durationField()],{targetScope:'target-creature',powerValue:1,toughnessValue:1,duration:'end-of-turn'}),
 'switch-power-toughness':def('Intercambiar Ataque/Defensa','Combate','Intercambia Ataque y Defensa.','resolve',[scopeField(),durationField()],{targetScope:'target-creature',duration:'end-of-turn'}),
 'modify-power':def('Modificar ataque equipado','Combate','Modifica el ataque de la criatura equipada.','equipped',[numField('amount','Ataque adicional',1,20)],{amount:1},{type:'modify-power',lockedEvent:true}),
 'grant-keyword':def('Otorgar keyword','Combate','Otorga una habilidad de combate/keyword.','resolve',[scopeField(),{key:'keyword',kind:'select',label:'Keyword',options:KEYWORD_LABELS},durationField()],{targetScope:'target-creature',keyword:'flying',duration:'end-of-turn'}),
 'remove-keyword':def('Quitar keyword','Combate','Quita una keyword de un objetivo.','resolve',[scopeField(),{key:'keyword',kind:'select',label:'Keyword',options:KEYWORD_LABELS},durationField()],{targetScope:'target-creature',keyword:'flying',duration:'end-of-turn'}),

 'put-from-graveyard-to-hand':def('Recuperar del cementerio a mano','Cementerio','Mueve cartas del cementerio a la mano.','resolve',[targetField('Cementerio de'),filterField(),numField('amount','Cantidad',1,20)],{target:'self',cardFilter:'any',amount:1}),
 'return-from-graveyard-to-battlefield':def('Reanimar','Cementerio','Devuelve una carta del cementerio al campo.','resolve',[targetField('Cementerio de'),filterField(),numField('amount','Cantidad',1,20)],{target:'self',cardFilter:'creature',amount:1}),
 'exile-from-graveyard':def('Exiliar del cementerio','Cementerio','Exilia cartas de un cementerio.','resolve',[targetField('Cementerio de'),filterField(),numField('amount','Cantidad',1,50)],{target:'opponent',cardFilter:'any',amount:1}),

 'add-mana':def('Generar mana / recurso','Mana y coste','Añade recurso temporal de un color.','resolve',[{key:'requiresPip',kind:'color',label:'Color'},numField('amount','Cantidad',1,20)],{requiresPip:'U',amount:1}),
 'mana-filter':def('Filtrar mana','Mana y coste','Convierte recurso de un color en otro.','resolve',[{key:'fromColor',kind:'color',label:'Color origen'},{key:'toColor',kind:'color',label:'Color destino'},numField('amount','Cantidad',1,20)],{fromColor:'U',toColor:'R',amount:1}),
 'manifest-bonus':def('Bonificación de Manafestación','Mana y coste','Suma un bono a una tirada de Manafestación.','manifest-roll',[numField('amount','Bonificación',1,20),{key:'requiresPip',kind:'color',label:'Requiere cristal'},{key:'exhaustSource',kind:'boolean',label:'Agotar la fuente'}],{amount:1,requiresPip:'U',exhaustSource:true},{type:'manifest-bonus',lockedEvent:true}),
 'search-basic-land':def('Buscar Land básica','Mana y coste','Busca Lands básicas y las mueve al destino.','resolve',[targetField('Library de'),zoneField('destination','Destino'),numField('amount','Cantidad',1,10)],{target:'self',destination:'battlefield',amount:1}),
 'play-additional-land':def('Jugar Land adicional','Mana y coste','Permite una cantidad extra de Lands este turno.','resolve',[numField('amount','Lands adicionales',1,10)],{amount:1}),

 'counter-stack-target':def('Contrarrestar spell','Stack','Contrarresta el objetivo actual del Stack.','resolve',[],{},{type:'counter-stack-target'}),
 'copy-spell':def('Copiar spell','Stack','Copia un spell del Stack.','resolve',[numField('amount','Copias',1,20)],{amount:1}),
 'redirect-spell':def('Cambiar objetivo de spell','Stack','Permite cambiar el objetivo de un spell o habilidad.','resolve',[],{}),

 'extra-combat':def('Fase de combate adicional','Turno','Crea fases de combate adicionales.','resolve',[numField('amount','Combates extra',1,5)],{amount:1}),
 'extra-turn':def('Turno adicional','Turno','Otorga turnos adicionales.','resolve',[targetField('Jugador'),numField('amount','Turnos',1,5)],{target:'self',amount:1}),
 'skip-turn':def('Saltar próximo turno','Turno','Hace que un jugador salte turnos.','resolve',[targetField('Jugador'),numField('amount','Turnos',1,5)],{target:'opponent',amount:1})
});
const TYPES=Object.freeze(Object.keys(EDITOR_DEFINITIONS));

function text(value,fallback=''){return String(value??fallback);}
function integer(value,fallback=0){const n=Number(value);return Number.isFinite(n)?Math.trunc(n):fallback;}
function cloneSimple(value){if(value==null)return value;if(Array.isArray(value))return value.map(cloneSimple);if(typeof value==='object'){const out={};for(const[k,v]of Object.entries(value))out[k]=cloneSimple(v);return out;}return value;}
function normalizeEffect(input={}){
 const type=TYPES.includes(input.type)?input.type:text(input.type,''),defn=EDITOR_DEFINITIONS[type],event=EVENTS.includes(input.event)?input.event:(defn?.defaultEvent||'resolve'),effect={type,event};
 const keys=['target','amount','choice','requiresPip','exhaustSource','targetScope','secondTargetScope','destination','cardFilter','duration','counterType','keyword','tokenName','tokenPower','tokenToughness','powerDelta','toughnessDelta','powerValue','toughnessValue','fromColor','toColor','customCounter'];
 for(const key of keys){if(input[key]==null)continue;const v=input[key];if(['amount','tokenPower','tokenToughness','powerDelta','toughnessDelta','powerValue','toughnessValue'].includes(key))effect[key]=integer(v,0);else if(['exhaustSource'].includes(key))effect[key]=!!v;else if(['requiresPip','fromColor','toColor'].includes(key))effect[key]=text(v).toUpperCase();else effect[key]=cloneSimple(v);}
 return effect;
}
function normalizeEffects(input=[]){return Array.isArray(input)?input.map(normalizeEffect):[];}
function editorDefinition(type){return EDITOR_DEFINITIONS[type]||null;}
function newEffect(type,event=null){const d=editorDefinition(type);return normalizeEffect({type,event:event||d?.defaultEvent||'resolve',...(d?.defaults||{})});}
function validateEffects(input=[]){
 const effects=normalizeEffects(input),errors=[],warnings=[];
 effects.forEach((effect,index)=>{
  const p=`effects[${index}]`,d=editorDefinition(effect.type);
  if(!d){errors.push(`${p}: tipo de efecto inválido (${effect.type||'vacío'}).`);return;}
  if(!EVENTS.includes(effect.event))errors.push(`${p}: evento inválido (${effect.event||'vacío'}).`);
  for(const field of d.fields||[]){const v=effect[field.key];if(field.kind==='number'&&(v==null||!Number.isFinite(Number(v))||Number(v)<(field.min??-Infinity)))errors.push(`${p}: ${d.label} requiere ${field.label}.`);}
  if(effect.type==='discard'&&effect.amount!==1)warnings.push(`${p}: el runtime Arena actual sólo resuelve descarte de 1; el Generator conserva cantidades mayores para expansión.`);
  if(d.lockedEvent&&effect.event!==d.defaultEvent)errors.push(`${p}: ${effect.type} requiere event=${d.defaultEvent}.`);
  for(const key of ['requiresPip','fromColor','toColor'])if(effect[key]&&!COLORS.includes(effect[key]))errors.push(`${p}: ${key} inválido (${effect[key]}).`);
  if(d.runtime!=='wired')warnings.push(`${p}: ${d.label} está disponible para autoría; su resolución completa en Arena aún requiere handler runtime.`);
 });
 return{valid:errors.length===0,errors,warnings,effects};
}
function forEvent(card,event){return normalizeEffects(card?.effects).filter(effect=>effect.event===event);}
function hasEffect(card,type,event=null){const list=event?forEvent(card,event):normalizeEffects(card?.effects);return list.some(effect=>effect.type===type);}
function sumAmount(card,event,type){return forEvent(card,event).filter(effect=>effect.type===type).reduce((sum,effect)=>sum+(effect.amount||0),0);}
function effectSide(target,selfSide,opponentSide,defaultTarget='self'){return(target||defaultTarget)==='opponent'?opponentSide:selfSide;}
function otherPermanentTargets(match,sourceOwner,entryIndex=null,sourceZone=null,sourceIndex=null){const targets=[];for(const owner of ['player','enemy']){const player=match[owner];player.battlefield.forEach((id,index)=>{if(!(owner===sourceOwner&&index===entryIndex))targets.push({owner,zone:'battlefield',index,id});});player.artifacts.forEach((id,index)=>{if(!(owner===sourceOwner&&sourceZone==='artifacts'&&index===sourceIndex))targets.push({owner,zone:'artifacts',index,id})});player.equipment.forEach((entry,index)=>{if(!(owner===sourceOwner&&sourceZone==='equipment'&&index===sourceIndex))targets.push({owner,zone:'equipment',index,id:entry.id})});}return targets;}
function preferredPermanentTarget(targets=[],preferredOwner='player'){return targets.find(target=>target.owner===preferredOwner)||targets[0]||null;}
function bouncePlan(target={}){const zone=target.zone||'battlefield';return{owner:target.owner,zone,index:target.index,destination:'hand',zoneLabel:zone==='equipment'?'Equipo':zone==='artifacts'?'Reliquias':'Invocaciones'};}
function stackTargetIndex(stack,targetStackId){const index=stack.findIndex(entry=>entry.id===targetStackId);return index>=0?index:stack.length-1;}
function runtimePlan(effect,context={}){
 const match=context.match,sourceOwner=context.sourceOwner,opponentOwner=sourceOwner==='player'?'enemy':'player',targetOwner=defaultTarget=>effectSide(effect.target,sourceOwner,opponentOwner,defaultTarget);
 if(effect.type==='counter-stack-target')return{kind:'counter-stack-target',terminal:true,stackIndex:stackTargetIndex(match.stack,context.targetStackId)};
 if(effect.type==='draw')return{kind:'draw',terminal:false,targetOwner:targetOwner('self'),amount:effect.amount||1,logResolve:effect.event==='resolve'};
 if(effect.type==='damage-character')return{kind:'damage-character',terminal:false,targetOwner:targetOwner('opponent'),amount:effect.amount||1};
 if(effect.type==='observe-top'){const owner=targetOwner('self'),topCardId=match[owner].library[0];return{kind:'observe-top',terminal:false,targetOwner:owner,topCardId,action:topCardId?(sourceOwner==='player'&&owner===sourceOwner?'choice':'log'):'none'};}
 if(effect.type==='bounce-other-permanent'){const targets=otherPermanentTargets(match,sourceOwner,context.entryIndex,context.sourceZone,context.sourceIndex),action=!targets.length?'none':sourceOwner==='player'?'choice':'bounce';return{kind:'bounce-other-permanent',terminal:false,targets,action,preferredTarget:action==='bounce'?preferredPermanentTarget(targets,'player'):null};}
 if(effect.type==='discard'){const owner=targetOwner('self'),target=match[owner],action=effect.amount!==1?'none':sourceOwner==='player'&&owner===sourceOwner?'choice':target.hand.length?'discard-last':'none';return{kind:'discard',terminal:false,targetOwner:owner,amount:effect.amount,action};}
 return{kind:effect.type,terminal:false,unsupported:!WIRED_TYPES.has(effect.type),effect:normalizeEffect(effect)};
}
function preferredResponseCard(hand=[],resolveCard,canPay){return hand.map((id,index)=>({i:index,c:resolveCard(id)})).filter(entry=>entry.c?.type==='Instant'&&canPay(entry.c)).sort((a,b)=>(hasEffect(a.c,'counter-stack-target','resolve')?-1:0)-(hasEffect(b.c,'counter-stack-target','resolve')?-1:0))[0]||null;}
function preferredMainPhaseCard(hand=[],resolveCard,canPay){return hand.map((id,index)=>({i:index,c:resolveCard(id)})).filter(entry=>entry.c?.type!=='Land'&&!hasEffect(entry.c,'counter-stack-target','resolve')&&canPay(entry.c)).sort((a,b)=>a.c.difficulty-b.c.difficulty)[0];}
function priorityWindowPlan(sourceOwner){const responder=sourceOwner==='player'?'enemy':'player';return{responder,active:responder==='player'?'response':'enemy-response',phase:responder==='player'?'Tu prioridad':'Prioridad rival'};}
function priorityPassPlan(responseWindow,owner){if(responseWindow?.responder!==owner)return null;return{responseWindow:null,pendingResolution:true,active:'resolving',phase:'Stack listo'};}
function stackCompletionPlan(match={}){if(match.over)return{kind:'over'};if(match.pendingChoice)return{kind:'choice',active:'choice'};const owner=match.stackReturnOwner||'player',enemy=owner==='enemy';return{kind:'return',stackReturnOwner:null,active:enemy?'enemy':'player',phase:enemy?'Main rival':'Main',scheduleEnemy:enemy};}
function shouldContinueStackResolution(match,resolvedCount,limit=30){return!!(match.stack.length&&!match.pendingChoice&&!match.over&&resolvedCount<limit);}
function matchWinner(playerLife,enemyLife){return playerLife<=0||enemyLife<=0?(playerLife>0?'player':'enemy'):null;}
function categories(){return [...new Set(TYPES.map(type=>EDITOR_DEFINITIONS[type].category))];}

global.SizaCardEffects=Object.freeze({VERSION,EVENTS,TYPES,TARGETS,COLORS,KEYWORDS,ZONES,TARGET_SCOPES,CARD_FILTERS,DURATIONS,COUNTERS,EVENT_LABELS,TARGET_LABELS,COLOR_LABELS,KEYWORD_LABELS,ZONE_LABELS,TARGET_SCOPE_LABELS,CARD_FILTER_LABELS,DURATION_LABELS,COUNTER_LABELS,EDITOR_DEFINITIONS,categories,editorDefinition,newEffect,normalizeEffect,normalizeEffects,validateEffects,forEvent,hasEffect,sumAmount,effectSide,otherPermanentTargets,preferredPermanentTarget,bouncePlan,stackTargetIndex,runtimePlan,preferredResponseCard,preferredMainPhaseCard,priorityWindowPlan,priorityPassPlan,stackCompletionPlan,shouldContinueStackResolution,matchWinner});
})(window);
