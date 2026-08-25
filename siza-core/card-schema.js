(function(global){
'use strict';

const CARD_SCHEMA_VERSION='1.2.0';
const CARD_TYPES=['Instant','Creature','Artifact','Land'];
const COLORS=['U','R','G','W','B'];
const TYPE_ALIASES={instant:'Instant',instantaneo:'Instant','instantáneo':'Instant',creature:'Creature',invocacion:'Creature','invocación':'Creature',artifact:'Artifact',artefacto:'Artifact',land:'Land',reserva:'Land',tierra:'Land'};
const COLOR_ALIASES={u:'U',azul:'U',blue:'U',r:'R',rojo:'R',red:'R',g:'G',verde:'G',green:'G',w:'W',blanco:'W',white:'W',b:'B',negro:'B',black:'B'};

function clone(value){return JSON.parse(JSON.stringify(value));}
function finiteNumber(value,fallback=null){const n=Number(value);return Number.isFinite(n)?n:fallback;}
function int(value,fallback=0){const n=finiteNumber(value,fallback);return Math.trunc(n);}
function text(value,fallback=''){return String(value??fallback);}
function normalizeType(value){if(CARD_TYPES.includes(value))return value;return TYPE_ALIASES[text(value).trim().toLowerCase()]||'Creature';}
function normalizeColor(value){const raw=text(value).trim();if(COLORS.includes(raw))return raw;return COLOR_ALIASES[raw.toLowerCase()]||null;}
function normalizeEffects(input=[]){if(global.SizaCardEffects?.normalizeEffects)return global.SizaCardEffects.normalizeEffects(input);return Array.isArray(input)?clone(input):[];}
function equipmentCost(input={}){return Math.max(0,int(input?.equipCost,0));}
function isEquipmentCard(input={}){
 const type=normalizeType(input.cardType??input.type),effects=normalizeEffects(input.effects);
 const hasEquipped=global.SizaCardEffects?.forEvent?global.SizaCardEffects.forEvent({...input,effects},'equipped').length>0:effects.some(effect=>effect?.event==='equipped');
 return type==='Artifact'&&(equipmentCost(input)>0||hasEquipped);
}

function normalizePips(input={}){
 const out={};
 if(Array.isArray(input)){
  for(const value of input){const k=normalizeColor(value);if(k)out[k]=(out[k]||0)+1;}
  return out;
 }
 for(const [raw,value] of Object.entries(input||{})){
  const k=normalizeColor(raw);if(!k)continue;const n=Math.max(0,int(value,0));if(n)out[k]=(out[k]||0)+n;
 }
 return out;
}

function pipsToCrystalArray(input={}){
 const pips=normalizePips(input),names={U:'azul',R:'rojo',G:'verde',W:'blanco',B:'negro'},out=[];
 for(const k of COLORS)for(let i=0;i<(pips[k]||0);i++)out.push(names[k]);
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
 const type=normalizeType(input.cardType??input.type),power=input.force??input.power,toughness=input.resistance??input.toughness,pips=normalizePips(input.pips??input.crystals);
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
  equipCost:equipmentCost(input),
  pips,
  crystals:pipsToCrystalArray(pips),
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
  art:text(input.art,input.affinity||'multi'),
  role:text(input.role,''),
  adventureUnlock:!!input.adventureUnlock,
  effects:normalizeEffects(input.effects)
 };
 return card;
}

function validateCard(input={}){
 const card=normalizeCard(input),errors=[],warnings=[];
 if(!card.id.trim())errors.push('La carta necesita un ID.');
 if(!card.name.trim())errors.push('La carta necesita un nombre.');
 if(!CARD_TYPES.includes(card.cardType))errors.push('Tipo de carta inválido.');
 if(card.cardType!=='Land'&&card.difficulty<=0)warnings.push('La dificultad es 0.');
 if(card.cardType==='Creature'&&(card.power==null||card.toughness==null))errors.push('Una Creature necesita Fuerza y Resistencia.');
 if(card.cardType!=='Creature'&&(card.power!=null||card.toughness!=null))warnings.push('Las estadísticas P/T sólo se muestran en Creature.');
 if(card.equipCost>0&&card.cardType!=='Artifact')errors.push('equipCost sólo es válido en Artifact.');
 if(card.equipCost>1)errors.push('El runtime actual sólo admite Equipar {1}.');
 if(!card.rules.trim()&&card.cardType!=='Land')warnings.push('La carta no tiene texto de reglas.');
 if(card.artUrl&&/cards-v\d+\//i.test(card.artUrl))warnings.push('artUrl parece apuntar a una carta completa legada, no a arte puro.');
 if(global.SizaCardEffects?.validateEffects){const e=global.SizaCardEffects.validateEffects(card.effects);errors.push(...e.errors);warnings.push(...e.warnings);card.effects=e.effects;}
 return {valid:errors.length===0,errors,warnings,card};
}

function cardFromMobileShape(input={}){return normalizeCard(input);}
function cardToMobileShape(input={}){
 const c=normalizeCard(input),out={id:c.id,name:c.name,type:c.cardType,cost:c.cost,difficulty:c.difficulty,pips:clone(c.pips),text:c.rules,flavor:c.flavor,art:c.art,glyph:c.glyph,artUrl:c.artUrl,artTransform:clone(c.artTransform),effects:clone(c.effects)};
 if(c.subtype)out.subtype=c.subtype;if(c.cardType==='Creature'){out.power=c.power;out.toughness=c.toughness;}if(c.equipCost>0)out.equipCost=c.equipCost;if(c.role)out.role=c.role;if(c.adventureUnlock)out.adventureUnlock=true;return out;
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
 normalizePips,
 pipsToCrystalArray,
 normalizeEffects,
 equipmentCost,
 isEquipmentCard
});
})(window);
