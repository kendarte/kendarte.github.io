(function(){
"use strict";
var BUILD="0.1.0-dodge-reaction-ui";
var STYLE_ID="pokerol-battle-reaction-style-v01";
var latestState=null;
var observer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function ensureStyle(){
  if(byId(STYLE_ID))return;
  var style=document.createElement("style");style.id=STYLE_ID;
  style.textContent='.pkbReactionTag{display:inline-block;padding:2px 4px;border:1px solid currentColor;background:var(--pk-dark,#33412d);color:var(--pk-paper,#eef3d5);font:700 7px/1 var(--pk-ui-font,monospace);letter-spacing:.04em;text-transform:uppercase}.pkbReactionTag:before{content:"↯ ";}';
  document.head.appendChild(style);
}
function reaction(){return latestState&&latestState.player&&latestState.player.battle_reaction||{}}
function armed(){var r=reaction();return !!r.armed&&text(r.policy).toUpperCase()==="DODGE"}
function ready(){return !!latestState&&text(latestState.status)==="ACTIVE"&&text(latestState.phase)==="COMMAND"&&!latestState.forced_switch}
function decorate(){
  ensureStyle();
  var root=byId("pkb-player-info");if(!root)return;
  var old=root.querySelector(".pkbReactionTag");if(old)old.remove();
  if(!armed())return;
  var types=root.querySelector(".pkbTypes")||root;
  var tag=document.createElement("span");tag.className="pkbReactionTag";tag.textContent="ESQUIVAR ARMADO";types.appendChild(tag);
}
function toggle(){
  if(!ready()||!window.Evennia||!Evennia.isConnected())return;
  Evennia.msg("text",["pokerol-reaction "+(armed()?"NONE":"DODGE")],{});
}
function enhance(){
  if(!ready())return;
  var fight=byId("pkb-fight");if(!fight)return;
  var grid=fight.parentNode;if(!grid)return;
  var btn=byId("pkb-reaction-dodge");
  if(!btn){
    btn=document.createElement("button");btn.className="pkbAction";btn.id="pkb-reaction-dodge";btn.onclick=toggle;
    grid.insertBefore(btn,byId("pkb-party")||null);
  }
  btn.textContent=armed()?"ESQUIVAR ✓":"ESQUIVAR";
  btn.title=armed()?"Reacción preparada; se consumirá con el próximo ataque entrante.":"Armar una reacción de esquiva para el próximo ataque entrante.";
}
function watch(){
  var body=byId("pkb-menu-body");if(!body||observer)return;
  observer=new MutationObserver(function(){window.setTimeout(function(){decorate();enhance()},0)});
  observer.observe(body,{childList:true,subtree:true});
}
function onState(args){latestState=args&&args[0]||null;window.setTimeout(function(){decorate();watch();enhance()},0)}
function init(){ensureStyle();watch();if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function")Evennia.emitter.on("pokerol_pokemon_battle_state",onState)}
window.PokerolBattleReactionUiV01=Object.freeze({BUILD:BUILD,toggle:toggle});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
