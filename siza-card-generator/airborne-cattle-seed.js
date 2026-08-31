(function(global){
'use strict';

const baseCards=global.SizaCardCatalog;
const baseDecks=global.SizaDeckCatalog;
if(!baseCards||!baseDecks)return;

const RESERVE_TEXT_ES='Reserva. Manténla en la mano; después de una tirada fallida de Manafestación, consúmela como Mana Burn para sumar +1 a esa tirada.';
const freezeEffect=effect=>Object.freeze({...effect});
const freezeCard=data=>Object.freeze({...data,pips:Object.freeze({...data.pips}),effects:data.effects?Object.freeze(data.effects.map(freezeEffect)):undefined});

const airborneCattleCards=Object.freeze([
 freezeCard({id:'bov_paracaidista_de_linea',name:'Paracaidista de Línea',type:'Creature',subtype:'Vaca · Paracaidista',difficulty:4,pips:{R:1},power:2,toughness:1,text:'',flavor:'Primero toca suelo. Después pregunta quién controla la granja.',role:'aggro',art:'red',glyph:'▼'}),
 freezeCard({id:'bov_recluta_de_reemplazo',name:'Recluta de Reemplazo',type:'Creature',subtype:'Vaca · Soldado',difficulty:4,pips:{R:1},power:1,toughness:1,text:'Cuando entra, crea una ficha Recluta Bovino 1/1.',flavor:'Siempre hay otro esperando junto a la puerta del transporte.',role:'swarm',art:'red',glyph:'✚',effects:[{event:'enter',type:'create-token',amount:1,tokenName:'Recluta Bovino',tokenPower:1,tokenToughness:1,tokenSubtype:'Vaca · Soldado'}]}),
 freezeCard({id:'bov_artillero_de_escuadra',name:'Artillero de Escuadra',type:'Creature',subtype:'Vaca · Soldado',difficulty:5,pips:{R:1},power:2,toughness:2,text:'La primera vez cada turno que otra Vaca entra bajo tu control, hace 1 daño al Personaje rival.',flavor:'No necesita ver el objetivo. Sólo necesita saber dónde aterrizó el pelotón.',role:'engine',art:'red',glyph:'✹',effects:[{event:'ally-enter',type:'ally-enter-damage',requiresSubtype:'Vaca',amount:1,thresholdCount:0,thresholdAmount:0}]}),
 freezeCard({id:'bov_sargento_angus',name:'Sargento Angus',type:'Creature',subtype:'Vaca · Oficial',difficulty:5,pips:{R:2},power:2,toughness:2,text:'Tus otras Vacas obtienen +1/+0.',flavor:'Si Angus grita “avance”, el rebaño deja de ser un rebaño.',role:'lord',art:'red',glyph:'★',effects:[{event:'static',type:'tribal-stat-bonus',requiresSubtype:'Vaca',powerDelta:1,toughnessDelta:0}]}),
 freezeCard({id:'bov_operador_de_radio',name:'Operador de Radio',type:'Creature',subtype:'Vaca · Especialista',difficulty:5,pips:{R:1},power:1,toughness:2,text:'Cuando entra, crea una ficha Recluta Bovino 1/1. Cuando ataque junto con otras dos Vacas, roba 1 carta y luego descarta 1 carta.',flavor:'La mitad del combate es fuego. La otra mitad es conseguir que alguien responda.',role:'velocity',art:'red',glyph:'⌁',effects:[{event:'enter',type:'create-token',amount:1,tokenName:'Recluta Bovino',tokenPower:1,tokenToughness:1,tokenSubtype:'Vaca · Soldado'},{event:'attack-declared',type:'loot',target:'self',amount:1}]}),
 freezeCard({id:'bov_veterano_primera_caida',name:'Veterano de la Primera Caída',type:'Creature',subtype:'Vaca · Paracaidista',difficulty:6,pips:{R:2},power:3,toughness:3,text:'Cuando ataca, otra Vaca atacante obtiene +1/+0 hasta el final del turno.',flavor:'Todavía lleva el arnés de la operación que dio nombre al batallón.',role:'pressure',art:'red',glyph:'▲',effects:[{event:'attack-declared',type:'modify-stats',targetScope:'target-creature',powerDelta:1,toughnessDelta:0,duration:'end-of-turn'}]}),
 freezeCard({id:'bov_mayor_batallon_aerotransportado',name:'Mayor del Batallón Aerotransportado',type:'Creature',subtype:'Vaca · Oficial',difficulty:7,pips:{R:2},power:4,toughness:4,text:'Cuando entra, crea dos fichas Recluta Bovino 1/1. Tus Vacas obtienen +1/+0.',flavor:'No trae refuerzos. Él es la señal de que los refuerzos ya vienen cayendo.',role:'finisher',art:'red',glyph:'♛',effects:[{event:'enter',type:'create-token',amount:2,tokenName:'Recluta Bovino',tokenPower:1,tokenToughness:1,tokenSubtype:'Vaca · Soldado'},{event:'static',type:'tribal-stat-bonus',requiresSubtype:'Vaca',powerDelta:1,toughnessDelta:0}]}),

 freezeCard({id:'bov_zona_de_salto',name:'Zona de Salto',type:'Artifact',subtype:'Reliquia',difficulty:5,pips:{R:1},text:'Cada vez que una Vaca entra bajo tu control, hace 1 daño al Personaje rival.',flavor:'Las bengalas rojas significan una sola cosa: despeje el terreno.',role:'engine',art:'red',glyph:'⊕',effects:[{event:'ally-enter',type:'ally-enter-damage',requiresSubtype:'Vaca',amount:1,thresholdCount:0,thresholdAmount:0}]}),
 freezeCard({id:'bov_puesto_mando_campana',name:'Puesto de Mando de Campaña',type:'Artifact',subtype:'Reliquia',difficulty:5,pips:{R:1},text:'La primera vez cada turno que atacas con tres o más Vacas, crea una ficha Recluta Bovino 1/1.',flavor:'Una mesa plegable, dos radios y un mapa bastan para iniciar otra ofensiva.',role:'swarm',art:'red',glyph:'⌂',effects:[{event:'attack-declared',type:'create-token',amount:1,tokenName:'Recluta Bovino',tokenPower:1,tokenToughness:1,tokenSubtype:'Vaca · Soldado'}]}),
 freezeCard({id:'bov_caja_municion_peloton',name:'Caja de Munición del Pelotón',type:'Artifact',subtype:'Reliquia',difficulty:4,pips:{R:1},text:'Tus Vacas atacantes obtienen +1/+0 durante el enfrentamiento.',flavor:'Marcada “forraje”. Nadie recuerda quién empezó a usar esa etiqueta.',role:'anthem',art:'red',glyph:'▣',effects:[{event:'static',type:'modify-stats',targetScope:'each-creature-self',powerDelta:1,toughnessDelta:0,duration:'permanent'}]}),

 freezeCard({id:'bov_fuego_de_cobertura',name:'Fuego de Cobertura',type:'Instant',difficulty:4,pips:{R:1},text:'Hace 1 daño a cualquier objetivo.',flavor:'No tiene que acertar para obligarlos a bajar la cabeza.',role:'removal',art:'red',glyph:'•',effects:[{event:'resolve',type:'damage-target',targetScope:'any-target',amount:1}]}),
 freezeCard({id:'bov_bombardeo_preparacion',name:'Bombardeo de Preparación',type:'Instant',difficulty:5,pips:{R:1},text:'Hace 2 daño a una Invocación o al Personaje rival.',flavor:'La infantería sólo salta cuando el suelo deja de contestar.',role:'removal',art:'red',glyph:'✹',effects:[{event:'resolve',type:'damage-target',targetScope:'any-target',amount:2}]}),
 freezeCard({id:'bov_todos_abajo',name:'¡Todos Abajo!',type:'Instant',difficulty:5,pips:{R:1},text:'Tus Vacas obtienen +1/+0 hasta el final del turno.',flavor:'La orden funciona mejor si nadie pregunta por qué.',role:'pump',art:'red',glyph:'▲',effects:[{event:'resolve',type:'modify-stats',targetScope:'each-creature-self',powerDelta:1,toughnessDelta:0,duration:'end-of-turn'}]}),
 freezeCard({id:'bov_ultima_granada',name:'Última Granada',type:'Instant',difficulty:5,pips:{R:1},text:'Sacrifica una Vaca: hace 3 daño a cualquier objetivo.',flavor:'Si no regresa el soldado, por lo menos regresa el pasador.',role:'reach',art:'red',glyph:'✦',effects:[{event:'resolve',type:'sacrifice',target:'self',cardFilter:'creature',amount:1},{event:'resolve',type:'damage-target',targetScope:'any-target',amount:3}]}),

 freezeCard({id:'bov_zona_de_lanzamiento',name:'Zona de Lanzamiento',type:'Land',pips:{},text:RESERVE_TEXT_ES,flavor:'Marcadores, humo y una franja de terreno que todavía no sabe lo que viene.',role:'land',art:'land',glyph:'▽'}),
 freezeCard({id:'bov_pista_de_campana',name:'Pista de Campaña',type:'Land',pips:{},text:RESERVE_TEXT_ES,flavor:'Lo suficiente para despegar. No necesariamente para volver.',role:'land',art:'land',glyph:'═'}),
 freezeCard({id:'bov_pastizal_requisado',name:'Pastizal Requisado',type:'Land',pips:{},text:RESERVE_TEXT_ES,flavor:'El cartel dice propiedad militar. La hierba no parece convencida.',role:'land',art:'land',glyph:'∿'}),
 freezeCard({id:'bov_recluta_bovino_token',name:'Recluta Bovino',type:'Creature',subtype:'Vaca · Soldado',difficulty:1,pips:{},power:1,toughness:1,text:'Ficha de Invocación.',flavor:'Uno más en la formación.',role:'token',art:'red',glyph:'•'})
]);

const baseCardList=baseCards.all();
const cardIds=new Set(baseCardList.map(card=>card.id));
const mergedCards=Object.freeze([...baseCardList,...airborneCattleCards.filter(card=>!cardIds.has(card.id))]);
global.SizaCardCatalog=Object.freeze({
 ...baseCards,
 VERSION:String(baseCards.VERSION||'core')+'+BOV1',
 cards:mergedCards,
 get(id){return mergedCards.find(card=>card.id===id)||null},
 all(){return mergedCards.slice()},
 airborneCattleCards
});

const AIRBORNE_DECK_ID='starter_batallon_bovino_aerotransportado_v01';
const airborneCounts=Object.freeze({
 bov_paracaidista_de_linea:4,
 bov_recluta_de_reemplazo:4,
 bov_artillero_de_escuadra:4,
 bov_sargento_angus:4,
 bov_operador_de_radio:3,
 bov_veterano_primera_caida:3,
 bov_mayor_batallon_aerotransportado:2,
 bov_zona_de_salto:3,
 bov_puesto_mando_campana:2,
 bov_caja_municion_peloton:1,
 bov_fuego_de_cobertura:3,
 bov_bombardeo_preparacion:3,
 bov_todos_abajo:2,
 bov_ultima_granada:2,
 bov_zona_de_lanzamiento:12,
 bov_pista_de_campana:4,
 bov_pastizal_requisado:4
});
const total=Object.values(airborneCounts).reduce((sum,n)=>sum+n,0);
if(total!==60)throw new Error('Batallón Bovino Aerotransportado debe tener 60 cartas; actual '+total);

const airborneDeck=Object.freeze({
 id:AIRBORNE_DECK_ID,
 name:'Batallón Bovino Aerotransportado',
 format:baseDecks.FORMAT||'Siza Core 60',
 version:'1.0.0',
 role:'Rojo · enjambre paramilitar aerotransportado',
 counts:airborneCounts
});
const baseDeckList=baseDecks.all();
const mergedDecks=Object.freeze([...baseDeckList.filter(deck=>deck.id!==AIRBORNE_DECK_ID),airborneDeck]);
function getDeck(id){return mergedDecks.find(deck=>deck.id===id)||null}
function copyDeck(id){const source=getDeck(id);if(!source)return baseDecks.copy(id);return{id:source.id,name:source.name,format:source.format,version:source.version,role:source.role,counts:{...source.counts}}}
global.SizaDeckCatalog=Object.freeze({
 ...baseDecks,
 VERSION:String(baseDecks.VERSION||'core')+'+BOV1',
 decks:mergedDecks,
 get:getDeck,
 all(){return mergedDecks.slice()},
 copy:copyDeck
});

global.SizaAirborneCattleSeed=Object.freeze({
 deckId:AIRBORNE_DECK_ID,
 cards:airborneCattleCards.map(card=>card.id),
 total
});
})(window);
