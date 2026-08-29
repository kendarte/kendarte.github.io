(function(){
'use strict';

const CARD_KEY='siza_card_generator_library_v2';
const DECK_KEY='siza_card_generator_decks_v1';
const SESSION_RELOAD_KEY='siza_generator_seeded_reload_core_decks_v02';
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
 const art=source.art||'multi';
 const affinity=art==='blue'?'azul':art==='red'?'rojo':art==='land'?'land':'multi';
 const template=art==='blue'?'standard_blue':art==='red'?'standard_red':art==='land'?'standard_colorless':'standard_colorless';
 const setCode=source.id.startsWith('dtc_')?'DTC':source.id.startsWith('dhk_')?'DHK':'SZA';
 return SizaCardSchema.normalizeCard({...source,cardType:source.type,affinity,template,rules:source.text,setCode,cardNumber:String(index+1).padStart(3,'0')});
}

/* The generator now mirrors the shared Siza catalogs instead of maintaining a
   second copy. This makes Marea Carmesí and Dragon Thunder Classic both appear
   in Deck Generator with the same card IDs used by Siza Web. */
const cards=SizaCardCatalog.all().map(generatorCard);
const decks=SizaDeckCatalog.all().map(deck=>({
 id:deck.id,
 name:deck.name,
 cards:{...deck.counts},
 createdAt:now(),
 updatedAt:now(),
 source:`Siza Core Decks · ${deck.role} · catalog ${SizaDeckCatalog.VERSION}`
}));

const library=loadObject(CARD_KEY);
let changedCards=0;
for(const canonical of cards){
 const existing=library[canonical.id];
 const preserved=existing?{
  artUrl:existing.artUrl||canonical.artUrl||'',
  artAssetKey:existing.artAssetKey||canonical.artAssetKey||'',
  artTransform:existing.artTransform||canonical.artTransform,
  battleSpriteUrl:existing.battleSpriteUrl||canonical.battleSpriteUrl||'',
  battleSpriteAssetKey:existing.battleSpriteAssetKey||canonical.battleSpriteAssetKey||'',
  battleSpriteTransform:existing.battleSpriteTransform||canonical.battleSpriteTransform,
  templateParts:existing.templateParts||canonical.templateParts||{}
 }:{};
 const next={...canonical,...preserved};
 if(JSON.stringify(existing)!==JSON.stringify(next)){library[canonical.id]=next;changedCards++}
}
if(changedCards)saveObject(CARD_KEY,library);

const deckLibrary=loadObject(DECK_KEY);
let changedDecks=0;
for(const canonical of decks){
 const existing=deckLibrary[canonical.id];
 const next={...canonical,createdAt:existing?.createdAt||canonical.createdAt,updatedAt:now()};
 if(JSON.stringify(existing)!==JSON.stringify(next)){deckLibrary[canonical.id]=next;changedDecks++}
}
if(changedDecks)saveObject(DECK_KEY,deckLibrary);

window.SizaStarterSeed=Object.freeze({
 cards:cards.map(card=>card.id),
 decks:decks.map(deck=>deck.id),
 dragonThunderDeck:'vertical_dragon_thunder_classic',
 crimsonTideDeck:'deck_tide_crimson',
 changedCards,
 changedDecks
});

function openRequestedDeck(){
 const requested=new URLSearchParams(location.search).get('deck');
 const aliases={
  'dragon-thunder-classic':'vertical_dragon_thunder_classic',
  'marea-carmesi':'deck_tide_crimson',
  'marea-roja':'deck_tide_crimson'
 };
 const target=aliases[requested]||requested;
 if(!target)return;
 let tries=0;
 const timer=setInterval(()=>{
  tries++;
  const select=document.getElementById('savedDecks');
  if(select&&Array.from(select.options).some(option=>option.value===target)){
   select.value=target;
   select.dispatchEvent(new Event('change',{bubbles:true}));
   document.getElementById('tabDeckBtn')?.click();
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
