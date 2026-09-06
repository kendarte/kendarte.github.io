(function(){
"use strict";
var BUILD="0.2.0-red-plus-battle-menu";
var state=null;
var menuMode="ACTION";
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function clone(v){try{return JSON.parse(JSON.stringify(v))}catch(e){return v}}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function pct(cur,max){max=Math.max(1,Number(max)||1);return Math.max(0,Math.min(100,(Number(cur)||0)/max*100))}
function battleReady(){return !!state&&text(state.status)==="ACTIVE"&&text(state.phase)==="COMMAND"}
function ensure(){
  var root=byId("pokerol-pokemon-battle");
  if(root)return root;
  root=document.createElement("div");
  root.id="pokerol-pokemon-battle";
  root.className="pokerolPokemonBattle";
  root.innerHTML=''
  +'<div class="pkbScene">'
  +'<div class="pkbTopbar"><div class="pkbBadge" id="pkb-site">POKEROL</div><div class="pkbBadge pkbPhase" id="pkb-phase">COMMAND</div></div>'
  +'<div class="pkbArena">'
  +'<div class="pkbSide pkbEnemy"><div class="pkbInfo" id="pkb-enemy-info"></div><div class="pkbSpriteWrap" id="pkb-enemy-sprite"></div></div>'
  +'<div class="pkbSide pkbPlayer"><div class="pkbInfo" id="pkb-player-info"></div><div class="pkbSpriteWrap" id="pkb-player-sprite"></div></div>'
  +'</div>'
  +'<div class="pkbBottom">'
  +'<div class="pkbDialogue"><div class="pkbLog" id="pkb-log"></div></div>'
  +'<div class="pkbMenuWindow"><div class="pkbCommandTitle"><span id="pkb-menu-title">¿QUÉ HARÁ?</span><span id="pkb-turn">TURNO 1</span></div><div class="pkbMenuBody" id="pkb-menu-body"></div></div>'
  +'</div>'
  +'<div class="pkbOutcome"><div class="pkbOutcomeCard"><h2 id="pkb-outcome-title">BATALLA TERMINADA</h2><p id="pkb-outcome-text"></p><button class="pkbReturn" id="pkb-return">VOLVER A LA AVENTURA</button></div></div>'
  +'</div>';
  document.body.appendChild(root);
  byId("pkb-return").onclick=function(){closeBattle()};
  return root;
}
function infoHtml(p){
  var types=(p.types||[]).map(function(t){return '<span>'+esc(t)+'</span>'}).join('');
  var hp=pct(p.hp_current,p.hp_max);
  return '<div class="pkbNameRow"><span>'+esc(p.name||p.species_name||"Pokémon")+'</span><span>Lv '+esc(p.level)+'</span></div>'
    +'<div class="pkbTypes">'+types+'</div>'
    +'<div class="pkbHpRow"><span class="pkbHpLabel">HP</span><div class="pkbHpTrack"><div class="pkbHpFill" style="width:'+hp+'%"></div></div></div>'
    +'<div class="pkbHpText">'+esc(p.hp_current)+' / '+esc(p.hp_max)+'</div>';
}
function spriteHtml(p,side){
  var s=p&&p.sprite||{};
  var src=side==="PLAYER"?(s.back||s.front):(s.front||s.back);
  var scale=Number(s.scale)||1;
  if(src)return '<img class="pkbSprite" src="'+esc(src)+'" alt="'+esc(p.name||p.species_name||"Pokémon")+'" style="--pkb-scale:'+scale+'">';
  var name=text(p.name||p.species_name||"?");
  return '<div class="pkbFallback">'+esc(name.slice(0,2).toUpperCase())+'</div>';
}
function moveButton(m,disabled){
  return '<button class="pkbMove" data-move="'+esc(m.move_id)+'" '+(disabled?'disabled':'')+'><b>'+esc(m.name||m.move_id)+'</b><small>'+esc(m.pokemon_type||"")+' · POT '+esc(m.power||0)+' · ACC '+esc(m.accuracy||100)+'</small></button>';
}
function outcomeText(v){
  var map={PLAYER_WIN:"VICTORIA",PLAYER_LOSS:"DERROTA",DRAW:"EMPATE",CAPTURED:"¡CAPTURADO!",ESCAPED:"ESCAPASTE",ABANDONED:"BATALLA TERMINADA"};
  return map[text(v).toUpperCase()]||text(v)||"BATALLA TERMINADA";
}
function menuTitle(value){
  var map={ACTION:"¿QUÉ HARÁ?",MOVE:"ELIGE MOVIMIENTO",PARTY:"POKÉMON",BAG:"BOLSA"};
  return map[value]||"ORDEN";
}
function setMenuMode(next){menuMode=next;renderMenu()}
function renderMenu(){
  ensure();
  var body=byId("pkb-menu-body");
  if(!body)return;
  byId("pkb-menu-title").textContent=menuTitle(menuMode);
  var disabled=!battleReady();
  if(menuMode==="MOVE"){
    var moves=(state&&state.player&&state.player.moves)||[];
    body.innerHTML='<div class="pkbMoveGrid">'+(moves.map(function(m){return moveButton(m,disabled)}).join('')||'<div class="pkbStubText">SIN MOVIMIENTOS.</div>')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-move]"),function(btn){btn.onclick=function(){sendAction({type:"MOVE",move_id:btn.getAttribute("data-move")})}});
    var backMove=byId("pkb-back");if(backMove)backMove.onclick=function(){setMenuMode("ACTION")};
    return;
  }
  if(menuMode==="PARTY"){
    var active=state&&state.player?text(state.player.name||state.player.species_name):"POKÉMON ACTIVO";
    body.innerHTML='<div class="pkbSubMenu"><button class="pkbPartyStub" type="button">▶ '+esc(active)+'</button><div class="pkbStubText">El Party System persistente entra en el siguiente sprint. Esta vista ya reserva el flujo de cambio de Pokémon.</div><button class="pkbBack" id="pkb-back">ATRÁS</button></div>';
    byId("pkb-back").onclick=function(){setMenuMode("ACTION")};
    return;
  }
  if(menuMode==="BAG"){
    var wild=state&&text(state.battle_kind)==="WILD";
    body.innerHTML='<div class="pkbSubMenu"><button class="pkbBagItem" id="pkb-ball" '+(!wild||disabled?'disabled':'')+'>POKÉ BALL</button><div class="pkbStubText">Objetos adicionales llegarán con el Bag System. La Poké Ball ya usa la captura autoritativa actual.</div><button class="pkbBack" id="pkb-back">ATRÁS</button></div>';
    var ball=byId("pkb-ball");if(ball)ball.onclick=function(){sendAction({type:"CAPTURE",ball_multiplier:1.0})};
    byId("pkb-back").onclick=function(){setMenuMode("ACTION")};
    return;
  }
  body.innerHTML='<div class="pkbActionGrid">'
    +'<button class="pkbAction" id="pkb-fight" '+(disabled?'disabled':'')+'>FIGHT</button>'
    +'<button class="pkbAction" id="pkb-party" '+(disabled?'disabled':'')+'>POKÉMON</button>'
    +'<button class="pkbAction" id="pkb-bag" '+(disabled?'disabled':'')+'>BAG</button>'
    +'<button class="pkbAction" id="pkb-run" '+(disabled||text(state&&state.battle_kind)!=="WILD"?'disabled':'')+'>RUN</button>'
    +'</div>';
  byId("pkb-fight").onclick=function(){setMenuMode("MOVE")};
  byId("pkb-party").onclick=function(){setMenuMode("PARTY")};
  byId("pkb-bag").onclick=function(){setMenuMode("BAG")};
  byId("pkb-run").onclick=function(){sendAction({type:"RUN"})};
}
function render(packet){
  state=clone(packet||{});
  var root=ensure();
  root.setAttribute("data-open","true");
  root.setAttribute("data-complete",text(state.status)==="COMPLETE"?"true":"false");
  var site=state.site||{};
  var scene=root.querySelector(".pkbScene");
  if(scene){
    var bg=text(site.scene_image&&site.scene_image.src);
    scene.style.backgroundImage=bg?'linear-gradient(180deg,rgba(23,32,22,.03),rgba(23,32,22,.3)),url("'+bg.replace(/"/g,'%22')+'")':'';
  }
  byId("pkb-site").textContent=text(site.name)||"POKEROL";
  byId("pkb-phase").textContent=text(state.phase)||"COMMAND";
  byId("pkb-turn").textContent="TURNO "+(state.turn||1);
  byId("pkb-player-info").innerHTML=infoHtml(state.player||{});
  byId("pkb-enemy-info").innerHTML=infoHtml(state.enemy||{});
  byId("pkb-player-sprite").innerHTML=spriteHtml(state.player||{},"PLAYER");
  byId("pkb-enemy-sprite").innerHTML=spriteHtml(state.enemy||{},"ENEMY");
  var log=(state.log||[]).slice(-6);
  byId("pkb-log").innerHTML=log.map(function(row){return '<div class="pkbLogLine">'+esc(row.text||row.kind||"")+'</div>'}).join('')||'<div class="pkbLogLine">¿Qué hará '+esc(state.player&&state.player.name||"tu Pokémon")+'?</div>';
  if(text(state.status)==="COMPLETE"){
    byId("pkb-outcome-title").textContent=outcomeText(state.outcome);
    byId("pkb-outcome-text").textContent=(state.player&&state.player.name?state.player.name+" · ":"")+(state.enemy&&state.enemy.name?state.enemy.name:"");
  }
  renderMenu();
}
function encode(value){
  var json=JSON.stringify(value),raw=unescape(encodeURIComponent(json)),bin="";
  for(var i=0;i<raw.length;i++)bin+=String.fromCharCode(raw.charCodeAt(i));
  return btoa(bin).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
}
function sendAction(action){
  if(!battleReady())return;
  if(!window.Evennia||!Evennia.isConnected())return;
  disableCommands();
  Evennia.msg("text",["pokerol-battle-action "+encode(action)],{});
}
function disableCommands(){
  var root=ensure();
  Array.prototype.forEach.call(root.querySelectorAll(".pkbAction,.pkbMove,.pkbBagItem,.pkbBack"),function(btn){btn.disabled=true});
}
function closeBattle(){
  var root=ensure();
  root.removeAttribute("data-open");root.removeAttribute("data-complete");
  state=null;menuMode="ACTION";
  if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("EXPLORATION");
}
function onState(args){
  var packet=args&&args[0];
  if(!packet||typeof packet!=="object")return;
  if(text(packet.event)==="START"||text(packet.event)==="ROUND")menuMode="ACTION";
  if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("COMBAT");
  render(packet);
}
function onError(args){
  var packet=args&&args[0];if(!packet)return;
  var log=byId("pkb-log");
  if(log)log.innerHTML+='<div class="pkbLogLine">ACCIÓN RECHAZADA: '+esc(packet.status)+'</div>';
  renderMenu();
}
function onKey(event){
  if(!state||!byId("pokerol-pokemon-battle")||byId("pokerol-pokemon-battle").getAttribute("data-open")!=="true")return;
  if(event.key==="Escape"&&menuMode!=="ACTION"){event.preventDefault();setMenuMode("ACTION")}
}
function init(){
  ensure();document.addEventListener("keydown",onKey);
  if(!window.Evennia)return;
  Evennia.init();
  if(Evennia.emitter&&typeof Evennia.emitter.on==="function"){
    Evennia.emitter.on("pokerol_pokemon_battle_state",onState);
    Evennia.emitter.on("pokerol_pokemon_battle_error",onError);
  }
}
window.PokerolPokemonBattleV01=Object.freeze({BUILD:BUILD,render:render,close:closeBattle,getState:function(){return clone(state)},setMenuMode:setMenuMode});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
