(function(global){
'use strict';

const CARD_SCHEMA_VERSION='1.0.0';
const CARD_TYPES=['Instant','Creature','Artifact','Land'];
const COLORS=['U','R','G','W','B'];

function clone(value){return JSON.parse(JSON.stringify(value));}
function finiteNumber(value,fallback=null){const n=Number(value);return Number.isFinite(n)?n:fallback;}
function int(value,fallback=0){const n=finiteNumber(value,fallback);return Math.trunc(n);}
function text(value,fallback=''){return String(value??fallback);}

function normalizePips(input={}){
 const out={};
 for(const k of COLORS){const n=Math.max(0,int(input?.[k],0));if(n)out[k]=n;}
 return out;
}

function normalizeArtTransform(input={}){
 return {
  x:Math.max(0,Math.min(100,finiteNumber(input?.x,50))),
  y:Math.max(0,Math.min(100,finiteNumber(input?.y,50))),
  scale:Math.max(.25,Math.min(4,finiteNumber(input?.scale,1)))
 };
}

function normalizeCard(input={}){
 const type=CARD_TYPES.includes(input.cardType)?input.cardType:(CARD_TYPES.includes(input.type)?input.type:'Creature');
 const power=input.force??input.power;
 const toughness=input.resistance??input.toughness;
 const card={
  schemaVersion:CARD_SCHEMA_VERSION,
  id:text(input.id,'card_'+Date.now()),
  name:text(input.name,'Carta sin nombre'),
  template:text(input.template,'standard'),
  cardType:type,
  type,
  subtype:text(input.subtype,''),
  affinity:text(input.affinity,'multi'),
  difficulty:Math.max(0,int(input.difficulty,0)),
  cost:Math.max(0,int(input.cost,0)),
  pips:normalizePips(input.pips||input.crystals),
  crystals:normalizePips(input.crystals||input.pips),
  artId:text(input.artId,''),
  artUrl:text(input.artUrl,''),
  artTransform:normalizeArtTransform(input.artTransform),
  rules:text(input.rules??input.text,''),
  text:text(input.text??input.rules,''),
  flavor:text(input.flavor,''),
  force:power==null?null:int(power,0),
  resistance:toughness==null?null:int(toughness,0),
  power:power==null?null:int(power,0),
  toughness:toughness==null?null:int(toughness,0),
  setCode:text(input.setCode,'SZA'),
  cardNumber:text(input.cardNumber,'000'),
  glyph:text(input.glyph,'✦'),
  art:text(input.art,input.affinity||'multi')
 };
 return card;
}

function validateCard(input={}){
 const card=normalizeCard(input),errors=[],warnings=[];
 if(!card.id.trim())errors.push('La carta necesita un ID.');
 if(!card.name.trim())errors.push('La carta necesita un nombre.');
 if(!CARD_TYPES.includes(card.cardType))errors.push('Tipo de carta inválido.');
 if(card.cardType!=='Land'&&card.difficulty<=0)warnings.push('La dificultad es 0.');
 if(card.cardType==='Creature'){
  if(card.power==null||card.toughness==null)errors.push('Una Creature necesita Fuerza y Resistencia.');
 }
 if(card.cardType!=='Creature'&&(card.power!=null||card.toughness!=null))warnings.push('Las estadísticas P/T sólo se muestran en Creature.');
 if(!card.rules.trim()&&card.cardType!=='Land')warnings.push('La carta no tiene texto de reglas.');
 if(card.artUrl&&/cards-v\d+\//i.test(card.artUrl))warnings.push('artUrl parece apuntar a una carta completa legada, no a arte puro.');
 if(card.artTransform.scale<.25||card.artTransform.scale>4)errors.push('La escala de arte está fuera del rango permitido.');
 return {valid:errors.length===0,errors,warnings,card};
}

function cardFromMobileShape(input={}){return normalizeCard(input);}
function cardToMobileShape(input={}){
 const c=normalizeCard(input);
 const out={id:c.id,name:c.name,type:c.cardType,cost:c.cost,difficulty:c.difficulty,pips:clone(c.pips),text:c.rules,flavor:c.flavor,art:c.art,glyph:c.glyph,artUrl:c.artUrl,artTransform:clone(c.artTransform)};
 if(c.subtype)out.subtype=c.subtype;
 if(c.cardType==='Creature'){out.power=c.power;out.toughness=c.toughness;}
 return out;
}

global.SizaCardSchema=Object.freeze({
 VERSION:CARD_SCHEMA_VERSION,
 CARD_TYPES:Object.freeze(CARD_TYPES.slice()),
 COLORS:Object.freeze(COLORS.slice()),
 normalizeCard,
 validateCard,
 cardFromMobileShape,
 cardToMobileShape,
 normalizeArtTransform,
 normalizePips
});
})(window);
