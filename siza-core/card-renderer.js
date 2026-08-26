(function(global){
'use strict';

const RENDERER_SRC=typeof document!=='undefined'&&document.currentScript?.src?document.currentScript.src:'';
const FRAME_STANDARD_BASE_URL=RENDERER_SRC?new URL('assets/frames/standard/frame_standard_base.svg?v=094b0ee6',RENDERER_SRC).href:'../siza-core/assets/frames/standard/frame_standard_base.svg?v=094b0ee6';
const FALLBACK_TEMPLATE_PART_KEYS=['frame_base','affinity_overlay','crystal_rail','title_plate','difficulty_badge','art_frame','type_bar','rules_panel','stat_left','stat_right','footer','ornament_overlay'];

(function loadSharedCardStyles(){
 if(typeof document==='undefined'||!RENDERER_SRC)return;
 const styles=[['siza-card-template-v4-css','card-template-v4.css'],['siza-frame-standard-v5-css','frame-standard-v5.css?v=9']];
 for(const[id,path]of styles){if(document.getElementById(id))continue;const link=document.createElement('link');link.id=id;link.rel='stylesheet';link.href=new URL(path,RENDERER_SRC).href;document.head.appendChild(link);}
 if(!document.getElementById('siza-runtime-extra-v6-css')){
  const style=document.createElement('style');style.id='siza-runtime-extra-v6-css';style.textContent=`
.sizaTemplatePartV6{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none;user-select:none}
.sizaTemplatePartV6.part-affinity_overlay{z-index:5}.sizaTemplatePartV6.part-rules_panel{z-index:4}.sizaTemplatePartV6.part-art_frame{z-index:6}.sizaTemplatePartV6.part-ornament_overlay{z-index:7}.sizaTemplatePartV6.part-title_plate{z-index:7}.sizaTemplatePartV6.part-type_bar{z-index:8}.sizaTemplatePartV6.part-crystal_rail{z-index:9}.sizaTemplatePartV6.part-footer{z-index:10}.sizaTemplatePartV6.part-difficulty_badge{z-index:11}.sizaTemplatePartV6.part-stat_left,.sizaTemplatePartV6.part-stat_right{z-index:12}
.tpl-title_plate .sizaCardTitlePlateV3,.tpl-type_bar .sizaCardTypeV2,.tpl-rules_panel .sizaCardRulesV2,.tpl-footer .sizaCardFooterV2,.tpl-difficulty_badge .sizaManafestBadgeV3,.tpl-stat_left .sizaStatLeftV3,.tpl-stat_right .sizaStatRightV3,.tpl-crystal_rail .sizaCardCrystalRailV3{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.tpl-title_plate .sizaCardThumbHeaderV2,.tpl-type_bar .sizaGeneratedThumbType,.tpl-difficulty_badge .sizaThumbDifficultyV3,.tpl-crystal_rail .sizaThumbCrystalRailV3,.tpl-stat_left .sizaGeneratedThumbStats,.tpl-stat_right .sizaGeneratedThumbStats{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.sizaBattleSpriteV1{display:none}
.arenaMiniCard .generatedFaceSlotV1,.arenaMiniCard .generatedCardThumbV1{position:absolute!important;inset:0!important;width:100%!important;height:100%!important}
.arenaMiniCard .generatedCardThumbV1.hasBattleSpriteV1{border:0!important;background:transparent!important;overflow:visible!important}
.arenaMiniCard .generatedCardThumbV1.hasBattleSpriteV1>:not(.sizaBattleSpriteV1){display:none!important}
.arenaMiniCard .generatedCardThumbV1.hasBattleSpriteV1 .sizaBattleSpriteV1{display:block;position:absolute;inset:0;z-index:25;overflow:hidden;border-radius:8px;background:radial-gradient(circle at 50% 52%,rgba(29,74,100,.7),rgba(4,14,22,.96) 72%);pointer-events:none}
.arenaMiniCard .sizaBattleSpriteV1 img{position:absolute;max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;transform-origin:center;filter:drop-shadow(0 6px 8px rgba(0,0,0,.55))}
.arenaMiniCard .sizaBattleSpriteNameV1{position:absolute;z-index:2;left:4px;right:4px;bottom:4px;padding:3px 4px;border-radius:5px;background:rgba(3,11,18,.78);color:#f1e4c7;font:700 7px Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:left}
.arenaMiniCard .sizaBattleSpriteStatsV1{position:absolute;z-index:3;right:4px;top:4px;padding:2px 4px;border-radius:999px;background:rgba(3,11,18,.82);border:1px solid rgba(211,170,93,.62);color:#f5e5bd;font:800 8px Georgia,serif}
`;
  document.head.appendChild(style);
 }
})();

function esc(value){return String(value??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function schema(){if(!global.SizaCardSchema)throw new Error('SizaCardSchema must load before SizaCardRenderer.');return global.SizaCardSchema;}
function templateKeys(){return schema().TEMPLATE_PART_KEYS||FALLBACK_TEMPLATE_PART_KEYS;}
function stats(card,opts={}){const c=schema().normalizeCard(card),s=opts.stats||{};return{power:s.power??opts.power??c.power,toughness:s.toughness??opts.toughness??c.toughness};}
function typeClass(card){return 'type-'+schema().normalizeCard(card).cardType.toLowerCase();}
function affinityClass(card){const c=schema().normalizeCard(card);return String(c.art||c.affinity||'multi').toLowerCase();}
function titleLengthClass(value){const n=String(value??'').trim().length;return n>34?'titleXLV4':n>22?'titleLongV4':'';}
function templatePart(card,key){const c=schema().normalizeCard(card);return c.templateParts?.[key]||'';}
function templateClasses(card){const c=schema().normalizeCard(card);return templateKeys().filter(key=>c.templateParts?.[key]).map(key=>'tpl-'+key);}
function templateLayerHtml(card,key){const src=templatePart(card,key);return src?`<img class="sizaTemplatePartV6 part-${esc(key)}" src="${esc(src)}" alt="" aria-hidden="true" draggable="false" onerror="this.style.display='none'">`:'';}
function templateLayersHtml(card){return templateKeys().filter(key=>key!=='frame_base').map(key=>templateLayerHtml(card,key)).join('');}
function frameHtml(card,extraClass=''){const c=schema().normalizeCard(card),src=c.templateParts?.frame_base||c.frameUrl||FRAME_STANDARD_BASE_URL;return `<img class="sizaFrameStandardBaseV5${extraClass?' '+extraClass:''}" src="${esc(src)}" alt="" aria-hidden="true" draggable="false" onerror="this.onerror=null;this.src='${esc(FRAME_STANDARD_BASE_URL)}'">`;}

function artFallbackHtml(c,mobile=false,hidden=false){const attrs=hidden?' hidden':'';if(mobile)return `<span class="sizaArtFallbackV5"${attrs}><span class="artGlyph">${esc(c.glyph||'✦')}</span><span class="artLabel">${esc(c.subtype||c.cardType)}</span></span>`;return `<div class="sizaGeneratedArtFallback sizaArtFallbackV5"${attrs}><span>${esc(c.glyph||'✦')}</span><small>${esc(c.subtype||c.cardType)}</small></div>`;}
function artHtml(card,opts={}){const c=schema().normalizeCard(card),t=c.artTransform,mobile=opts.variant==='mobile';if(c.artUrl)return `<span class="sizaArtHostV5"><img class="${mobile?'generatedArtImageV1':'sizaGeneratedArt'}" src="${esc(c.artUrl)}" alt="" draggable="false" style="object-position:${t.x}% ${t.y}%;transform:scale(${t.scale})" onerror="this.hidden=true;this.nextElementSibling.hidden=false">${artFallbackHtml(c,mobile,true)}</span>`;return artFallbackHtml(c,mobile,false);}
function battleSpriteHtml(card,opts={}){const c=schema().normalizeCard(card);if(!c.battleSpriteUrl)return'';const t=c.battleSpriteTransform,s=stats(c,opts),hasStats=c.cardType==='Creature'&&s.power!=null;return `<span class="sizaBattleSpriteV1"><img src="${esc(c.battleSpriteUrl)}" alt="" draggable="false" style="left:${t.x}%;top:${t.y}%;transform:translate(-50%,-50%) scale(${t.scale})" onerror="this.parentElement.style.display='none'"><span class="sizaBattleSpriteNameV1">${esc(c.name)}</span>${hasStats?`<span class="sizaBattleSpriteStatsV1">${esc(s.power)}/${esc(s.toughness)}</span>`:''}</span>`;}

function crystalRequirement(card){const c=schema().normalizeCard(card),out=[];for(const k of schema().COLORS){const count=Math.max(0,Math.trunc(Number(c.pips?.[k])||0));for(let i=0;i<count;i++)out.push(k);}return out;}
function crystalMetrics(count){if(count<=0)return{size:0,gap:0};if(count<=3)return{size:29,gap:4};const gap=count<=5?2.4:count<=8?1.7:1.1;return{size:Math.max(1,(96-gap*(count-1))/count),gap};}
function crystalItems(card,opts={}){const requirement=opts.requirement||crystalRequirement(card),names={U:'Azul',R:'Rojo',G:'Verde',W:'Blanco',B:'Negro'},metrics=crystalMetrics(requirement.length);return requirement.map((k,index)=>`<span class="sizaCrystalV3 crystal-${k.toLowerCase()}" data-crystal-color="${k}" data-crystal-index="${index}" title="Cristal ${names[k]||k}" aria-label="Cristal ${names[k]||k}" style="flex:0 0 ${metrics.size}%;height:${metrics.size}%;max-height:none"><span class="sizaCrystalCapV3"></span><span class="sizaCrystalGlassV3"><i class="sizaCrystalGemV3" style="left:14%;right:14%;top:15%;bottom:14%"></i></span><span class="sizaCrystalBaseV3"></span></span>`).join('');}
function crystalRailHtml(card,className='sizaCardCrystalRailV3'){const requirement=crystalRequirement(card),metrics=crystalMetrics(requirement.length),empty=requirement.length===0?' is-empty':'';return `<div class="${className}${empty}" data-crystal-count="${requirement.length}" style="--siza-crystal-count:${requirement.length};border:0!important;background:transparent!important;box-shadow:none!important;padding:0!important;gap:${metrics.gap}%">${crystalItems(card,{requirement})}</div>`;}
function crystalHtml(card){return crystalItems(card);}function manaHtml(card){return crystalHtml(card);}
function difficultyText(card){const c=schema().normalizeCard(card);return c.cardType==='Land'?'RES':String(c.difficulty);}
function printedType(card){const c=schema().normalizeCard(card),base=c.cardType==='Creature'?'INVOCACIÓN':c.cardType==='Instant'?'REACCIÓN':c.cardType==='Artifact'?'RELIQUIA':c.cardType==='Land'?'RESERVA':String(c.cardType).toUpperCase(),subtype=c.cardType==='Artifact'&&schema().isEquipmentCard?.(c)?(c.subtype||'EQUIPO'):c.subtype;return `${base}${subtype?' — '+String(subtype).toUpperCase():''}`;}
function rulesHtml(c){return `<div class="sizaCardRulesTextV2">${esc(c.rules)}</div>${c.flavor?`<div class="sizaGeneratedFlavor flavor sizaCardFlavorV2">“${esc(c.flavor)}”</div>`:''}`;}

function bodyHtml(card,opts={}){
 const c=schema().normalizeCard(card),s=stats(c,opts),mobile=opts.variant==='mobile',risk=mobile?(opts.risk??difficultyText(c)):difficultyText(c),hasStats=c.cardType==='Creature'&&s.power!=null,titleClass=titleLengthClass(c.name);
 return `<div class="sizaGeneratedInner sizaCardFrameV2 sizaQueenLayoutV3">
  ${frameHtml(c)}${templateLayersHtml(c)}
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
function renderStandardCard(card,opts={}){const c=schema().normalizeCard(card),validation=schema().validateCard(c),classes=['sizaGeneratedCard','sizaCardTemplateV2','sizaCardTemplateQueenV3',`affinity-${esc(affinityClass(c))}`,typeClass(c),...templateClasses(c)];if(opts.compact)classes.push('compact');if(!validation.valid)classes.push('invalid');return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}" data-template="${esc(c.template)}">${bodyHtml(c,opts)}</article>`;}
function renderMobileCard(card,opts={}){const c=schema().normalizeCard(card),classes=['sizaCard','generatedCardV1','sizaCardTemplateV2','sizaCardTemplateQueenV3',typeClass(c),esc(affinityClass(c)),...templateClasses(c)];return `<article class="${classes.join(' ')}" data-card-id="${esc(c.id)}" data-template="${esc(c.template)}">${bodyHtml(c,{...opts,variant:'mobile'})}</article>`;}
function renderCard(card,opts={}){return opts.variant==='mobile'?renderMobileCard(card,opts):renderStandardCard(card,opts);}

function thumbBody(card,opts={}){const c=schema().normalizeCard(card),s=stats(c,opts),hasStats=c.cardType==='Creature'&&s.power!=null;return `${frameHtml(c,'sizaFrameStandardThumbV5')}${templateLayersHtml(c)}${crystalRailHtml(c,'sizaThumbCrystalRailV3')}<div class="sizaCardThumbHeaderV2"><span class="sizaGeneratedThumbName">${esc(c.name)}</span></div><span class="sizaThumbDifficultyV3">${esc(difficultyText(c))}</span><div class="sizaGeneratedThumbArt">${artHtml(c,opts)}</div><div class="sizaGeneratedThumbType">${esc(printedType(c))}</div>${hasStats?`<div class="sizaGeneratedThumbStats">${esc(s.power)}/${esc(s.toughness)}</div>`:''}${battleSpriteHtml(c,opts)}`;}
function renderStandardThumb(card,opts={}){const c=schema().normalizeCard(card);return `<div class="sizaGeneratedThumb sizaCardThumbV2 sizaCardThumbQueenV3 affinity-${esc(affinityClass(c))} ${typeClass(c)} ${templateClasses(c).join(' ')}" data-card-id="${esc(c.id)}" data-template="${esc(c.template)}">${thumbBody(c,opts)}</div>`;}
function renderMobileThumb(card,opts={}){const c=schema().normalizeCard(card),spriteClass=c.battleSpriteUrl?' hasBattleSpriteV1':'';return `<div class="generatedFaceSlotV1"><div class="generatedCardThumbV1 sizaCardThumbV2 sizaCardThumbQueenV3 ${typeClass(c)} ${esc(affinityClass(c))} ${templateClasses(c).join(' ')}${spriteClass}" data-template="${esc(c.template)}">${thumbBody(c,{...opts,variant:'mobile'})}</div></div>`;}
function renderThumb(card,opts={}){return opts.variant==='mobile'?renderMobileThumb(card,opts):renderStandardThumb(card,opts);}
function mount(target,card,opts={}){const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw new Error('Renderer target not found.');el.innerHTML=opts.thumb?renderThumb(card,opts):renderCard(card,opts);return el.firstElementChild;}

global.SizaCardRenderer=Object.freeze({renderCard,renderThumb,mount,manaHtml,artHtml,battleSpriteHtml,crystalHtml,crystalRequirement,templateLayerHtml});
})(window);
