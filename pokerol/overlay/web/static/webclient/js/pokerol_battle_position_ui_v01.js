(function(){
"use strict";
var BUILD="0.1.0-anime-position-ui";
var STYLE_ID="pokerol-battle-position-style-v01";
var latestState=null;
var latestOptions=null;
var observer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function encode(value){
  var json=JSON.stringify(value),raw=unescape(encodeURIComponent(json)),bin="";
  for(var i=0;i<raw.length;i++)bin+=String.fromCharCode(raw.charCodeAt(i));
  return btoa(bin).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
}
function ensureStyle(){
  if(byId(STYLE_ID))return;
  var style=document.createElement("style");
  style.id=STYLE_ID;
  style.textContent=''
    +'.pkbPositionTag{display:inline-block;padding:2px 4px;border:1px solid currentColor;background:var(--pk-paper,#eef3d5);color:var(--pk-ink,#172016);font:700 7px/1 var(--pk-ui-font,monospace);letter-spacing:.04em;text-transform:uppercase}'
    +'.pkbPositionTag:before{content:"◆ ";}'
    +'.pkbPositionList{display:grid;gap:3px}'
    +'.pkbPositionOption{display:block;width:100%;position:relative;border:0!important;border-radius:0!important;background:transparent!important;color:var(--pk-ink,#172016)!important;box-shadow:none!important;padding:8px 10px 8px 24px;cursor:pointer;text-align:left;font:700 10px/1.2 var(--pk-ui-font,monospace)!important;text-transform:uppercase}'
    +'.pkbPositionOption:hover{background:var(--pk-select,#263521)!important;color:var(--pk-select-text,#f2f6dc)!important}'
    +'.pkbPositionOption:hover:before{content:"▶";position:absolute;left:7px;top:50%;transform:translateY(-50%)}'
    +'.pkbPositionOption small{display:block;margin-top:3px;font:8px/1.25 var(--pk-ui-font,monospace);color:var(--pk-dark,#33412d)}'
    +'.pkbPositionOption:hover small{color:inherit}';
  document.head.appendChild(style);
}
function positionLabel(p){
  var pos=p&&p.battle_position||{};
  var stance=text(pos.stance).toUpperCase();
  if(!stance&&text(p&&p.contact_medium_id))stance="WATER";
  if(stance==="WATER")return "AGUA"+(text(pos.medium_id||p.contact_medium_id)?" · "+text(pos.medium_id||p.contact_medium_id):"");
  if(stance==="AIR")return "AIRE"+(text(pos.altitude)?" · "+text(pos.altitude):"");
  if(stance==="ELEVATED"){
    var anchor=pos.anchor||{};
    return "ALTURA"+(text(anchor.name)?" · "+text(anchor.name):"");
  }
  if(pos.cover&&text(pos.cover.name))return "COBERTURA · "+text(pos.cover.name);
  return stance&&stance!=="GROUND"?stance:"SUELO";
}
function decorateOne(nodeId,p){
  var root=byId(nodeId);if(!root)return;
  var old=root.querySelector(".pkbPositionTag");if(old)old.remove();
  if(!p)return;
  var types=root.querySelector(".pkbTypes")||root;
  var tag=document.createElement("span");tag.className="pkbPositionTag";tag.textContent=positionLabel(p);types.appendChild(tag);
}
function decoratePositions(packet){
  ensureStyle();
  decorateOne("pkb-player-info",packet&&packet.player);
  decorateOne("pkb-enemy-info",packet&&packet.enemy);
}
function battleReady(){return !!latestState&&text(latestState.status)==="ACTIVE"&&text(latestState.phase)==="COMMAND"&&!latestState.forced_switch}
function requestOptions(){
  if(!battleReady()||!window.Evennia||!Evennia.isConnected())return;
  Evennia.msg("text",["pokerol-position-options"],{});
}
function actionName(row){
  var action=text(row.action).toUpperCase();
  if(action==="ENTER_WATER")return "ENTRAR AL AGUA";
  if(action==="TAKE_COVER")return "TOMAR COBERTURA";
  if(action==="CLIMB")return "GANAR ALTURA";
  if(action==="TAKEOFF")return "TOMAR EL AIRE";
  if(action==="RETURN_GROUND")return "VOLVER AL SUELO";
  return action||"MOVER";
}
function optionNote(row){
  var parts=[];
  if(row.method_move_name)parts.push("VÍA "+row.method_move_name+" · GASTA PP");
  else if(row.natural)parts.push("MOVIMIENTO NATURAL");
  if(row.water_body_id)parts.push(row.water_body_id);
  if(row.cover_rating!=null&&Number(row.cover_rating)>0)parts.push("COBERTURA "+Math.round(Number(row.cover_rating)*100)+"%");
  return parts.join(" · ");
}
function sendPosition(row){
  if(!battleReady()||!row||!window.Evennia||!Evennia.isConnected())return;
  var action={
    type:"FREE_ORDER",
    position_action:row.action,
    target_id:row.target_id
  };
  if(row.method_move_id)action.method_move_id=row.method_move_id;
  Evennia.msg("text",["pokerol-battle-action "+encode(action)],{});
  var body=byId("pkb-menu-body");if(body)Array.prototype.forEach.call(body.querySelectorAll("button"),function(btn){btn.disabled=true});
}
function showOptions(packet){
  latestOptions=packet||{};
  var body=byId("pkb-menu-body"),title=byId("pkb-menu-title");
  if(!body||!battleReady())return;
  if(title)title.textContent="MOVER / POSICIÓN";
  var rows=Array.isArray(latestOptions.targets)?latestOptions.targets:[];
  body.innerHTML='<div class="pkbStubText">POSICIÓN ACTUAL: '+esc(latestOptions.position_label||positionLabel(latestState&&latestState.player))+'</div>'
    +'<div class="pkbPositionList">'+(rows.length?rows.map(function(row,index){
      return '<button class="pkbPositionOption" data-position-index="'+index+'"><b>'+esc(actionName(row)+' · '+(row.name||row.target_id||"OBJETIVO"))+'</b><small>'+esc(optionNote(row))+'</small></button>';
    }).join(''):'<div class="pkbStubText">NO HAY CAMBIOS DE POSICIÓN DISPONIBLES EN ESTE ROOM.</div>')+'</div>'
    +'<button class="pkbBack" id="pkb-position-back">ATRÁS</button>';
  Array.prototype.forEach.call(body.querySelectorAll("[data-position-index]"),function(btn){btn.onclick=function(){
    var row=rows[Number(btn.getAttribute("data-position-index"))];sendPosition(row);
  }});
  var back=byId("pkb-position-back");if(back)back.onclick=function(){
    if(window.PokerolPokemonBattleV01&&typeof window.PokerolPokemonBattleV01.setMenuMode==="function")window.PokerolPokemonBattleV01.setMenuMode("ACTION");
    window.setTimeout(enhanceActionMenu,0);
  };
}
function enhanceActionMenu(){
  if(!battleReady())return;
  var fight=byId("pkb-fight");if(!fight)return;
  var grid=fight.parentNode;if(!grid||grid.querySelector("#pkb-move-position"))return;
  var btn=document.createElement("button");btn.className="pkbAction";btn.id="pkb-move-position";btn.textContent="MOVER";btn.onclick=requestOptions;
  grid.insertBefore(btn,byId("pkb-party")||null);
}
function watchMenu(){
  var body=byId("pkb-menu-body");if(!body||observer)return;
  observer=new MutationObserver(function(){window.setTimeout(enhanceActionMenu,0)});
  observer.observe(body,{childList:true,subtree:true});
}
function onBattleState(args){
  latestState=args&&args[0]||null;
  latestOptions=null;
  window.setTimeout(function(){decoratePositions(latestState);watchMenu();enhanceActionMenu()},0);
}
function onPositionOptions(args){showOptions(args&&args[0]||{})}
function init(){
  ensureStyle();watchMenu();
  if(!window.Evennia)return;Evennia.init();
  if(Evennia.emitter&&typeof Evennia.emitter.on==="function"){
    Evennia.emitter.on("pokerol_pokemon_battle_state",onBattleState);
    Evennia.emitter.on("pokerol_pokemon_position_options",onPositionOptions);
  }
}
window.PokerolBattlePositionUiV01=Object.freeze({BUILD:BUILD,requestOptions:requestOptions,decoratePositions:decoratePositions});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
