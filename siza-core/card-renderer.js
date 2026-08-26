(function(global){
'use strict';

(function loadTemplateV4(){
 if(typeof document==='undefined'||document.getElementById('siza-card-template-v4-css'))return;
 const script=document.currentScript;
 if(!script?.src)return;
 const link=document.createElement('link');
 link.id='siza-card-template-v4-css';
 link.rel='stylesheet';
 link.href=new URL('card-template-v4.css',script.src).href;
 document.head.appendChild(link);
})();

function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function schema(){if(!global.SizaCardSchema)throw new Error('SizaCardSchema must load before SizaCardRenderer.');return global.SizaCardSchema;}
function stats(card,opts={}){const c=schema().normalizeCard(card),s=opts.stats||{};return{power:s.power??opts.power??c.power,toughness:s.toughness??opts.toughness??c.toughness};}
function typeClass(card){return 'type-'+schema().normalizeCard(card).cardType.toLowerCase();}
function affinityClass(card){const c=schema().normalizeCard(card);return String(c.art||c.affinity||'multi').toLowerCase();}
function titleLengthClass(value){const n=String(value??'').trim().length;return n>34?'titleXLV4':n>22?'titleLongV4':'';}

function artHtml(card,opts={}){
 const c=schema().normalizeCard(card),t=c.artTransform,mobile=opts.variant==='mobile';
 if(c.artUrl)return `<img class="${mobile?'generatedArtImageV1':'sizaGeneratedArt'}" src="${esc(c.artUrl)}" alt="" draggable="false" style="object-position:${t.x}% ${t.y}%;transform:scale(${t.scale})">`;
 if(mobile)return `<span class="artGlyph">${esc(c.glyph||'✦')}</span><span class="artLabel">${esc(c.subtype||c.cardType)}</span>`;
 return `<div class="sizaGeneratedArtFallback"><span>${esc(c.glyph||'✦')}</span><small>${esc(c.subtype||c.cardType)}</small></div>`;
}

function crystalRequirement(card){
 const c=schema().normalizeCard(card),out=[];
 for(const k of schema().COLORS){
  const count=Math.max(0,Math.trunc(Number(c.pips?.[k])||0));
  for(let i=0;i<count;i++)out.push(k);
 }
 return out;
}
function crystalMetrics(count){
 if(count<=0)return{size:0,gap:0};
 if(count<=3)return{size:29,gap:4};
 const gap=count<=5?2.4:count<=8?1.7:1.1;
 return{size:Math.max(1,(96-gap*(count-1))/count),gap};
}
function crystalItems(card,opts={}){
 const requirement=opts.requirement||crystalRequirement(card),names={U:'Azul',R:'Rojo',G:'Verde',W:'Blanco',B:'Negro'},metrics=crystalMetrics(requirement.length);
 return requirement.map((k,index)=>`<span class="sizaCrystalV3 crystal-${k.toLowerCase()}" data-crystal-color="${k}" data-crystal-index="${index}" title="Cristal ${names[k]||k}" aria-label="Cristal ${names[k]||k}" style="flex:0 0 ${metrics.size}%;height:${metrics.size}%;max-height:none"><span class="sizaCrystalCapV3"></span><span class="sizaCrystalGlassV3"><i class="sizaCrystalGemV3" style="left:14%;right:14%;top:15%;bottom:14%"></i></span><span class="sizaCrystalBaseV3"></span></span>`).join('');
}
function crystalRailHtml(card,className='sizaCardCrystalRailV3'){
 const requirement=crystalRequirement(card),metrics=crystalMetrics(requirement.length),empty=requirement.length===0?' is-empty':'';
 return `<div class="${className}${empty}" data-crystal-count="${requirement.length}" style="--siza-crystal-count:${requirement.length};border:0!important;background:transparent!important;box-shadow:none!important;padding:0!important;gap:${metrics.gap}%">${crystalItems(card,{requirement})}</div>`;
}
function crystalHtml(card){return crystalItems(card);}
function manaHtml(card){return crystalHtml(card);}

function difficultyText(card){const c=schema().normalizeCard(card);return c.cardType==='Land'?'RES':String(c.difficulty);}
function printedType(card){
 const c=schema().normalizeCard(card);
 const base=c.cardType==='Creature'?'INVOCACIÓN':c.cardType==='Instant'?'REACCIÓN':c.cardType==='Artifact'?'RELIQUIA':c.cardType==='Land'?'RESERVA':String(c.cardType).toUpperCase();
 const subtype=c.cardType==='Artifact'&&schema().isEquipmentCard?.(c)?(c.subtype||'EQUIPO'):c.subtype;
 return `${base}${subtype?' — '+String(subtype).toUpperCase():''}`;
}
function rulesHtml(c){return `<div class="sizaCardRulesTextV2">${esc(c.rules)}</div>${c.flavor?`<div class="sizaGeneratedFlavor flavor sizaCardFlavorV2">“${esc(c.flavor)}”</div>`:''}`;}

function bodyHtml(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts),mobile=opts.variant==='mobile',risk=mobile?(opts.risk??difficultyText(c)):difficultyText(c),hasStats=c.cardType==='Creature'&&s.power!=null,titleClass=titleLengthClass(c.name);
 return `<div class="sizaGeneratedInner sizaCardFrameV2 sizaQueenLayoutV3">
  <div class="sizaCardTitlePlateV3 sizaGeneratedTitle"><span class="sizaCardNameV2${titleClass?' '+titleClass:''}">${esc(c.name)}</span></div>
  <div class="sizaCardDifficultyV2 sizaManafestBadgeV3 sizaGeneratedDifficulty${mobile?' cardRisk':''}">${esc(risk)}</div>
  ${crystalRailHtml(c)}
  <div class="sizaGeneratedArtWindow sizaCardArtV2">${artHtml(c,{variant:mobile?'mobile':'standard'})}</div>
  <div class="sizaGeneratedType sizaCardTypeV2">${esc(printedType(c))}</div>
  <div class="sizaGeneratedRules sizaCardRulesV2">${rulesHtml(c)}</div>
  ${hasStats?`<div class="sizaStatPlateV3 sizaStatLeftV3"><span class="sizaStatValueV4">${esc(s.power)}</span><small class="sizaStatLabelV4">ATAQUE</small></div><div class="sizaStatPlateV3 sizaStatRightV3"><span class="sizaStatValueV4">${esc(s.toughness)}</span><small class="sizaStatLabelV4">DEFENSA</small></div>`:''}
  <footer class="sizaGeneratedFooter sizaCardFooterV2"><span class="sizaCardSetV2">${esc(c.setCode||'SZA')} · ${esc(c.cardNumber||'000')}</span></footer>
 </div>`;
}

function renderStandardCard(card,opts={}){
 const c=schema().normalizeCard(card),validation=schema().validateCard(c),classes=['sizaGeneratedCard','sizaCardTemplateV2','sizaCardTemplateQueenV3',`affinity-${esc(affinityClass(c))}`,typeClass(c)];
 if(opts.compact)classes.push('compact');if(!validation.valid)classes.push('invalid');
 return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}">${bodyHtml(c,opts)}</article>`;
}

function renderMobileCard(card,opts={}){
 const c=schema().normalizeCard(card),classes=['sizaCard','generatedCardV1','sizaCardTemplateV2','sizaCardTemplateQueenV3',typeClass(c),esc(affinityClass(c))];
 return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}">${bodyHtml(c,{...opts,variant:'mobile'})}</article>`;
}

function renderCard(card,opts={}){return opts.variant==='mobile'?renderMobileCard(card,opts):renderStandardCard(card,opts);}

function thumbBody(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts),hasStats=c.cardType==='Creature'&&s.power!=null;
 return `${crystalRailHtml(c,'sizaThumbCrystalRailV3')}<div class="sizaCardThumbHeaderV2"><span class="sizaGeneratedThumbName">${esc(c.name)}</span></div><span class="sizaThumbDifficultyV3">${esc(difficultyText(c))}</span><div class="sizaGeneratedThumbArt">${artHtml(c,opts)}</div><div class="sizaGeneratedThumbType">${esc(printedType(c))}</div>${hasStats?`<div class="sizaGeneratedThumbStats">${esc(s.power)}/${esc(s.toughness)}</div>`:''}`;
}
function renderStandardThumb(card,opts={}){
 const c=schema().normalizeCard(card);return `<div class="sizaGeneratedThumb sizaCardThumbV2 sizaCardThumbQueenV3 affinity-${esc(affinityClass(c))} ${typeClass(c)}" data-card-id="${esc(c.id)}">${thumbBody(c,opts)}</div>`;
}
function renderMobileThumb(card,opts={}){
 const c=schema().normalizeCard(card);return `<div class="generatedFaceSlotV1"><div class="generatedCardThumbV1 sizaCardThumbV2 sizaCardThumbQueenV3 ${typeClass(c)} ${esc(affinityClass(c))}">${thumbBody(c,{...opts,variant:'mobile'})}</div></div>`;
}
function renderThumb(card,opts={}){return opts.variant==='mobile'?renderMobileThumb(card,opts):renderStandardThumb(card,opts);}
function mount(target,card,opts={}){const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw new Error('Renderer target not found.');el.innerHTML=opts.thumb?renderThumb(card,opts):renderCard(card,opts);return el.firstElementChild;}

global.SizaCardRenderer=Object.freeze({renderCard,renderThumb,mount,manaHtml,artHtml,crystalHtml,crystalRequirement});
})(window);
