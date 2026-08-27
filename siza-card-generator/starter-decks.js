(function(){
'use strict';
const CARD_KEY='siza_card_generator_library_v2',DECK_KEY='siza_card_generator_decks_v1',SESSION_RELOAD_KEY='siza_darkhaven_starters_seeded_reload_v03';
const now=()=>new Date().toISOString();
function loadObject(key){try{const raw=JSON.parse(localStorage.getItem(key)||'{}');if(Array.isArray(raw))return Object.fromEntries(raw.filter(x=>x?.id).map(x=>[x.id,x]));return raw&&typeof raw==='object'?raw:{}}catch(e){return{}}}
function saveObject(key,value){localStorage.setItem(key,JSON.stringify(value))}
function generatorCard(source,index){const affinity=source.art==='blue'?'azul':source.art==='red'?'rojo':source.art==='land'?'land':'multi',template=source.art==='blue'?'standard_blue':source.art==='red'?'standard_red':source.art==='land'?'standard_colorless':'standard_colorless';return SizaCardSchema.normalizeCard({...source,cardType:source.type,affinity,template,rules:source.text,setCode:'DHK',cardNumber:String(index+1).padStart(3,'0')})}
const cards=SizaCardCatalog.all().filter(card=>card.id.startsWith('dhk_')).map(generatorCard);
const decks=SizaDeckCatalog.all().filter(deck=>deck.id.startsWith('starter_darkhaven_')).map(deck=>({id:deck.id,name:deck.name,cards:{...deck.counts},createdAt:now(),updatedAt:now(),source:`Darkhaven Starter Decks · balance ${SizaDeckCatalog.VERSION}`}));
const library=loadObject(CARD_KEY);let changedCards=0;
for(const canonical of cards){const existing=library[canonical.id],preserved=existing?{artUrl:existing.artUrl||'',artAssetKey:existing.artAssetKey||'',artTransform:existing.artTransform||canonical.artTransform,battleSpriteUrl:existing.battleSpriteUrl||'',battleSpriteAssetKey:existing.battleSpriteAssetKey||'',battleSpriteTransform:existing.battleSpriteTransform||canonical.battleSpriteTransform,templateParts:existing.templateParts||{}}:{};const next={...canonical,...preserved};if(JSON.stringify(existing)!==JSON.stringify(next)){library[canonical.id]=next;changedCards++}}
if(changedCards)saveObject(CARD_KEY,library);
const deckLibrary=loadObject(DECK_KEY);let changedDecks=0;
for(const canonical of decks){const existing=deckLibrary[canonical.id],next={...canonical,createdAt:existing?.createdAt||canonical.createdAt};if(JSON.stringify(existing)!==JSON.stringify(next)){deckLibrary[canonical.id]=next;changedDecks++}}
if(changedDecks)saveObject(DECK_KEY,deckLibrary);
window.SizaDarkhavenStarterSeed=Object.freeze({cards:cards.map(card=>card.id),decks:decks.map(deck=>deck.id),changedCards,changedDecks});
if((changedCards||changedDecks)&&sessionStorage.getItem(SESSION_RELOAD_KEY)!=='1'){sessionStorage.setItem(SESSION_RELOAD_KEY,'1');location.reload()}else sessionStorage.removeItem(SESSION_RELOAD_KEY);
})();
