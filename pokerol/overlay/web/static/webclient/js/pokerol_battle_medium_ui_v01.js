(function(){
"use strict";
var BUILD="0.1.0-battle-medium-hud";
var STYLE_ID="pokerol-battle-medium-style-v01";
function text(v){return String(v==null?"":v).trim()}
function ensureStyle(){
  if(document.getElementById(STYLE_ID))return;
  var style=document.createElement("style");
  style.id=STYLE_ID;
  style.textContent='.pkbMediumTag{display:inline-block;padding:2px 4px;border:1px solid currentColor;background:var(--pk-light,#d7e0bd);color:var(--pk-ink,#172016);font:700 7px/1 var(--pk-ui-font,monospace);letter-spacing:.04em;text-transform:uppercase}.pkbMediumTag:before{content:"~ ";}';
  document.head.appendChild(style);
}
function label(p){
  var id=text(p&&p.contact_medium_id);if(!id)return"";
  var kind=text(p&&p.contact_medium_kind)||"MEDIO";
  return kind+" · "+id;
}
function applyOne(nodeId,p){
  var root=document.getElementById(nodeId);if(!root)return;
  var old=root.querySelector(".pkbMediumTag");if(old)old.remove();
  var value=label(p);if(!value)return;
  var types=root.querySelector(".pkbTypes")||root;
  var tag=document.createElement("span");tag.className="pkbMediumTag";tag.textContent=value;types.appendChild(tag);
}
function render(packet){ensureStyle();applyOne("pkb-player-info",packet&&packet.player);applyOne("pkb-enemy-info",packet&&packet.enemy)}
function onState(args){window.setTimeout(function(){render(args&&args[0])},0)}
function init(){ensureStyle();if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function")Evennia.emitter.on("pokerol_pokemon_battle_state",onState)}
window.PokerolBattleMediumUiV01=Object.freeze({BUILD:BUILD,render:render});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
