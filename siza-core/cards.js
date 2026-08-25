(function(global){
'use strict';

const VERSION='1.2.0';
const legacyFullCardImages=Object.freeze({
 mist:'cards-v0514/niebla_de_sal.webp?v=0514',
 spark:'cards-v0514/chispa_del_estuario.webp?v=0612',
 servitor:'cards-v0514/servidor_ahogado.webp?v=0514',
 ignimite:'cards-v0514/ignimite.webp?v=0612',
 counter:'cards-v0514/negacion_pictomantica.webp?v=0514',
 prism:'cards-v0514/prisma_de_enfoque.webp?v=0514',
 watcher:'cards-v0514/vigia_de_la_marea.webp?v=0514',
 smuggler:'cards-v0514/contrabandista_carmesi.webp?v=0612',
 tideblade:'cards-v0514/espada_de_bajamar.webp?v=0612',
 leviathan:'cards-v0514/leviatan_de_la_campana.webp?v=0514',
 dock:'cards-v0514/muelle_sumergido.webp?v=0514',
 cinder:'cards-v0514/erial_de_ceniza.webp?v=0514',
 queen:'cards-v0514/memoria_de_la_reina_ahogada.webp?v=0515'
});

const cards=Object.freeze([
 Object.freeze({id:'mist',legacyFullCardImage:legacyFullCardImages.mist,name:'Niebla de Sal',type:'Instant',cost:1,difficulty:5,pips:{U:1},text:'Roba una carta.',flavor:'La marea guarda secretos incluso de quienes viven de ella.',role:'draw',art:'blue',glyph:'≈',effects:Object.freeze([Object.freeze({event:'resolve',type:'draw',target:'self',amount:1})])}),
 Object.freeze({id:'spark',legacyFullCardImage:legacyFullCardImages.spark,name:'Chispa del Estuario',type:'Instant',cost:1,difficulty:5,pips:{R:1},text:'Inflige 2 de daño al Personaje rival.',flavor:'Una chispa basta cuando el aire sabe a sal.',role:'removal',art:'red',glyph:'✦',effects:Object.freeze([Object.freeze({event:'resolve',type:'damage-character',target:'opponent',amount:2})])}),
 Object.freeze({id:'servitor',legacyFullCardImage:legacyFullCardImages.servitor,name:'Servidor Ahogado',type:'Creature',subtype:'Ahogado',cost:2,difficulty:6,pips:{U:1},power:2,toughness:2,text:'Cuando entra, observa la carta superior de tu Library.',flavor:'No respira. Recuerda.',role:'threat',art:'blue',glyph:'☠',effects:Object.freeze([Object.freeze({event:'enter',type:'observe-top',target:'self'})])}),
 Object.freeze({id:'ignimite',legacyFullCardImage:legacyFullCardImages.ignimite,name:'Ignimite',type:'Creature',subtype:'Elemental',cost:2,difficulty:6,pips:{R:1},power:1,toughness:1,text:'Cuando hace daño de combate, obtiene +1/+1.',flavor:'Toda llama aprende de aquello que consume.',role:'threat',art:'red',glyph:'♨',effects:Object.freeze([Object.freeze({event:'combat-damage',type:'add-power-counter',amount:1})])}),
 Object.freeze({id:'counter',legacyFullCardImage:legacyFullCardImages.counter,name:'Negación Pictomántica',type:'Instant',cost:2,difficulty:6,pips:{U:2},text:'Contrarresta el spell objetivo.',flavor:'No toda memoria merece cruzar.',role:'counter',art:'blue',glyph:'⊘',effects:Object.freeze([Object.freeze({event:'resolve',type:'counter-stack-target'})])}),
 Object.freeze({id:'prism',legacyFullCardImage:legacyFullCardImages.prism,name:'Prisma de Enfoque',type:'Artifact',cost:2,difficulty:6,pips:{},text:'Agota: +1 a una Manafestation Azul.',flavor:'El cristal no crea poder. Lo convence de tomar forma.',role:'ramp',art:'multi',glyph:'◇'}),
 Object.freeze({id:'watcher',legacyFullCardImage:legacyFullCardImages.watcher,name:'Vigía de la Marea',type:'Creature',subtype:'Soldado',cost:3,difficulty:7,pips:{U:2},power:2,toughness:4,text:'Defensor de las rutas sumergidas.',flavor:'La costa nunca duerme; sólo cambia de guardia.',role:'threat',art:'blue',glyph:'♜'}),
 Object.freeze({id:'smuggler',legacyFullCardImage:legacyFullCardImages.smuggler,name:'Contrabandista Carmesí',type:'Creature',subtype:'Humano',cost:3,difficulty:7,pips:{R:2},power:3,toughness:2,text:'Siempre que ataque, inflige 1 de daño adicional al Personaje defensor.',flavor:'No existe puerto sin una segunda aduana.',role:'threat',art:'red',glyph:'⚔',effects:Object.freeze([Object.freeze({event:'attack-declared',type:'damage-character',target:'opponent',amount:1})])}),
 Object.freeze({id:'tideblade',legacyFullCardImage:legacyFullCardImages.tideblade,name:'Espada de Bajamar',type:'Artifact',cost:3,difficulty:6,pips:{U:1},text:'La criatura equipada obtiene +2/+0. Equipar {1}.',flavor:'Forjada donde el agua revela lo que la marea quiso ocultar.',role:'utility',art:'blue',glyph:'†'}),
 Object.freeze({id:'leviathan',legacyFullCardImage:legacyFullCardImages.leviathan,name:'Leviatán de la Campana',type:'Creature',subtype:'Leviatán',cost:7,difficulty:8,pips:{U:3},power:7,toughness:7,text:'Al entrar, devuelve otro permanente a la mano de su dueño.',flavor:'La campana no lo llama. Le recuerda que alguna vez estuvo despierto.',role:'finisher',art:'blue',glyph:'Ω',effects:Object.freeze([Object.freeze({event:'enter',type:'bounce-other-permanent'})])}),
 Object.freeze({id:'dock',legacyFullCardImage:legacyFullCardImages.dock,name:'Muelle Sumergido',type:'Land',cost:0,pips:{},text:'Las Lands no se juegan al Battlefield. Permanecen en la mano y sólo se consumen como Mana Burn para aumentar una tirada de Manafestation fallida.',flavor:'Cada tabla guarda el peso de quienes nunca regresaron.',role:'land',art:'land',glyph:'⌁'}),
 Object.freeze({id:'cinder',legacyFullCardImage:legacyFullCardImages.cinder,name:'Erial de Ceniza',type:'Land',cost:0,pips:{},text:'Las Lands no se juegan al Battlefield. Permanecen en la mano y sólo se consumen como Mana Burn para aumentar una tirada de Manafestation fallida.',flavor:'El fuego también deja territorio.',role:'land',art:'land',glyph:'△'}),
 Object.freeze({id:'queen',legacyFullCardImage:legacyFullCardImages.queen,name:'Memoria de la Reina Ahogada',type:'Creature',subtype:'Avatar',cost:5,difficulty:8,pips:{U:3},power:5,toughness:5,text:'Al entrar, roba dos cartas y luego descarta una.',flavor:'La corona sobrevivió porque nadie recordó enterrarla.',role:'finisher',art:'multi',glyph:'♛',adventureUnlock:true,effects:Object.freeze([Object.freeze({event:'enter',type:'draw',target:'self',amount:2}),Object.freeze({event:'enter',type:'discard',target:'self',amount:1,choice:'owner'})])})
]);

function get(id){return cards.find(card=>card.id===id)||null;}
function all(){return cards.slice();}

global.SizaCardCatalog=Object.freeze({VERSION,cards,legacyFullCardImages,get,all});
})(window);
