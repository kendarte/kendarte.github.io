(function(){
'use strict';

const CARD_KEY='siza_card_generator_library_v2';
const DECK_KEY='siza_card_generator_decks_v1';
const SESSION_RELOAD_KEY='siza_generator_seeded_reload_dragon_thunder_v01';
const RESERVE_TEXT='Reserves are not played to the Battlefield. Keep them in hand; after a failed Manafestation roll, consume one as Mana Burn to add +1 to that roll.';
const now=()=>new Date().toISOString();

function loadObject(key){
 try{
  const raw=JSON.parse(localStorage.getItem(key)||'{}');
  if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));
  return raw&&typeof raw==='object'?raw:{};
 }catch(e){return{}}
}
function saveObject(key,value){localStorage.setItem(key,JSON.stringify(value))}
function generatorCard(source,index){
 const affinity=source.art==='blue'?'azul':source.art==='red'?'rojo':source.art==='land'?'land':'multi';
 const template=source.art==='blue'?'standard_blue':source.art==='red'?'standard_red':source.art==='land'?'standard_colorless':'standard_colorless';
 return SizaCardSchema.normalizeCard({...source,cardType:source.type,affinity,template,rules:source.text,setCode:'DHK',cardNumber:String(index+1).padStart(3,'0')});
}
function dtCard(data,index){
 const art=data.art||((data.type==='Land')?'land':(data.pips?.R?'red':'multi'));
 const affinity=art==='red'?'rojo':art==='land'?'land':'multi';
 const template=art==='red'?'standard_red':'standard_colorless';
 return SizaCardSchema.normalizeCard({...data,cardType:data.type,affinity,template,rules:data.text,setCode:'DTC',cardNumber:String(index+1).padStart(3,'0'),art});
}

const darkhavenCards=SizaCardCatalog.all().filter(card=>card.id.startsWith('dhk_')).map(generatorCard);
const darkhavenDecks=SizaDeckCatalog.all().filter(deck=>deck.id.startsWith('starter_darkhaven_')).map(deck=>({
 id:deck.id,
 name:deck.name,
 cards:{...deck.counts},
 createdAt:now(),
 updatedAt:now(),
 source:`Darkhaven Starter Decks · balance ${SizaDeckCatalog.VERSION}`
}));

const dragonThunderCards=[
 {id:'dtc_familiar_conductor',name:'Familiar Conductor',type:'Creature',subtype:'Familiar',difficulty:4,pips:{G:1},power:1,toughness:1,text:'Exhaust: +1 to a Manafestation roll for a Dragon Invocation.',flavor:'It does not summon the storm. It teaches the storm where to land.',role:'ramp',glyph:'◈'},
 {id:'dtc_reactor_weaver',name:'Reactor Weaver',type:'Creature',subtype:'Spider',difficulty:5,pips:{G:1},power:2,toughness:2,text:'Exhaust: +1 to a Red or Green Manafestation roll. Whenever you successfully manifest a D7+ Dragon, ready Reactor Weaver.',flavor:'Its web vibrates before the first wingbeat.',role:'ramp',glyph:'✣'},
 {id:'dtc_dragonstorm_front',name:'Dragonstorm Front',type:'Artifact',subtype:'Relic',difficulty:5,pips:{R:1},text:'Whenever a Dragon Invocation enters under your control, deal 1 damage to the opposing Character. Each Dragonstorm Front triggers separately.',flavor:'The sky burns before the dragon arrives.',role:'engine',glyph:'ϟ'},
 {id:'dtc_predators_ascension',name:"Predator's Ascension",type:'Artifact',subtype:'Relic',difficulty:5,pips:{G:1},text:'The first time each turn an Invocation with 4 or more ATK enters under your control, draw 1 card.',flavor:'Power announces itself long before it attacks.',role:'engine',glyph:'▲'},
 {id:'dtc_crucible_of_the_bloodline',name:'Crucible of the Bloodline',type:'Artifact',subtype:'Relic',difficulty:6,pips:{R:1,G:1},text:'Your Dragon Invocations get +1/+1.',flavor:'Blood remembers the shape of fire.',role:'engine',glyph:'◆'},
 {id:'dtc_hard_won_warblade',name:'Hard-Won Warblade',type:'Artifact',subtype:'Equipment',difficulty:4,pips:{},equipCost:1,text:'Equipped Invocation gets +1/+0. Equip {1}.',flavor:'Every notch is a victory that refused to disappear.',role:'utility',glyph:'†',effects:[{event:'equipped',type:'modify-power',amount:1}]},
 {id:'dtc_thunderfront_regent',name:'Thunderfront Regent',type:'Creature',subtype:'Dragon',difficulty:6,pips:{R:2},power:4,toughness:4,text:'Whenever an opposing Reaction targets one of your Dragons, deal 1 damage to the opposing Character.',flavor:'Threaten the brood and the answer comes from the clouds.',role:'threat',glyph:'♛'},
 {id:'dtc_caldera_scourge',name:'Caldera Scourge',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2},power:4,toughness:4,text:'Whenever this or another Dragon enters under your control, deal 1 damage to the opposing Character. If you control three or more Dragons, deal 2 instead.',flavor:'One dragon is an omen. Three are a weather system.',role:'engine',glyph:'Ω'},
 {id:'dtc_ash_collector',name:'Ash Collector',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2},power:5,toughness:5,text:'When Ash Collector enters, the opponent chooses one: sacrifice an Invocation; or take 3 damage.',flavor:'Its tribute is paid in flesh or smoke.',role:'threat',glyph:'◇'},
 {id:'dtc_cinderwing_twin',name:'Cinderwing Twin',type:'Creature',subtype:'Dragon',difficulty:6,pips:{R:2},power:4,toughness:4,text:'If you used 2 or more Mana Burn to complete this Manafestation, create a 3/3 Dragon Invocation token.',flavor:'The second shadow appears only after the fire is fed.',role:'threat',glyph:'∞'},
 {id:'dtc_fulminated_ridge_tyrant',name:'Fulminated Ridge Tyrant',type:'Creature',subtype:'Dragon',difficulty:7,pips:{R:2,G:1},power:4,toughness:5,text:'When Fulminated Ridge Tyrant enters, deal 2 damage to any target.',flavor:'The ridge cracked because it landed there once.',role:'removal',glyph:'ϟ'},
 {id:'dtc_cataclysm_maw',name:'Cataclysm Maw',type:'Creature',subtype:'Dragon',difficulty:8,pips:{R:2,G:1},power:7,toughness:7,text:'Whenever Cataclysm Maw attacks, deal 3 damage to the opposing Character and 1 damage to up to two opposing Invocations.',flavor:'It does not enter a battle. It changes the geography.',role:'finisher',glyph:'Ω'},
 {id:'dtc_variable_ember_devastator',name:'Variable Ember Devastator',type:'Creature',subtype:'Dragon',difficulty:5,pips:{R:1},power:1,toughness:1,text:'Variable Ember Devastator enters with one +1/+1 counter for each Mana Burn used to complete its Manafestation.',flavor:'Feed the spark. Decide how large the disaster becomes.',role:'threat',glyph:'✦'},
 {id:'dtc_fiery_shapeshifter',name:'Fiery Shapeshifter',type:'Creature',subtype:'Dragon Shapeshifter',difficulty:5,pips:{R:1},power:3,toughness:2,text:'When Fiery Shapeshifter dies, draw 1 card.',flavor:'Its last shape is always smoke.',role:'utility',glyph:'≈',effects:[{event:'dies',type:'draw',target:'self',amount:1}]},
 {id:'dtc_mutagenic_stomper',name:'Mutagenic Stomper',type:'Creature',subtype:'Dragon Shapeshifter',difficulty:5,pips:{R:1,G:1},power:4,toughness:2,text:'Trample.',flavor:'Too many wings. Too much mass. Exactly enough momentum.',role:'threat',glyph:'»'},
 {id:'dtc_brotherhoods_end',name:"Brotherhood's End",type:'Instant',difficulty:6,pips:{R:1},text:'Deal 2 damage to all Invocations.',flavor:'When the formation breaks, everyone burns together.',role:'removal',glyph:'✹'},
 {id:'dtc_hunting_frenzy',name:'Hunting Frenzy',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 3 damage to target Invocation.',flavor:'The chase ends at the first mistake.',role:'removal',glyph:'×'},
 {id:'dtc_lightning_strike',name:'Lightning Strike',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 2 damage to target Invocation or Character.',flavor:'Fast enough to become a decision instead of an event.',role:'removal',glyph:'ϟ'},
 {id:'dtc_flash_discharge',name:'Flash Discharge',type:'Instant',difficulty:4,pips:{R:1},text:'Deal 1 damage to any target.',flavor:'Small sparks still choose where the fire begins.',role:'removal',glyph:'✦'},
 {id:'dtc_airship_fall',name:'Airship Fall',type:'Instant',difficulty:5,pips:{G:1},text:'Destroy target Relic. If you do not, draw 1 card, then discard 1 card.',flavor:'Anything that flies eventually negotiates with gravity.',role:'utility',glyph:'⌄'},
 {id:'dtc_pictomantic_suplex',name:'Pictomantic Suplex',type:'Instant',difficulty:5,pips:{R:1},text:'Choose one — Deal 3 damage to target Invocation; if it dies this turn, exile it. Or exile target Relic.',flavor:'Technique first. Humiliation second.',role:'removal',glyph:'↯'},
 {id:'dtc_subsurface_missile',name:'Subsurface Missile',type:'Instant',difficulty:5,pips:{R:1},text:'Deal 2 damage to target Invocation. You may put a card from your hand on the bottom of your Library. If you do, draw 1 card.',flavor:'The street only looks solid from above.',role:'removal',glyph:'↑'},
 {id:'dtc_war_kick',name:'War Kick',type:'Instant',difficulty:5,pips:{G:1},text:'One of your Invocations deals damage equal to its ATK to target opposing Invocation. If Mana Burn was used to manifest War Kick, it deals double that damage instead.',flavor:'Commit the whole body or do not kick at all.',role:'removal',glyph:'★'},
 {id:'dtc_thunder_peaks',name:'Thunder Peaks',type:'Land',pips:{},text:RESERVE_TEXT,flavor:'Storms gather here because the dragons already did.',role:'land',art:'land',glyph:'△'},
 {id:'dtc_reactor_forests',name:'Reactor Forests',type:'Land',pips:{},text:RESERVE_TEXT,flavor:'Roots drink the heat leaking from buried machinery.',role:'land',art:'land',glyph:'♣'},
 {id:'dtc_dragon_spirit_haven',name:'Dragon Spirit Haven',type:'Land',pips:{},text:RESERVE_TEXT,flavor:'The dead circle above it before deciding whether to leave.',role:'land',art:'land',glyph:'⌁'},
 {id:'dtc_storm_pass',name:'Storm Pass',type:'Land',pips:{},text:RESERVE_TEXT,flavor:'The shortest road is also the one under the wings.',role:'land',art:'land',glyph:'◇'}
].map(dtCard);

const dragonThunderDeck={
 id:'vertical_dragon_thunder_classic',
 name:'Dragon Thunder Classic',
 cards:{
  dtc_familiar_conductor:3,
  dtc_reactor_weaver:2,
  dtc_dragonstorm_front:3,
  dtc_predators_ascension:1,
  dtc_crucible_of_the_bloodline:1,
  dtc_hard_won_warblade:1,
  dtc_thunderfront_regent:4,
  dtc_caldera_scourge:2,
  dtc_ash_collector:2,
  dtc_cinderwing_twin:1,
  dtc_fulminated_ridge_tyrant:1,
  dtc_cataclysm_maw:1,
  dtc_variable_ember_devastator:1,
  dtc_fiery_shapeshifter:1,
  dtc_mutagenic_stomper:1,
  dtc_brotherhoods_end:2,
  dtc_hunting_frenzy:1,
  dtc_lightning_strike:3,
  dtc_flash_discharge:2,
  dtc_airship_fall:2,
  dtc_pictomantic_suplex:3,
  dtc_subsurface_missile:1,
  dtc_war_kick:1,
  dtc_thunder_peaks:10,
  dtc_reactor_forests:5,
  dtc_dragon_spirit_haven:3,
  dtc_storm_pass:2
 },
 createdAt:now(),
 updatedAt:now(),
 source:'Siza Vertical Slice · Dragon Thunder Classic · English v01'
};

const cards=[...darkhavenCards,...dragonThunderCards];
const decks=[...darkhavenDecks,dragonThunderDeck];

const library=loadObject(CARD_KEY);
let changedCards=0;
for(const canonical of cards){
 const existing=library[canonical.id];
 const preserved=existing?{
  artUrl:existing.artUrl||'',artAssetKey:existing.artAssetKey||'',artTransform:existing.artTransform||canonical.artTransform,
  battleSpriteUrl:existing.battleSpriteUrl||'',battleSpriteAssetKey:existing.battleSpriteAssetKey||'',battleSpriteTransform:existing.battleSpriteTransform||canonical.battleSpriteTransform,
  templateParts:existing.templateParts||{}
 }:{};
 const next={...canonical,...preserved};
 if(JSON.stringify(existing)!==JSON.stringify(next)){library[canonical.id]=next;changedCards++}
}
if(changedCards)saveObject(CARD_KEY,library);

const deckLibrary=loadObject(DECK_KEY);
let changedDecks=0;
for(const canonical of decks){
 const existing=deckLibrary[canonical.id];
 const next={...canonical,createdAt:existing?.createdAt||canonical.createdAt,updatedAt:existing?.updatedAt||canonical.updatedAt};
 if(JSON.stringify(existing)!==JSON.stringify(next)){deckLibrary[canonical.id]=next;changedDecks++}
}
if(changedDecks)saveObject(DECK_KEY,deckLibrary);

window.SizaStarterSeed=Object.freeze({
 cards:cards.map(card=>card.id),
 decks:decks.map(deck=>deck.id),
 dragonThunderCards:dragonThunderCards.map(card=>card.id),
 dragonThunderDeck:dragonThunderDeck.id,
 changedCards,
 changedDecks
});

function openRequestedDeck(){
 const requested=new URLSearchParams(location.search).get('deck');
 const target=requested==='dragon-thunder-classic'?dragonThunderDeck.id:requested;
 if(!target)return;
 let tries=0;
 const timer=setInterval(()=>{
  tries++;
  const select=document.getElementById('savedDecks');
  if(select&&Array.from(select.options).some(option=>option.value===target)){
   select.value=target;
   select.dispatchEvent(new Event('change',{bubbles:true}));
   const deckTab=document.getElementById('tabDeckBtn');
   if(deckTab)deckTab.click();
   clearInterval(timer);
  }else if(tries>80)clearInterval(timer);
 },50);
}

if((changedCards||changedDecks)&&sessionStorage.getItem(SESSION_RELOAD_KEY)!=='1'){
 sessionStorage.setItem(SESSION_RELOAD_KEY,'1');
 location.reload();
}else{
 sessionStorage.removeItem(SESSION_RELOAD_KEY);
 openRequestedDeck();
}
})();
