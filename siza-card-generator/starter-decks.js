(function(){
'use strict';

const CARD_KEY='siza_card_generator_library_v2';
const DECK_KEY='siza_card_generator_decks_v1';
const SESSION_RELOAD_KEY='siza_darkhaven_starters_seeded_reload_v01';

const now=()=>new Date().toISOString();
const slug=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');

function loadObject(key){
 try{const raw=JSON.parse(localStorage.getItem(key)||'{}');if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));return raw&&typeof raw==='object'?raw:{}}catch(e){return{}}
}
function saveObject(key,value){localStorage.setItem(key,JSON.stringify(value));}

function card(name,cardType,subtype,opts={}){
 const id='dhk_'+slug(name);
 return{
  schemaVersion:'1.6.0',id,name,template:'standard',templateParts:{},frameUrl:'',frameAssetKey:'',
  cardType,type:cardType,subtype:subtype||'',affinity:'multi',difficulty:opts.difficulty??0,cost:opts.cost??0,equipCost:opts.equipCost??0,
  pips:{},crystals:[],artId:id,artUrl:'',artAssetKey:'',artTransform:{x:50,y:50,scale:1},battleSpriteUrl:'',battleSpriteAssetKey:'',battleSpriteTransform:{x:50,y:50,scale:1},
  rules:opts.rules||'',text:opts.rules||'',flavor:opts.flavor||'Darkhaven starter v0.1 · afinidades, pips, coste y Manafestación pendientes del perfil final del protagonista.',
  attack:opts.attack??null,defense:opts.defense??null,force:opts.attack??null,resistance:opts.defense??null,power:opts.attack??null,toughness:opts.defense??null,
  setCode:'DHK',cardNumber:String(opts.number||'000').padStart(3,'0'),glyph:opts.glyph||'✦',art:'multi',role:'starter-page',adventureUnlock:false,effects:opts.effects||[]
 };
}

const cards=[
 card('Familiar de Práctica','Creature','Familiar',{number:1,attack:1,defense:1,rules:'Invocación básica de entrenamiento.'}),
 card('Lectura de Campo','Instant','',{number:2,rules:'Roba una carta.',effects:[{event:'resolve',type:'draw',target:'self',amount:1}]}),
 card('Interrupción de Protocolo','Instant','',{number:3,rules:'Contrarresta el spell objetivo.',effects:[{event:'resolve',type:'counter-stack-target'}]}),
 card('Prisma de Servicio','Artifact','',{number:4,rules:'Agotar: obtén +1 a una tirada de Manafestación compatible.',effects:[{event:'manifest-roll',type:'manifest-bonus',amount:1}]}),
 card('Spellweapon de Servicio','Artifact','Equipment',{number:5,equipCost:1,rules:'La Invocación equipada obtiene +1 Ataque. Equipar {1}.',effects:[{event:'equipped',type:'modify-power',amount:1}]}),

 card('Ojo de Baliza','Creature','Familiar',{number:6,attack:1,defense:2,rules:'Al entrar, observa la carta superior de tu Library.',effects:[{event:'enter',type:'observe-top',target:'self'}]}),
 card('Eco de Rastreo','Creature','Echo',{number:7,attack:2,defense:2,rules:'Al entrar, roba una carta.',effects:[{event:'enter',type:'draw',target:'self',amount:1}]}),
 card('Ancla de Retorno','Artifact','',{number:8,rules:'Al entrar, devuelve otro permanente a la mano de su dueño.',effects:[{event:'enter',type:'bounce-other-permanent'}]}),
 card('Corte de Señal','Instant','',{number:9,rules:'El rival descarta una carta.',effects:[{event:'resolve',type:'discard',target:'opponent',amount:1,choice:'owner'}]}),
 card('Archivo de Guardia','Land','Reserve',{number:10,rules:''}),
 card('Plataforma de Relevo','Land','Reserve',{number:11,rules:''}),

 card('Ignimite de Ejercicio','Creature','Elemental',{number:12,attack:1,defense:1,rules:'Cuando haga daño de combate, obtiene un contador +1/+1.',effects:[{event:'combat-damage',type:'add-power-counter',amount:1}]}),
 card('Mastín de Impacto','Creature','Beast',{number:13,attack:3,defense:2,rules:'Criatura de entrenamiento orientada a presión y combate limpio.'}),
 card('Eco de Asalto','Creature','Echo',{number:14,attack:2,defense:2,rules:'Al declarar ataque, inflige 1 de daño al Personaje defensor.',effects:[{event:'attack-declared',type:'damage-character',target:'opponent',amount:1}]}),
 card('Descarga de Ruptura','Instant','',{number:15,rules:'Inflige 2 de daño al Personaje rival.',effects:[{event:'resolve',type:'damage-character',target:'opponent',amount:2}]}),
 card('Galería de Entrenamiento','Land','Reserve',{number:16,rules:''}),
 card('Hangar de Salida','Land','Reserve',{number:17,rules:''}),

 card('Sabueso de Umbral','Creature','Familiar',{number:18,attack:1,defense:3,rules:'Invocación defensiva de entrenamiento.'}),
 card('Custodio Lumex','Creature','Construct',{number:19,attack:2,defense:4,rules:'Constructo de alta resistencia.'}),
 card('Bastión Pictomántico','Creature','Construct',{number:20,attack:3,defense:6,rules:'Invocación de desarrollo tardío, difícil de retirar.'}),
 card('Contraimpulso','Instant','',{number:21,rules:'Contrarresta el spell objetivo.',effects:[{event:'resolve',type:'counter-stack-target'}]}),
 card('Patio de Contención','Land','Reserve',{number:22,rules:''}),
 card('Cámara de Frames','Land','Reserve',{number:23,rules:''})
];

const ids=Object.fromEntries(cards.map(c=>[c.name,c.id]));
const shared={
 [ids['Familiar de Práctica']]:4,
 [ids['Lectura de Campo']]:4,
 [ids['Interrupción de Protocolo']]:4,
 [ids['Prisma de Servicio']]:4,
 [ids['Spellweapon de Servicio']]:4
};
function deck(id,name,own,reserves){
 return{id,name,cards:{...shared,...own,...reserves},createdAt:now(),updatedAt:now(),source:'Darkhaven Starter Decks v0.1'};
}
const decks=[
 deck('starter_darkhaven_vigilancia_v01','Darkhaven Starter — Vigilancia',{
  [ids['Ojo de Baliza']]:4,[ids['Eco de Rastreo']]:4,[ids['Ancla de Retorno']]:4,[ids['Corte de Señal']]:4
 },{[ids['Archivo de Guardia']]:12,[ids['Plataforma de Relevo']]:12}),
 deck('starter_darkhaven_ruptura_v01','Darkhaven Starter — Ruptura',{
  [ids['Ignimite de Ejercicio']]:4,[ids['Mastín de Impacto']]:4,[ids['Eco de Asalto']]:4,[ids['Descarga de Ruptura']]:4
 },{[ids['Galería de Entrenamiento']]:12,[ids['Hangar de Salida']]:12}),
 deck('starter_darkhaven_contencion_v01','Darkhaven Starter — Contención',{
  [ids['Sabueso de Umbral']]:4,[ids['Custodio Lumex']]:4,[ids['Bastión Pictomántico']]:4,[ids['Contraimpulso']]:4
 },{[ids['Patio de Contención']]:12,[ids['Cámara de Frames']]:12})
];

const library=loadObject(CARD_KEY);let addedCards=0;
for(const c of cards){if(!library[c.id]){library[c.id]=c;addedCards++;}}
if(addedCards)saveObject(CARD_KEY,library);

const deckLibrary=loadObject(DECK_KEY);let addedDecks=0;
for(const d of decks){if(!deckLibrary[d.id]){deckLibrary[d.id]=d;addedDecks++;}}
if(addedDecks)saveObject(DECK_KEY,deckLibrary);

window.SizaDarkhavenStarterSeed=Object.freeze({cards:cards.map(c=>c.id),decks:decks.map(d=>d.id),addedCards,addedDecks});

// app.js lee la biblioteca antes de este módulo. Si acabamos de sembrar datos,
// recargamos una sola vez para que Card Creator y Deck Generator vean exactamente la misma biblioteca.
if((addedCards||addedDecks)&&sessionStorage.getItem(SESSION_RELOAD_KEY)!=='1'){
 sessionStorage.setItem(SESSION_RELOAD_KEY,'1');
 location.reload();
}else{
 sessionStorage.removeItem(SESSION_RELOAD_KEY);
}
})();
