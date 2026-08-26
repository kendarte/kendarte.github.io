(function(global){
'use strict';

function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function schema(){if(!global.SizaCardSchema)throw new Error('SizaCardSchema must load before SizaCardRenderer.');return global.SizaCardSchema;}
function stats(card,opts={}){const c=schema().normalizeCard(card),s=opts.stats||{};return{power:s.power??opts.power??c.power,toughness:s.toughness??opts.toughness??c.toughness};}
function legacyImage(card){const c=schema().normalizeCard(card),raw=card?.legacyFullCardImage||global.SizaCardCatalog?.get?.(c.id)?.legacyFullCardImage||'';if(!raw)return'';if(/^(?:https?:|data:|\/)/i.test(raw))return raw;return '/siza-mobile-test/'+String(raw).replace(/^\.\//,'');}

function manaHtml(card,opts={}){
 const c=schema().normalizeCard(card),colored=Object.values(c.pips||{}).reduce((a,b)=>a+b,0),generic=Math.max(0,c.cost-colored),parts=[],mobile=opts.variant==='mobile';
 if(generic)parts.push(mobile?`<span class="mana c">${generic}</span>`:`<span class="sizaMana sizaManaGeneric">${generic}</span>`);
 for(const k of schema().COLORS)for(let i=0;i<(c.pips?.[k]||0);i++)parts.push(mobile?`<span class="mana ${k.toLowerCase()}">${k}</span>`:`<span class="sizaMana sizaMana${k}">${k}</span>`);
 return parts.join('')||(mobile?'<span class="mana c">0</span>':'<span class="sizaMana sizaManaGeneric">0</span>');
}

function artHtml(card,opts={}){
 const c=schema().normalizeCard(card),t=c.artTransform,mobile=opts.variant==='mobile';
 if(c.artUrl)return `<img class="${mobile?'generatedArtImageV1':'sizaGeneratedArt'}" src="${esc(c.artUrl)}" alt="" draggable="false" style="object-position:${t.x}% ${t.y}%;transform:scale(${t.scale})">`;
 if(mobile)return `<span class="artGlyph">${esc(c.glyph||'✦')}</span><span class="artLabel">${esc(c.subtype||c.cardType)}</span>`;
 return `<div class="sizaGeneratedArtFallback"><span>${esc(c.glyph||'✦')}</span><small>${esc(c.subtype||c.cardType)}</small></div>`;
}

function difficultyText(card){const c=schema().normalizeCard(card);return c.cardType==='Land'?'RES':String(c.difficulty);}
function typeLine(card){const c=schema().normalizeCard(card);return `${esc(c.cardType)}${c.subtype?' — '+esc(c.subtype):''}`;}
function typeClass(card){return 'type-'+schema().normalizeCard(card).cardType.toLowerCase();}
function rulesHtml(c){return `<div class="sizaCardRulesTextV2">${esc(c.rules)}</div>${c.flavor?`<div class="sizaGeneratedFlavor flavor sizaCardFlavorV2">${esc(c.flavor)}</div>`:''}`;}
function printedCard(card,variant,opts={}){const c=schema().normalizeCard(card),src=legacyImage(card);if(!src)return'';const classes=variant==='mobile'?['sizaCard','generatedCardV1','sizaCanonicalPrintedCard',typeClass(c),esc(c.art||c.affinity||'multi')]:['sizaGeneratedCard','sizaCanonicalPrintedCard',typeClass(c),`affinity-${esc(c.affinity||'multi')}`];if(opts.compact)classes.push('compact');return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}"><img class="sizaCanonicalPrintedImage" src="${esc(src)}" alt="${esc(c.name)}" draggable="false"></article>`;}

function renderStandardCard(card,opts={}){
 const printed=printedCard(card,'standard',opts);if(printed)return printed;
 const c=schema().normalizeCard(card),validation=schema().validateCard(c),classes=['sizaGeneratedCard','sizaCardTemplateV2',`affinity-${esc(c.affinity||'multi')}`,typeClass(c)],s=stats(c,opts);
 if(opts.compact)classes.push('compact');if(!validation.valid)classes.push('invalid');
 return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}"><div class="sizaGeneratedInner sizaCardFrameV2"><header class="sizaGeneratedTitle sizaCardHeaderV2"><span class="sizaCardNameV2">${esc(c.name)}</span><span class="sizaGeneratedDifficulty sizaCardDifficultyV2">${difficultyText(c)}</span></header><div class="sizaGeneratedArtWindow sizaCardArtV2">${artHtml(c)}</div><div class="sizaGeneratedType sizaCardTypeV2">${typeLine(c)}</div><div class="sizaGeneratedRules sizaCardRulesV2">${rulesHtml(c)}</div><footer class="sizaGeneratedFooter sizaCardFooterV2"><span class="sizaCardSetV2">${esc(c.setCode)} · ${esc(c.cardNumber)}</span>${c.cardType==='Creature'&&s.power!=null?`<span class="sizaGeneratedStats sizaCardStatsV2">${s.power}/${s.toughness}</span>`:'<span class="sizaCardBrandV2">SIZA</span>'}</footer></div></article>`;
}

function renderMobileCard(card,opts={}){
 const printed=printedCard(card,'mobile',opts);if(printed)return printed;
 const c=schema().normalizeCard(card),s=stats(c,opts),risk=opts.risk??(c.cardType==='Land'?'RES':String(c.difficulty));
 return `<article class="sizaCard generatedCardV1 sizaCardTemplateV2 ${typeClass(c)} ${esc(c.art||c.affinity||'multi')}"><div class="cardInner sizaCardFrameV2"><header class="cardName sizaCardHeaderV2"><span class="sizaCardNameV2">${esc(c.name)}</span><span class="cardRisk sizaCardDifficultyV2">${esc(risk)}</span></header><div class="cardArt sizaCardArtV2 ${esc(c.art||c.affinity||'multi')}">${artHtml(c,{variant:'mobile'})}</div><div class="typeLine sizaCardTypeV2">${typeLine(c)}</div><div class="rulesBox sizaCardRulesV2">${rulesHtml(c)}</div><footer class="sizaCardFooterV2"><span class="sizaCardSetV2">${esc(c.setCode||'SZA')}</span>${c.cardType==='Creature'&&s.power!=null?`<span class="pt sizaCardStatsV2">${s.power}/${s.toughness}</span>`:'<span class="sizaCardBrandV2">SIZA</span>'}</footer></div></article>`;
}

function renderCard(card,opts={}){return opts.variant==='mobile'?renderMobileCard(card,opts):renderStandardCard(card,opts);}

function renderStandardThumb(card,opts={}){
 const c=schema().normalizeCard(card),src=legacyImage(card);if(src)return `<div class="sizaGeneratedThumb sizaCanonicalPrintedThumb" data-card-id="${esc(c.id)}"><img class="sizaCanonicalPrintedImage" src="${esc(src)}" alt="${esc(c.name)}" draggable="false"></div>`;
 const s=stats(c,opts);
 return `<div class="sizaGeneratedThumb sizaCardThumbV2 affinity-${esc(c.affinity||'multi')} ${typeClass(c)}" data-card-id="${esc(c.id)}"><div class="sizaCardThumbHeaderV2"><span class="sizaGeneratedThumbName">${esc(c.name)}</span></div><div class="sizaGeneratedThumbArt">${artHtml(c)}</div><div class="sizaGeneratedThumbType">${esc(c.subtype||c.cardType)}</div>${c.cardType==='Creature'&&s.power!=null?`<div class="sizaGeneratedThumbStats">${s.power}/${s.toughness}</div>`:''}</div>`;
}

function renderMobileThumb(card,opts={}){
 const c=schema().normalizeCard(card),src=legacyImage(card);if(src)return `<div class="generatedFaceSlotV1"><div class="generatedCardThumbV1 sizaCanonicalPrintedThumb"><img class="sizaCanonicalPrintedImage" src="${esc(src)}" alt="${esc(c.name)}" draggable="false"></div></div>`;
 const s=stats(c,opts);
 return `<div class="generatedFaceSlotV1"><div class="generatedCardThumbV1 sizaCardThumbV2 ${typeClass(c)} ${esc(c.art||c.affinity||'multi')}"><div class="sizaCardThumbHeaderV2"><div class="generatedThumbNameV1">${esc(c.name)}</div></div><div class="generatedThumbArtV1">${artHtml(c,{variant:'mobile'})}</div><div class="generatedThumbTypeV1">${esc(c.subtype||c.cardType)}</div>${c.cardType==='Creature'&&s.power!=null?`<div class="generatedThumbPtV1">${s.power}/${s.toughness}</div>`:''}</div></div>`;
}

function renderThumb(card,opts={}){return opts.variant==='mobile'?renderMobileThumb(card,opts):renderStandardThumb(card,opts);}
function mount(target,card,opts={}){const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw new Error('Renderer target not found.');el.innerHTML=opts.thumb?renderThumb(card,opts):renderCard(card,opts);return el.firstElementChild;}

global.SizaCardRenderer=Object.freeze({renderCard,renderThumb,mount,manaHtml,artHtml});
})(window);
