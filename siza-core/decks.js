(function(global){
'use strict';
const VERSION='1.0.0',FORMAT='Siza Core 60',freezeCounts=counts=>Object.freeze({...counts});
const deck=(id,name,counts,role)=>Object.freeze({id,name,format:FORMAT,version:VERSION,role,counts:freezeCounts(counts)});
const shared=Object.freeze({dhk_familiar_de_practica:4,dhk_lectura_de_campo:4,dhk_interrupcion_de_protocolo:4,dhk_prisma_de_servicio:4,dhk_spellweapon_de_servicio:4});
const decks=Object.freeze([
 deck('deck_tide_crimson','Marea Carmesí',{mist:4,spark:4,servitor:4,ignimite:4,counter:4,prism:4,watcher:4,tideblade:4,dhk_mastin_de_impacto:4,dock:12,cinder:12},'Azul-rojo equilibrado'),
 deck('starter_darkhaven_vigilancia_v01','Darkhaven — Vigilancia',{...shared,dhk_ojo_de_baliza:4,dhk_eco_de_rastreo:4,dhk_ancla_de_retorno:4,dhk_corte_de_senal:4,dhk_archivo_de_guardia:12,dhk_plataforma_de_relevo:12},'Control e información'),
 deck('starter_darkhaven_ruptura_v01','Darkhaven — Ruptura',{...shared,dhk_ignimite_de_ejercicio:4,dhk_mastin_de_impacto:4,dhk_eco_de_asalto:4,dhk_descarga_de_ruptura:4,dhk_galeria_de_entrenamiento:12,dhk_hangar_de_salida:12},'Presión y combate'),
 deck('starter_darkhaven_contencion_v01','Darkhaven — Contención',{...shared,dhk_sabueso_de_umbral:4,dhk_custodio_lumex:4,dhk_bastion_pictomantico:4,dhk_contraimpulso:4,dhk_patio_de_contencion:12,dhk_camara_de_frames:12},'Defensa y permanencia')
]);
function get(id){return decks.find(entry=>entry.id===id)||null}function all(){return decks.slice()}
function copy(id='deck_tide_crimson'){const source=get(id)||decks[0];return{id:source.id,name:source.name,format:source.format,version:source.version,role:source.role,counts:{...source.counts}}}
function validate(input,resolveCard){const errors=[],counts=input?.counts||{},total=Object.values(counts).reduce((sum,value)=>sum+(Number(value)||0),0);if(total!==60)errors.push('DECK_MUST_HAVE_60_CARDS');for(const[id,raw]of Object.entries(counts)){const quantity=Number(raw)||0,card=resolveCard(id);if(!card){errors.push(`UNKNOWN_CARD:${id}`);continue}if(quantity<0||!Number.isInteger(quantity))errors.push(`INVALID_QUANTITY:${id}`);if(card.type!=='Land'&&quantity>4)errors.push(`COPY_LIMIT:${id}`);if(card.type!=='Land'&&!(Number(card.difficulty)>0))errors.push(`INVALID_DIFFICULTY:${id}`)}return{valid:errors.length===0,total,errors}}
global.SizaDeckCatalog=Object.freeze({VERSION,FORMAT,decks,get,all,copy,validate});
})(window);
