(function(global){
'use strict';

function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function schema(){if(!global.SizaCardSchema)throw new Error('SizaCardSchema must load before SizaCardRenderer.');return global.SizaCardSchema;}

function manaHtml(card){
 const c=schema().normalizeCard(card),colored=Object.values(c.pips||{}).reduce((a,b)=>a+b,0),generic=Math.max(0,c.cost-colored),parts=[];
 if(generic)parts.push(`<span class="sizaMana sizaManaGeneric">${generic}</span>`);
 for(const k of schema().COLORS)for(let i=0;i<(c.pips?.[k]||0);i++)parts.push(`<span class="sizaMana sizaMana${k}">${k}</span>`);
 return parts.join('')||'<span class="sizaMana sizaManaGeneric">0</span>';
}

function artHtml(card){
 const c=schema().normalizeCard(card),t=c.artTransform;
 if(c.artUrl)return `<img class="sizaGeneratedArt" src="${esc(c.artUrl)}" alt="" draggable="false" style="object-position:${t.x}% ${t.y}%;transform:scale(${t.scale})">`;
 return `<div class="sizaGeneratedArtFallback"><span>${esc(c.glyph||'✦')}</span><small>${esc(c.subtype||c.cardType)}</small></div>`;
}

function difficultyText(card){const c=schema().normalizeCard(card);return c.cardType==='Land'?'RESERVA':`D${c.difficulty}`;}
function typeLine(card){const c=schema().normalizeCard(card);return `${esc(c.cardType)}${c.subtype?' — '+esc(c.subtype):''}`;}
function statsHtml(card){const c=schema().normalizeCard(card);if(c.cardType!=='Creature'||c.power==null)return'';return `<div class="sizaGeneratedStats">${c.power}/${c.toughness}</div>`;}

function renderCard(card,opts={}){
 const c=schema().normalizeCard(card),validation=schema().validateCard(c),classes=['sizaGeneratedCard',`affinity-${esc(c.affinity||'multi')}`];
 if(opts.compact)classes.push('compact');
 if(!validation.valid)classes.push('invalid');
 return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}"><div class="sizaGeneratedDifficulty">${difficultyText(c)}</div><div class="sizaGeneratedInner"><header class="sizaGeneratedTitle"><span>${esc(c.name)}</span><span class="sizaGeneratedCost">${manaHtml(c)}</span></header><div class="sizaGeneratedArtWindow">${artHtml(c)}</div><div class="sizaGeneratedType">${typeLine(c)}</div><div class="sizaGeneratedRules">${esc(c.rules)}${c.flavor?`<div class="sizaGeneratedFlavor">${esc(c.flavor)}</div>`:''}</div>${statsHtml(c)}<footer class="sizaGeneratedFooter"><span>${esc(c.setCode)} · ${esc(c.cardNumber)}</span><span>${esc(c.id)}</span></footer></div></article>`;
}

function renderThumb(card,opts={}){
 const c=schema().normalizeCard(card),power=opts.power??c.power,toughness=opts.toughness??c.toughness;
 return `<div class="sizaGeneratedThumb affinity-${esc(c.affinity||'multi')}" data-card-id="${esc(c.id)}"><div class="sizaGeneratedThumbName">${esc(c.name)}</div><div class="sizaGeneratedThumbArt">${artHtml(c)}</div><div class="sizaGeneratedThumbType">${esc(c.subtype||c.cardType)}</div>${c.cardType==='Creature'&&power!=null?`<div class="sizaGeneratedThumbStats">${power}/${toughness}</div>`:''}</div>`;
}

function mount(target,card,opts={}){
 const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw new Error('Renderer target not found.');
 el.innerHTML=opts.thumb?renderThumb(card,opts):renderCard(card,opts);return el.firstElementChild;
}

global.SizaCardRenderer=Object.freeze({renderCard,renderThumb,mount,manaHtml,artHtml});
})(window);
