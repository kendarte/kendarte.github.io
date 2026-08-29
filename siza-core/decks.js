(function(global){
'use strict';

/* Dragon Thunder Classic lives in the shared core catalog so the same cards are
   available to Siza Web and to the Card/Deck Generator. IDs stay stable. */
const BASE_CARD_CATALOG=global.SizaCardCatalog;
const RESERVE_TEXT_EN='Reserves are not played to the Battlefield. Keep them in hand; after a failed Manafestation roll, consume one as Mana Burn to add +1 to that roll.';
function freezeCard(data){const pips=Object.freeze({...data.pips}),effects=data.effects?Object.freeze(data.effects.map(effect=>Object.freeze({...effect}))):undefined;return Object.freeze({...data,pips,...(effects?{effects}:{})})}
const dragonThunderCards=Object.freeze([
 freezeCard({id:'dtc_familiar_conductor',name:'Familiar Conductor',type:'Creature',subtype:'Familiar',difficulty:4,pips:{U:1},power:1,toughness:1,text:'Exhaust: +1 to a Manafestation roll for a Dragon Invocation.',flavor:'It does not summon the storm. It teaches the storm where to land.',role:'ramp',art:'blue',glyph:'◈'}),
 freezeCard({id:'dtc_reactor_weaver',name:'Reactor Weaver',type:'Creature',subtype:'Spider',difficulty:5,pips:{U:1},power:2,toughness:2,text:'Exhaust: +1 to a Red or Blue Manafestation roll. Whenever you successfully manifest a D7+ Dragon, ready Reactor Weaver.',flavor:'Its web vibrates before the first wingbeat.',role:'ramp',art:'blue',glyph:'✣'}),
 freezeCard({id:'dtc_dragonstorm_front',name:'Dragonstorm Front',type:'Artifact',subtype:'Relic',difficulty:5,pips:{R:1},text:'Whenever a Dragon Invocation enters under your control, deal 1 damage to the opposing Character. Each Dragonstorm Front triggers separately.',flavor:'The sky burns before the dragon arrives.',role:'engine',art:'red',glyph:'ϟ'}),
 freezeCard({id:'dtc_predators_ascension',name:"Predator's Ascension",type:'Artifact',subtype:'Relic',difficulty:5,pips:{U:1},text:'The first time each turn an Invocation with 4 or more ATK enters under your control, draw 1 card.',flavor:'Power announces itself long before it attacks.',role:'engine',art:'blue',glyph:'▲'}),
 freezeCard({id:'dtc_crucible_of_the_bloodline',name:'Crucible of the Bloodline',type:'Artifact',subtype:'Relic',difficulty:6,pips:{R:1,U:1},text:'Your Dragon Invocations get +1/+1.',flavor:'Blood remembers the shape of fire.',role:'engine',art:'multi',glyph:'◆'}),
 freezeCard({id:'dtc_hard_won_warblade',name:'Hard-Won Warblade',type:'Artifact',subtype:'Equipment',difficulty:4,pips:{},equipCost:1,text:'Equipped Invocation gets +1/+0. Equip {1}.',flavor:'Every notch is a victory that refused to disappear.',role:'utility',art:'multi',glyph:'†',effects:[{event:'equipped',type:'modify-power',amount:1}]}),
 freezeCard({id:'dtc_thunderfront_regent',name:'Thunderfront Regent',type:'Creature',subtype:'Dragon',difficulty:6,pips:{R:2},power:4,toughness:4,text:'Whenever an opposing Reaction targets one of your Dragons, deal 1 damage to the opposing Character.',flavor:'Threaten the brood and the answer comes from the clouds.',role:'threat',art:'red',glyph:'♛'}),
 freezeCard({id:'dtc_caldera_scourge',name:'Caldera Scourge',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2},power:4,toughness:4,text:'Whenever this or another Dragon enters under your control, deal 1 damage to the opposing Character. If you control three or more Dragons, deal 2 instead.',flavor:'One dragon is an omen. Three are a weather system.',role:'engine',art:'red',glyph:'Ω'}),
 freezeCard({id:'dtc_ash_collector',name:'Ash Collector',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2},power:5,toughness:5,text:'When Ash Collector enters, the opponent chooses one: sacrifice an Invocation; or take 3 damage.',flavor:'Its tribute is paid in flesh or smoke.',role:'threat',art:'red',glyph:'◇'}),
 freezeCard({id:'dtc_cinderwing_twin',name:'Cinderwing Twin',type:'Creature',subtype:'Dragon',difficulty:6,pips:{R:2},power:4,toughness:4,text:'If you used 2 or more Mana Burn to complete this Manafestation, create a 3/3 Dragon Invocation token.',flavor:'The second shadow appears only after the fire is fed.',role:'threat',art:'red',glyph:'∞'}),
 freezeCard({id:'dtc_fulminated_ridge_tyrant',name:'Fulminated Ridge Tyrant',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2,U:1},power:4,toughness:5,text:'When Fulminated Ridge Tyrant enters, deal 2 damage to any target.',flavor:'The ridge cracked because it landed there once.',role:'removal',art:'multi',glyph:'ϟ'}),
 freezeCard({id:'dtc_cataclysm_maw',name:'Cataclysm Maw',type:'Creature',subtype:'Dragon',difficulty:8,pips:{R:2,U:1},power:7,toughness:7,text:'Whenever Cataclysm Maw attacks, deal 3 damage to the opposing Character and 1 damage to up to two opposing Invocations.',flavor:'It does not enter a battle. It changes the geography.',role:'finisher',art:'multi',glyph:'Ω'}),
 freezeCard({id:'dtc_variable_ember_devastator',name:'Variable Ember Devastator',type:'Creature',subtype:'Dragon',difficulty:5,pips:{R:1},power:1,toughness:1,text:'Variable Ember Devastator enters with one +1/+1 counter for each Mana Burn used to complete its Manafestation.',flavor:'Feed the spark. Decide how large the disaster becomes.',role:'threat',art:'red',glyph:'✦'}),
 freezeCard({id:'dtc_fiery_shapeshifter',name:'Fiery Shapeshifter',type:'Creature',subtype:'Dragon Shapeshifter',difficulty:5,pips:{R:1},power:3,toughness:2,text:'When Fiery Shapeshifter dies, draw 1 card.',flavor:'Its last shape is always smoke.',role:'utility',art:'red',glyph:'≈',effects:[{event:'dies',type:'draw',target:'self',amount:1}]}),
 freezeCard({id:'dtc_mutagenic_stomper',name:'Mutagenic Stomper',type:'Creature',subtype:'Dragon Shapeshifter',difficulty:5,pips:{R:1,U:1},power:4,toughness:2,text:'Trample.',flavor:'Too many wings. Too much mass. Exactly enough momentum.',role:'threat',art:'multi',glyph:'»'}),
 freezeCard({id:'dtc_brotherhoods_end',name:"Brotherhood's End",type:'Instant',difficulty:6,pips:{R:1},text:'Deal 2 damage to all Invocations.',flavor:'When the formation breaks, everyone burns together.',role:'removal',art:'red',glyph:'✹'}),
 freezeCard({id:'dtc_hunting_frenzy',name:'Hunting Frenzy',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 3 damage to target Invocation.',flavor:'The chase ends at the first mistake.',role:'removal',art:'red',glyph:'×'}),
 freezeCard({id:'dtc_lightning_strike',name:'Lightning Strike',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 2 damage to target Invocation or Character.',flavor:'Fast enough to become a decision instead of an event.',role:'removal',art:'red',glyph:'ϟ'}),
 freezeCard({id:'dtc_flash_discharge',name:'Flash Discharge',type:'Instant',difficulty:4,pips:{R:1},text:'Deal 1 damage to any target.',flavor:'Small sparks still choose where the fire begins.',role:'removal',art:'red',glyph:'✦'}),
 freezeCard({id:'dtc_airship_fall',name:'Airship Fall',type:'Instant',difficulty:5,pips:{U:1},text:'Destroy target Relic. If you do not, draw 1 card, then discard 1 card.',flavor:'Anything that flies eventually negotiates with gravity.',role:'utility',art:'blue',glyph:'⌄'}),
 freezeCard({id:'dtc_pictomantic_suplex',name:'Pictomantic Suplex',type:'Instant',difficulty:5,pips:{R:1},text:'Choose one — Deal 3 damage to target Invocation; if it dies this turn, exile it. Or exile target Relic.',flavor:'Technique first. Humiliation second.',role:'removal',art:'red',glyph:'↯'}),
 freezeCard({id:'dtc_subsurface_missile',name:'Subsurface Missile',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 2 damage to target Invocation. You may put a card from your hand on the bottom of your Library. If you do, draw 1 card.',flavor:'The street only looks solid from above.',role:'removal',art:'red',glyph:'↑'}),
 freezeCard({id:'dtc_war_kick',name:'War Kick',type:'Instant',difficulty:5,pips:{U:1},text:'One of your Invocations deals damage equal to its ATK to target opposing Invocation. If Mana Burn was used to manifest War Kick, it deals double that damage instead.',flavor:'Commit the whole body or do not kick at all.',role:'removal',art:'blue',glyph:'★'}),
 freezeCard({id:'dtc_thunder_peaks',name:'Thunder Peaks',type:'Land',pips:{},text:RESERVE_TEXT_EN,flavor:'Storms gather here because the dragons already did.',role:'land',art:'land',glyph:'△'}),
 freezeCard({id:'dtc_reactor_forests',name:'Reactor Forests',type:'Land',pips:{},text:RESERVE_TEXT_EN,flavor:'Roots drink the heat leaking from buried machinery.',role:'land',art:'land',glyph:'♣'}),
 freezeCard({id:'dtc_dragon_spirit_haven',name:'Dragon Spirit Haven',type:'Land',pips:{},text:RESERVE_TEXT_EN,flavor:'The dead circle above it before deciding whether to leave.',role:'land',art:'land',glyph:'⌁'}),
 freezeCard({id:'dtc_storm_pass',name:'Storm Pass',type:'Land',pips:{},text:RESERVE_TEXT_EN,flavor:'The shortest road is also the one under the wings.',role:'land',art:'land',glyph:'◇'})
]);
if(BASE_CARD_CATALOG&&typeof BASE_CARD_CATALOG.all==='function'){
 const baseCards=BASE_CARD_CATALOG.all(),ids=new Set(baseCards.map(card=>card.id)),combined=Object.freeze([...baseCards,...dragonThunderCards.filter(card=>!ids.has(card.id))]);
 global.SizaCardCatalog=Object.freeze({
  ...BASE_CARD_CATALOG,
  VERSION:'1.6.0',
  cards:combined,
  get(id){return combined.find(entry=>entry.id===id)||null},
  all(){return combined.slice()},
  dragonThunderCards
 });
}

const VERSION='1.1.0',FORMAT='Siza Core 60',freezeCounts=counts=>Object.freeze({...counts});
const deck=(id,name,counts,role)=>Object.freeze({id,name,format:FORMAT,version:VERSION,role,counts:freezeCounts(counts)});
const shared=Object.freeze({dhk_familiar_de_practica:4,dhk_lectura_de_campo:4,dhk_interrupcion_de_protocolo:4,dhk_prisma_de_servicio:4,dhk_spellweapon_de_servicio:4});
const decks=Object.freeze([
 deck('deck_tide_crimson','Marea Carmesí',{mist:4,spark:4,servitor:4,ignimite:4,counter:4,prism:4,watcher:4,tideblade:4,dhk_mastin_de_impacto:4,dock:12,cinder:12},'Azul-rojo equilibrado'),
 deck('vertical_dragon_thunder_classic','Dragon Thunder Classic',{
  dtc_familiar_conductor:3,dtc_reactor_weaver:2,dtc_dragonstorm_front:3,dtc_predators_ascension:1,dtc_crucible_of_the_bloodline:1,dtc_hard_won_warblade:1,
  dtc_thunderfront_regent:4,dtc_caldera_scourge:2,dtc_ash_collector:2,dtc_cinderwing_twin:1,dtc_fulminated_ridge_tyrant:1,dtc_cataclysm_maw:1,dtc_variable_ember_devastator:1,dtc_fiery_shapeshifter:1,dtc_mutagenic_stomper:1,
  dtc_brotherhoods_end:2,dtc_hunting_frenzy:1,dtc_lightning_strike:3,dtc_flash_discharge:2,dtc_airship_fall:2,dtc_pictomantic_suplex:3,dtc_subsurface_missile:1,dtc_war_kick:1,
  dtc_thunder_peaks:10,dtc_reactor_forests:5,dtc_dragon_spirit_haven:3,dtc_storm_pass:2
 },'Windrago · Red/Blue storm dragons'),
 deck('starter_darkhaven_vigilancia_v01','Darkhaven — Vigilancia',{...shared,dhk_ojo_de_baliza:4,dhk_eco_de_rastreo:4,dhk_ancla_de_retorno:4,dhk_corte_de_senal:4,dhk_archivo_de_guardia:12,dhk_plataforma_de_relevo:12},'Control e información'),
 deck('starter_darkhaven_ruptura_v01','Darkhaven — Ruptura',{...shared,dhk_ignimite_de_ejercicio:4,dhk_mastin_de_impacto:4,dhk_eco_de_asalto:4,dhk_descarga_de_ruptura:4,dhk_galeria_de_entrenamiento:12,dhk_hangar_de_salida:12},'Presión y combate'),
 deck('starter_darkhaven_contencion_v01','Darkhaven — Contención',{...shared,dhk_sabueso_de_umbral:4,dhk_custodio_lumex:4,dhk_bastion_pictomantico:4,dhk_contraimpulso:4,dhk_patio_de_contencion:12,dhk_camara_de_frames:12},'Defensa y permanencia')
]);
function get(id){return decks.find(entry=>entry.id===id)||null}
function all(){return decks.slice()}
function copy(id='vertical_dragon_thunder_classic'){const source=get(id)||get('vertical_dragon_thunder_classic')||decks[0];return{id:source.id,name:source.name,format:source.format,version:source.version,role:source.role,counts:{...source.counts}}}
function validate(input,resolveCard){const errors=[],counts=input?.counts||{},total=Object.values(counts).reduce((sum,value)=>sum+(Number(value)||0),0);if(total!==60)errors.push('DECK_MUST_HAVE_60_CARDS');for(const[id,raw]of Object.entries(counts)){const quantity=Number(raw)||0,card=resolveCard(id);if(!card){errors.push(`UNKNOWN_CARD:${id}`);continue}if(quantity<0||!Number.isInteger(quantity))errors.push(`INVALID_QUANTITY:${id}`);if(card.type!=='Land'&&quantity>4)errors.push(`COPY_LIMIT:${id}`);if(card.type!=='Land'&&!(Number(card.difficulty)>0))errors.push(`INVALID_DIFFICULTY:${id}`)}return{valid:errors.length===0,total,errors}}
global.SizaDeckCatalog=Object.freeze({VERSION,FORMAT,decks,get,all,copy,validate});

/* Marea Carmesí stays selectable, but the vertical-slice player is migrated to Dragon Thunder Classic. */
try{
 const key='siza_work_state_v1',raw=global.localStorage?.getItem(key);
 if(raw){
  const state=JSON.parse(raw);
  if(state?.deck?.id==='deck_tide_crimson'){
   state.deck=copy('vertical_dragon_thunder_classic');
   state.match=null;
   global.localStorage.setItem(key,JSON.stringify(state));
  }
 }
}catch(e){}
})(window);
