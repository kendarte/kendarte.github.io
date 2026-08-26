(function(global){
'use strict';

const VERSION='1.0.0';
const core=global.SizaCardEffects;
if(!core)return;

const SCOPE_TEXT=Object.freeze({
 source:'esta carta',
 'target-creature':'la criatura objetivo',
 'target-permanent':'el permanente objetivo',
 'target-artifact':'el artefacto objetivo',
 'target-player':'el jugador objetivo',
 'each-creature-self':'cada criatura que controlas',
 'each-creature-opponent':'cada criatura que controla el rival',
 'each-creature':'cada criatura',
 'random-creature-opponent':'una criatura rival aleatoria'
});
const FILTER_TEXT=Object.freeze({
 any:'una carta',creature:'una carta de criatura',artifact:'una carta de artefacto',instant:'una Reacción',land:'una Land',nonland:'una carta que no sea Land','basic-land':'una Land básica'
});
const DESTINATION_TEXT=Object.freeze({library:'en la Library',hand:'en la mano',battlefield:'en el campo de batalla',graveyard:'en el cementerio',exile:'en el exilio'});
const EVENT_PREFIX=Object.freeze({
 resolve:'',
 enter:'Cuando esta carta entre al campo de batalla, ',
 leave:'Cuando esta carta deje el campo de batalla, ',
 dies:'Cuando esta carta muera, ',
 cast:'Cuando lances esta carta, ',
 'attack-declared':'Cuando esta carta ataque, ',
 'block-declared':'Cuando esta carta bloquee, ',
 'becomes-blocked':'Cuando esta carta sea bloqueada, ',
 'combat-damage':'Cuando esta carta haga daño de combate, ',
 upkeep:'Al comienzo de tu mantenimiento, ',
 'draw-step':'Al comienzo de tu paso de robar, ',
 'end-step':'Al comienzo de tu paso final, ',
 'card-drawn':'Siempre que robes una carta, ',
 'card-discarded':'Siempre que descartes una carta, ',
 'life-gained':'Siempre que ganes vida, ',
 'life-lost':'Siempre que pierdas vida, ',
 'permanent-tapped':'Siempre que un permanente se agote, ',
 'permanent-untapped':'Siempre que un permanente se enderece, ',
 'manifest-roll':'Siempre que hagas una tirada de Manafestación, ',
 equipped:''
});

function n(value,fallback=1){const x=Number(value);return Number.isFinite(x)?Math.trunc(x):fallback;}
function plural(amount,singular,pluralText){return `${amount} ${amount===1?singular:pluralText}`;}
function lowerFirst(text){return text?text.charAt(0).toLocaleLowerCase('es')+text.slice(1):'';}
function stripPeriod(text){return String(text||'').trim().replace(/[.]+$/,'');}
function sentence(text){const clean=stripPeriod(text);return clean?clean+'.':'';}
function scope(effect,key='targetScope'){return SCOPE_TEXT[effect?.[key]]||'el objetivo';}
function player(effect){return effect?.target==='opponent'?'el rival':'tú';}
function possessive(effect){return effect?.target==='opponent'?'del rival':'tu';}
function filter(effect){return FILTER_TEXT[effect?.cardFilter]||'una carta';}
function destination(effect){return DESTINATION_TEXT[effect?.destination]||'en la mano';}
function duration(effect){
 switch(effect?.duration){
  case'end-of-turn':return' hasta el final del turno';
  case'while-equipped':return' mientras permanezca equipado';
  case'until-source-leaves':return' hasta que esta carta deje el campo de batalla';
  default:return'';
 }
}
function keyword(effect){return core.KEYWORD_LABELS?.[effect?.keyword]||effect?.keyword||'la habilidad elegida';}
function counter(effect){return core.COUNTER_LABELS?.[effect?.counterType]||effect?.customCounter||effect?.counterType||'contador';}
function color(value){return String(core.COLOR_LABELS?.[value]||value||'incoloro').toLocaleLowerCase('es');}
function signed(value){const x=n(value,0);return x>=0?`+${x}`:String(x);}
function cardCount(effect,label='carta'){const amount=n(effect?.amount,1);return plural(amount,label,label+'s');}

function effectBody(input={}){
 const e=core.normalizeEffect(input),amount=n(e.amount,1),who=player(e),owner=possessive(e),target=scope(e);
 switch(e.type){
  case'draw':return who==='tú'?`Roba ${cardCount(e)}`:`El rival roba ${cardCount(e)}`;
  case'discard':return who==='tú'?`Descarta ${cardCount(e)}`:`El rival descarta ${cardCount(e)}`;
  case'mill':return`Pon las ${amount} cartas superiores de la Library ${owner==='tu'?'que controlas':'del rival'} en ${owner==='tu'?'tu':'su'} cementerio`;
  case'scry':return who==='tú'?`Haz Scry ${amount}`:`El rival hace Scry ${amount}`;
  case'surveil':return who==='tú'?`Haz Surveil ${amount}`:`El rival hace Surveil ${amount}`;
  case'loot':return who==='tú'?`Roba ${cardCount(e)} y luego descarta ${cardCount(e)}`:`El rival roba ${cardCount(e)} y luego descarta ${cardCount(e)}`;
  case'rummage':return who==='tú'?`Descarta ${cardCount(e)} y luego roba ${cardCount(e)}`:`El rival descarta ${cardCount(e)} y luego roba ${cardCount(e)}`;
  case'tutor':return`Busca en ${owner} Library ${amount===1?filter(e):plural(amount,filter(e),filter(e))}, pon ${amount===1?'esa carta':'esas cartas'} ${destination(e)} y luego baraja`;
  case'reveal-top':return`Revela las ${amount} cartas superiores de ${owner} Library`;
  case'observe-top':return`Observa la carta superior de ${owner} Library`;
  case'reorder-top':return`Mira las ${amount} cartas superiores de ${owner} Library y ordénalas como quieras`;
  case'shuffle-library':return`Baraja ${owner} Library`;

  case'damage-character':return e.target==='self'?`Esta carta te hace ${amount} de daño`:`Esta carta hace ${amount} de daño al rival`;
  case'damage-target':return`Esta carta hace ${amount} de daño a ${target}`;
  case'gain-life':return who==='tú'?`Gana ${plural(amount,'vida','vidas')}`:`El rival gana ${plural(amount,'vida','vidas')}`;
  case'lose-life':return who==='tú'?`Pierde ${plural(amount,'vida','vidas')}`:`El rival pierde ${plural(amount,'vida','vidas')}`;
  case'prevent-damage':return`Prevén los próximos ${amount} puntos de daño que se fueran a hacer a ${target}${duration(e)}`;
  case'fight':return`${scope(e)} pelea contra ${scope(e,'secondTargetScope')}`;

  case'destroy-target':return`Destruye ${target}`;
  case'exile-target':return`Exilia ${target}`;
  case'bounce-other-permanent':return'Devuelve otro permanente objetivo a la mano de su propietario';
  case'return-target-to-hand':return`Devuelve ${target} a la mano de su propietario`;
  case'sacrifice':return e.target==='opponent'?`El rival sacrifica ${amount===1?filter(e):plural(amount,filter(e),filter(e))}`:`Sacrifica ${amount===1?filter(e):plural(amount,filter(e),filter(e))}`;
  case'tap-target':return`Agota ${target}`;
  case'untap-target':return`Endereza ${target}`;
  case'freeze-target':return`${target.charAt(0).toUpperCase()+target.slice(1)} no se endereza durante el próximo paso de enderezar de su controlador`;
  case'gain-control':return`Gana el control de ${target}${duration(e)}`;

  case'create-token':{
   const name=e.tokenName||'Token',p=n(e.tokenPower,1),t=n(e.tokenToughness,1);
   return amount===1?`Crea una ficha de criatura ${p}/${t} llamada ${name}`:`Crea ${amount} fichas de criatura ${p}/${t} llamadas ${name}`;
  }
  case'create-resource-token':return amount===1?`Crea una ficha de ${e.tokenName||'recurso'}`:`Crea ${amount} fichas de ${e.tokenName||'recurso'}`;
  case'copy-permanent':return amount===1?`Crea una copia de ${target}`:`Crea ${amount} copias de ${target}`;

  case'add-power-counter':return`Pon ${plural(amount,'contador +1/+1','contadores +1/+1')} sobre esta carta`;
  case'add-counter':return`Pon ${plural(amount,'contador','contadores')} ${counter(e)} sobre ${target}`;
  case'remove-counter':return`Quita ${plural(amount,'contador','contadores')} ${counter(e)} de ${target}`;

  case'modify-stats':return`${target.charAt(0).toUpperCase()+target.slice(1)} obtiene ${signed(e.powerDelta)}/${signed(e.toughnessDelta)}${duration(e)}`;
  case'set-power-toughness':return`El Ataque y la Defensa de ${target} pasan a ser ${n(e.powerValue,0)}/${n(e.toughnessValue,0)}${duration(e)}`;
  case'switch-power-toughness':return`Intercambia el Ataque y la Defensa de ${target}${duration(e)}`;
  case'modify-power':return`La criatura equipada obtiene +${amount}/+0`;
  case'grant-keyword':return`${target.charAt(0).toUpperCase()+target.slice(1)} obtiene ${keyword(e)}${duration(e)}`;
  case'remove-keyword':return`${target.charAt(0).toUpperCase()+target.slice(1)} pierde ${keyword(e)}${duration(e)}`;

  case'put-from-graveyard-to-hand':return`Devuelve ${amount===1?filter(e):plural(amount,filter(e),filter(e))} de ${owner} cementerio a ${owner==='tu'?'tu':'su'} mano`;
  case'return-from-graveyard-to-battlefield':return`Devuelve ${amount===1?filter(e):plural(amount,filter(e),filter(e))} de ${owner} cementerio al campo de batalla bajo ${owner==='tu'?'tu':'su'} control`;
  case'exile-from-graveyard':return`Exilia ${amount===1?filter(e):plural(amount,filter(e),filter(e))} de ${owner} cementerio`;

  case'add-mana':return`Genera ${plural(amount,'recurso','recursos')} ${color(e.requiresPip)}`;
  case'mana-filter':return`Convierte ${plural(amount,'recurso','recursos')} ${color(e.fromColor)} en la misma cantidad de recurso ${color(e.toColor)}`;
  case'manifest-bonus':return`Una tirada de Manafestación que use un cristal ${color(e.requiresPip)} obtiene +${amount}${e.exhaustSource?'; agota esta carta':''}`;
  case'cost-reduction':return`Las cartas que sean ${filter(e)} cuestan ${amount} menos${duration(e)}`;
  case'cost-increase':return`Las cartas que sean ${filter(e)} cuestan ${amount} más${duration(e)}`;
  case'search-basic-land':return`Busca en ${owner} Library ${plural(amount,'Land básica','Lands básicas')}, pon ${amount===1?'esa carta':'esas cartas'} ${destination(e)} y luego baraja`;
  case'play-additional-land':return`Puedes jugar ${plural(amount,'Land adicional','Lands adicionales')} este turno`;

  case'counter-stack-target':return'Contrarresta el spell objetivo';
  case'copy-spell':return amount===1?'Copia el spell objetivo':`Copia el spell objetivo ${amount} veces`;
  case'redirect-spell':return'Cambia el objetivo de un spell o habilidad objetivo';

  case'extra-combat':return amount===1?'Después de esta fase principal, hay una fase de combate adicional':`Después de esta fase principal, hay ${amount} fases de combate adicionales`;
  case'extra-turn':return e.target==='opponent'?`El rival toma ${plural(amount,'turno adicional','turnos adicionales')} después de este`:`Toma ${plural(amount,'turno adicional','turnos adicionales')} después de este`;
  case'skip-turn':return e.target==='self'?`Salta ${plural(amount,'tu próximo turno','tus próximos turnos')}`:`El rival salta ${plural(amount,'su próximo turno','sus próximos turnos')}`;
  default:{
   const def=core.editorDefinition(e.type);return def?.label||e.type||'';
  }
 }
}

function eventPrefix(event){return EVENT_PREFIX[event]??`${core.EVENT_LABELS?.[event]||event}: `;}
function rulesText(input=[]){
 const effects=core.normalizeEffects(input);
 if(!effects.length)return'';
 const lines=[];
 for(let i=0;i<effects.length;){
  const event=effects[i].event,group=[];
  while(i<effects.length&&effects[i].event===event){group.push(effects[i]);i++;}
  const bodies=group.map(effectBody).filter(Boolean);
  if(!bodies.length)continue;
  const prefix=eventPrefix(event);
  let line='';
  if(prefix){
   line=prefix+lowerFirst(stripPeriod(bodies[0]));
   for(let j=1;j<bodies.length;j++)line+=`. Luego, ${lowerFirst(stripPeriod(bodies[j]))}`;
  }else{
   line=stripPeriod(bodies[0]);
   for(let j=1;j<bodies.length;j++)line+=`. Luego, ${lowerFirst(stripPeriod(bodies[j]))}`;
  }
  lines.push(sentence(line));
 }
 return lines.join('\n');
}

global.SizaCardRulesText=Object.freeze({VERSION,effectBody,rulesText,eventPrefix});
})(window);
