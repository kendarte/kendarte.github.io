(function(global){
'use strict';

function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function schema(){if(!global.SizaCardSchema)throw new Error('SizaCardSchema must load before SizaCardRenderer.');return global.SizaCardSchema;}
function stats(card,opts={}){const c=schema().normalizeCard(card),s=opts.stats||{};return{power:s.power??opts.power??c.power,toughness:s.toughness??opts.toughness??c.toughness};}

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

function difficultyText(card){const c=schema().normalizeCard(card);return c.cardType==='Land'?'RESERVA':`D${c.difficulty}`;}
function typeLine(card){const c=schema().normalizeCard(card);return `${esc(c.cardType)}${c.subtype?' — '+esc(c.subtype):''}`;}

function renderStandardCard(card,opts={}){
 const c=schema().normalizeCard(card),validation=schema().validateCard(c),classes=['sizaGeneratedCard',`affinity-${esc(c.affinity||'multi')}`],s=stats(c,opts);
 if(opts.compact)classes.push('compact');if(!validation.valid)classes.push('invalid');
 return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}"><div class="sizaGeneratedDifficulty">${difficultyText(c)}</div><div class="sizaGeneratedInner"><header class="sizaGeneratedTitle"><span>${esc(c.name)}</span><span class="sizaGeneratedCost">${manaHtml(c)}</span></header><div class="sizaGeneratedArtWindow">${artHtml(c)}</div><div class="sizaGeneratedType">${typeLine(c)}</div><div class="sizaGeneratedRules">${esc(c.rules)}${c.flavor?`<div class="sizaGeneratedFlavor">${esc(c.flavor)}</div>`:''}</div>${c.cardType==='Creature'&&s.power!=null?`<div class="sizaGeneratedStats">${s.power}/${s.toughness}</div>`:''}<footer class="sizaGeneratedFooter"><span>${esc(c.setCode)} · ${esc(c.cardNumber)}</span><span>${esc(c.id)}</span></footer></div></article>`;
}

function renderMobileCard(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts),risk=opts.risk??(c.cardType==='Land'?'RESERVA':`D${c.difficulty}`);
 return `<article class="sizaCard generatedCardV1 ${esc(c.art||c.affinity||'multi')}"><div class="cardRisk">${esc(risk)}</div><div class="cardInner"><div class="cardName"><span>${esc(c.name)}</span><span class="manaCost">${manaHtml(c,{variant:'mobile'})}</span></div><div class="cardArt ${esc(c.art||c.affinity||'multi')}">${artHtml(c,{variant:'mobile'})}</div><div class="typeLine">${typeLine(c)}</div><div class="rulesBox">${esc(c.rules)}<div class="flavor">${esc(c.flavor||'')}</div></div>${c.cardType==='Creature'&&s.power!=null?`<div class="pt">${s.power}/${s.toughness}</div>`:''}</div></article>`;
}

function renderCard(card,opts={}){return opts.variant==='mobile'?renderMobileCard(card,opts):renderStandardCard(card,opts);}

function renderStandardThumb(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts);
 return `<div class="sizaGeneratedThumb affinity-${esc(c.affinity||'multi')}" data-card-id="${esc(c.id)}"><div class="sizaGeneratedThumbName">${esc(c.name)}</div><div class="sizaGeneratedThumbArt">${artHtml(c)}</div><div class="sizaGeneratedThumbType">${esc(c.subtype||c.cardType)}</div>${c.cardType==='Creature'&&s.power!=null?`<div class="sizaGeneratedThumbStats">${s.power}/${s.toughness}</div>`:''}</div>`;
}

function renderMobileThumb(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts);
 return `<div class="generatedFaceSlotV1"><div class="generatedCardThumbV1 ${esc(c.art||c.affinity||'multi')}"><div class="generatedThumbNameV1">${esc(c.name)}</div><div class="generatedThumbArtV1">${artHtml(c,{variant:'mobile'})}</div><div class="generatedThumbTypeV1">${esc(c.subtype||c.cardType)}</div>${c.cardType==='Creature'&&s.power!=null?`<div class="generatedThumbPtV1">${s.power}/${s.toughness}</div>`:''}</div></div>`;
}

function renderThumb(card,opts={}){return opts.variant==='mobile'?renderMobileThumb(card,opts):renderStandardThumb(card,opts);}
function mount(target,card,opts={}){const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw new Error('Renderer target not found.');el.innerHTML=opts.thumb?renderThumb(card,opts):renderCard(card,opts);return el.firstElementChild;}

global.SizaCardRenderer=Object.freeze({renderCard,renderThumb,mount,manaHtml,artHtml});
})(window);
