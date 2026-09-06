(function(){
"use strict";
var BUILD="0.2.0-defensive-reaction-menu";
var STYLE_ID="pokerol-battle-reaction-style-v01";
var latestState=null;
var latestOptions=null;
var observer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function ensureStyle(){
  if(byId(STYLE_ID))return;
  var style=document.createElement("style");style.id=STYLE_ID;
  style.textContent=''
    +'.pkbReactionTag{display:inline-block;padding:2px 4px;border:1px solid currentColor;background:var(--pk-dark,#33412d);color:var(--pk-paper,#eef3d5);font:700 7px/1 var(--pk-ui-font,monospace);letter-spacing:.04em;text-transform:uppercase}.pkbReactionTag:before{content:"↯ ";}'
    +'.pkbReactionList{display:grid;gap:3px}.pkbReactionOption{display:block;width:100%;position:relative;border:0!important;border-radius:0!important;background:transparent!important;color:var(--pk-ink,#172016)!important;box-shadow:none!important;padding:8px 10px 8px 24px;cursor:pointer;text-align:left;font:700 10px/1.2 var(--pk-ui-font,monospace)!important;text-transform:uppercase}.pkbReactionOption:hover{background:var(--pk-select,#263521)!important;color:var(--pk-select-text,#f2f6dc)!important}.pkbReactionOption:hover:before{content:"▶";position:absolute;left:7px;top:50%;transform:translateY(-50%)}.pkbReactionOption small{display:block;margin-top:3px;font:8px/1.25 var(--pk-ui-font,monospace);color:var(--pk-dark,#33412d)}.pkbReactionOption:hover small{color:inherit}';
  document.head.appendChild(style);
}
function reaction(){return latestState&&latestState.player&&latestState.player.battle_reaction||{}}
function armed(){var r=reaction();return !!r.armed&&text(r.policy).toUpperCase()!=="NONE"}
function reactionLabel(r){
  r=r||{};var p=text(r.policy).toUpperCase();
  if(p==="DODGE")return"ESQUIVAR";
  if(p==="REDIRECT")return"DESVIAR";
  if(p==="BLOCK")return"BLOQUEAR";
  if(p==="INTERCEPT")return"INTERCEPTAR";
  return p||"REACCIÓN";
}
function ready(){return !!latestState&&text(latestState.status)==="ACTIVE"&&text(latestState.phase)==="COMMAND"&&!latestState.forced_switch}
function decorate(){
  ensureStyle();
  var root=byId("pkb-player-info");if(!root)return;
  var old=root.querySelector(".pkbReactionTag");if(old)old.remove();
  if(!armed())return;
  var r=reaction(),types=root.querySelector(".pkbTypes")||root;
  var tag=document.createElement("span");tag.className="pkbReactionTag";
  tag.textContent=reactionLabel(r)+" ARMADO"+(text(r.method_move_name)?" · "+text(r.method_move_name):"");types.appendChild(tag);
}
function requestOptions(){
  if(!ready()||!window.Evennia||!Evennia.isConnected())return;
  Evennia.msg("text",["pokerol-reaction-options"],{});
}
function sendReaction(row){
  if(!ready()||!row||!window.Evennia||!Evennia.isConnected())return;
  var cmd="pokerol-reaction "+text(row.policy).toUpperCase();
  if(text(row.method_move_id))cmd+=" "+text(row.method_move_id);
  Evennia.msg("text",[cmd],{});
}
function clearReaction(){
  if(!ready()||!window.Evennia||!Evennia.isConnected())return;
  Evennia.msg("text",["pokerol-reaction NONE"],{});
}
function note(row){
  var out=[];
  if(row.natural)out.push("NATURAL · 0 PP");
  if(text(row.method_move_name))out.push(text(row.method_move_name)+" · PP "+String(row.pp_current==null?"?":row.pp_current)+"/"+String(row.pp_max==null?"?":row.pp_max));
  if(Array.isArray(row.allowed_deliveries)&&row.allowed_deliveries.length)out.push("VS "+row.allowed_deliveries.join("/"));
  if(row.physical_only)out.push("SÓLO FÍSICO");
  return out.join(" · ");
}
function showOptions(packet){
  latestOptions=packet||{};
  var body=byId("pkb-menu-body"),title=byId("pkb-menu-title");if(!body||!ready())return;
  if(title)title.textContent="REACCIÓN";
  var rows=Array.isArray(latestOptions.options)?latestOptions.options:[],current=latestOptions.current||reaction();
  body.innerHTML='<div class="pkbStubText">'+(current&&current.armed?"ARMADA: "+esc(reactionLabel(current)+(text(current.method_move_name)?" · "+current.method_move_name:"")):"ELIGE UNA DEFENSA PARA EL PRÓXIMO ATAQUE ENTRANTE.")+'</div>'
    +'<div class="pkbReactionList">'+(rows.length?rows.map(function(row,index){return '<button class="pkbReactionOption" data-reaction-index="'+index+'"><b>'+esc(row.label||reactionLabel(row))+(text(row.method_move_name)?' · '+esc(row.method_move_name):'')+'</b><small>'+esc(note(row))+'</small></button>'}).join(''):'<div class="pkbStubText">NO HAY REACCIONES DISPONIBLES.</div>')+'</div>'
    +(current&&current.armed?'<button class="pkbBack" id="pkb-reaction-clear">QUITAR REACCIÓN</button>':'')
    +'<button class="pkbBack" id="pkb-reaction-back">ATRÁS</button>';
  Array.prototype.forEach.call(body.querySelectorAll("[data-reaction-index]"),function(btn){btn.onclick=function(){var row=rows[Number(btn.getAttribute("data-reaction-index"))];sendReaction(row)}});
  var clear=byId("pkb-reaction-clear");if(clear)clear.onclick=clearReaction;
  var back=byId("pkb-reaction-back");if(back)back.onclick=function(){if(window.PokerolPokemonBattleV01&&typeof window.PokerolPokemonBattleV01.setMenuMode==="function")window.PokerolPokemonBattleV01.setMenuMode("ACTION");window.setTimeout(enhance,0)};
}
function enhance(){
  if(!ready())return;
  var fight=byId("pkb-fight");if(!fight)return;
  var grid=fight.parentNode;if(!grid)return;
  var btn=byId("pkb-reaction-menu");
  if(!btn){btn=document.createElement("button");btn.className="pkbAction";btn.id="pkb-reaction-menu";btn.onclick=requestOptions;grid.insertBefore(btn,byId("pkb-party")||null)}
  btn.textContent=armed()?"REACCIÓN ✓":"REACCIÓN";
  btn.title=armed()?"Hay una reacción preparada para el próximo ataque compatible.":"Preparar esquiva, desvío, bloqueo o intercepción según las capacidades reales del Pokémon.";
}
function watch(){
  var body=byId("pkb-menu-body");if(!body||observer)return;
  observer=new MutationObserver(function(){window.setTimeout(function(){decorate();enhance()},0)});observer.observe(body,{childList:true,subtree:true});
}
function onState(args){latestState=args&&args[0]||null;latestOptions=null;window.setTimeout(function(){decorate();watch();enhance()},0)}
function onOptions(args){showOptions(args&&args[0]||{})}
function init(){ensureStyle();watch();if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function"){Evennia.emitter.on("pokerol_pokemon_battle_state",onState);Evennia.emitter.on("pokerol_pokemon_reaction_options",onOptions)}}
window.PokerolBattleReactionUiV01=Object.freeze({BUILD:BUILD,requestOptions:requestOptions});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
