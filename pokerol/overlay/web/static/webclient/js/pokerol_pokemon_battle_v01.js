(function(){
"use strict";
var BUILD="0.6.0-tsubasa-shared-frame";
var state=null;
var menuMode="ACTION";
var pendingItemId="";
var pendingItemSlot=null;
var pendingMoveId="";
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function clone(v){try{return JSON.parse(JSON.stringify(v))}catch(e){return v}}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function pct(cur,max){max=Math.max(1,Number(max)||1);return Math.max(0,Math.min(100,(Number(cur)||0)/max*100))}
function battleReady(){return !!state&&text(state.status).toUpperCase()==="ACTIVE"&&text(state.phase).toUpperCase()==="COMMAND"}
function forcedSwitch(){return !!(state&&state.forced_switch)}
function clearPendingItem(){pendingItemId="";pendingItemSlot=null}
function clearPendingMove(){pendingMoveId=""}
function clearPending(){clearPendingItem();clearPendingMove()}
function host(){return byId("pokerol-client")||document.body}
function ensure(){
  var root=byId("pokerol-pokemon-battle");
  if(root)return root;
  root=document.createElement("section");
  root.id="pokerol-pokemon-battle";
  root.className="pokerolPokemonBattle";
  root.setAttribute("aria-label","Modo combate");
  root.innerHTML=''
    +'<div class="pkbTransitionCurtain" aria-hidden="true"></div>'
    +'<div class="pkbBattleViewport" id="pkb-battle-viewport">'
      +'<div class="pkbBattleBackdrop" id="pkb-battle-bg"></div>'
      +'<div class="pkbBattleShade"></div>'
      +'<div class="pkbBattleMeta"><span id="pkb-site">COMBATE</span><span id="pkb-phase">COMMAND</span></div>'
      +'<div class="pkbInfo pkbEnemyInfo" id="pkb-enemy-info"></div>'
      +'<div class="pkbInfo pkbPlayerInfo" id="pkb-player-info"></div>'
      +'<div class="pkbSpriteWrap pkbEnemySpriteWrap" id="pkb-enemy-sprite"></div>'
      +'<div class="pkbSpriteWrap pkbPlayerSpriteWrap" id="pkb-player-sprite"></div>'
    +'</div>'
    +'<div class="pkbNarrator"><div class="pkbNarratorHead"><span id="pkb-narrator-label">NARRADOR</span><span id="pkb-turn">TURNO 1</span></div><div class="pkbLog" id="pkb-log"></div></div>'
    +'<div class="pkbCommandDeck"><div class="pkbCommandHead"><span id="pkb-menu-title">ORDEN</span><span id="pkb-command-hint">SKILLS + ACCIONES</span></div><div class="pkbMenuBody" id="pkb-menu-body"></div></div>'
    +'<div id="pkb-free-order-slot" class="pkbFreeOrderSlot"></div>'
    +'<div class="pkbOutcome"><div class="pkbOutcomeCard"><h2 id="pkb-outcome-title">COMBATE TERMINADO</h2><p id="pkb-outcome-text"></p><button class="pkbReturn" id="pkb-return" type="button">VOLVER</button></div></div>';
  host().appendChild(root);
  byId("pkb-return").onclick=closeBattle;
  return root;
}
function statusLabel(p){var s=text(p&&p.status).toUpperCase();return s&&s!=="OK"?'<span class="pkbStatus">'+esc(s)+'</span>':''}
function infoHtml(p){
  p=p||{};
  var types=(p.types||[]).map(function(t){return '<span>'+esc(t)+'</span>'}).join('');
  var hp=pct(p.hp_current,p.hp_max);
  return '<div class="pkbNameRow"><span>'+esc(p.name||p.species_name||"PKM")+'</span><span>LV '+esc(p.level||1)+'</span></div>'
    +'<div class="pkbTypes">'+types+statusLabel(p)+'</div>'
    +'<div class="pkbHpRow"><span class="pkbHpLabel">HP</span><div class="pkbHpTrack"><div class="pkbHpFill" style="width:'+hp+'%"></div></div><span class="pkbHpText">'+esc(p.hp_current)+' / '+esc(p.hp_max)+'</span></div>';
}
function spriteHtml(p,side){
  var s=p&&p.sprite||{};
  var src=side==="PLAYER"?(s.back||s.front):(s.front||s.back);
  var scale=Number(s.scale)||1;
  if(src)return '<img class="pkbSprite" src="'+esc(src)+'" alt="'+esc(p.name||p.species_name||"PKM")+'" style="--pkb-scale:'+scale+'">';
  var name=text(p&&p.name||p&&p.species_name||"PKM");
  return '<div class="pkbFallback">'+esc(name.slice(0,2).toUpperCase())+'</div>';
}
function moveButton(m,disabled,attrName){
  var ppMax=Number(m.pp_max!=null?m.pp_max:m.pp)||0;
  var ppCur=Number(m.pp_current!=null?m.pp_current:ppMax);
  var noPP=ppMax>0&&ppCur<=0;
  var attr=attrName||"data-move";
  var world=m.world_enabled&&Array.isArray(m.world_effects)&&m.world_effects.length?' · ENTORNO':'';
  return '<button class="pkbMove" '+attr+'="'+esc(m.move_id)+'" '+(disabled||noPP?'disabled':'')+'><b>'+esc(m.name||m.move_id)+'</b><small>'+esc(m.pokemon_type||"")+' · PP '+esc(ppCur)+'/'+esc(ppMax)+world+'</small></button>';
}
function outcomeText(v){var map={PLAYER_WIN:"VICTORIA",PLAYER_LOSS:"DERROTA",DRAW:"EMPATE",CAPTURED:"CAPTURADO",ESCAPED:"ESCAPASTE",ABANDONED:"COMBATE TERMINADO"};return map[text(v).toUpperCase()]||text(v)||"COMBATE TERMINADO"}
function menuTitle(value){
  if(forcedSwitch()&&value==="PARTY")return "ELIGE REEMPLAZO";
  var map={ACTION:"ORDEN",MOVE:"MOVIMIENTOS",MOVE_TARGET:"OBJETIVO",ENV_TARGET:"ENTORNO",PARTY:"CAMBIO",BAG:"BOLSA",ITEM_TARGET:"OBJETIVO",ITEM_MOVE:"MOVIMIENTO"};
  return map[value]||"ORDEN";
}
function setMenuMode(next){if(forcedSwitch()&&next!=="PARTY")next="PARTY";if(next==="ACTION")clearPending();menuMode=next;renderMenu()}
function playerMoves(){return state&&state.player&&Array.isArray(state.player.moves)?state.player.moves:[]}
function moveAt(moveId){var wanted=text(moveId).toUpperCase();return playerMoves().find(function(m){return text(m.move_id).toUpperCase()===wanted})||null}
function partyRows(){return state&&state.party_state&&Array.isArray(state.party_state.party)?state.party_state.party:[]}
function partyAt(slot){return partyRows().find(function(p){return Number(p.party_slot)===Number(slot)})||null}
function bagItems(){return state&&state.bag_state&&state.bag_state.items&&typeof state.bag_state.items==="object"?state.bag_state.items:{}}
function bagProfiles(){return state&&state.bag_state&&state.bag_state.profiles&&typeof state.bag_state.profiles==="object"?state.bag_state.profiles:{}}
function bagProfile(itemId){return bagProfiles()[itemId]||{kind:/_BALL$/i.test(itemId)?"CAPTURE":"UNKNOWN",battle_usable:false,label:itemId.replace(/_/g," ")}}
function environmentRows(){return state&&Array.isArray(state.environment_targets)?state.environment_targets:[]}
function authoritativeWorldTargets(moveId){var map=state&&state.world_move_targets&&typeof state.world_move_targets==="object"?state.world_move_targets:null;if(!map)return null;var direct=map[moveId];if(Array.isArray(direct))return direct;var wanted=text(moveId).toUpperCase(),key=Object.keys(map).find(function(k){return text(k).toUpperCase()===wanted});return key&&Array.isArray(map[key])?map[key]:[]}
function compatibleWorldTargets(move){
  if(!move)return[];
  var authoritative=authoritativeWorldTargets(move.move_id);if(authoritative!==null)return authoritative;
  var accepted=(move.materials||[]).map(function(v){return text(v).toUpperCase()}).filter(Boolean);
  return environmentRows().filter(function(row){if(!accepted.length)return true;var tags=(row.materials||[]).concat(row.tags||[]).map(function(v){return text(v).toUpperCase()});return accepted.some(function(v){return tags.indexOf(v)>=0})});
}
function partySlotHtml(p,disabled,mode){
  var slot=Number(p.party_slot)||0,name=text(p.nickname||p.species_name||"PKM"),sprite=p.sprite&&text(p.sprite.icon||p.sprite.front);
  var icon=sprite?'<img class="pkbPartyIcon" src="'+esc(sprite)+'" alt="">':'<span class="pkbPartyInitial">'+esc(name.slice(0,1))+'</span>';
  var hp=esc(p.hp_current)+'/'+esc(p.hp_max),flags=(p.active?' ACTIVO':'')+(Number(p.hp_current)<=0?' K.O.':'');
  var block=disabled;if(mode==="SWITCH")block=block||p.active||Number(p.hp_current)<=0;
  return '<button class="pkbPartySlot" data-slot="'+slot+'" '+(block?'disabled':'')+'>'+icon+'<span><b>'+esc(name)+'</b><small>LV '+esc(p.level)+' · HP '+hp+' · '+esc(p.status||'OK')+flags+'</small></span></button>';
}
function itemLabel(itemId,profile){return text(profile&&profile.label)||text(itemId).replace(/_/g,' ')}
function itemTargetEligible(profile,p){
  if(!profile||!p)return false;
  var kind=text(profile.kind).toUpperCase(),hp=Number(p.hp_current)||0,hpMax=Math.max(1,Number(p.hp_max)||1),status=text(p.status).toUpperCase()||"OK";
  if(kind==="HEAL")return hp>0&&hp<hpMax;if(kind==="CURE")return status===text(profile.status).toUpperCase();if(kind==="CURE_ALL")return status!=="OK";if(kind==="REVIVE")return hp<=0;
  if(kind==="PP"||kind==="PP_FULL")return Array.isArray(p.moves)&&p.moves.some(function(m){var max=Number(m.pp_max!=null?m.pp_max:m.pp)||0,cur=Number(m.pp_current!=null?m.pp_current:max);return cur<max});
  return false;
}
function bindActionButton(id,fn){var n=byId(id);if(n)n.onclick=fn}
function openPosition(){if(window.PokerolBattlePositionUiV01&&typeof window.PokerolBattlePositionUiV01.requestOptions==="function")window.PokerolBattlePositionUiV01.requestOptions()}
function openReaction(){if(window.PokerolBattleReactionUiV01&&typeof window.PokerolBattleReactionUiV01.requestOptions==="function")window.PokerolBattleReactionUiV01.requestOptions()}
function renderActionMenu(body,disabled){
  var moves=playerMoves();
  body.innerHTML='<div class="pkbMoveStrip">'+(moves.length?moves.slice(0,4).map(function(m){return moveButton(m,disabled)}).join(''):'<div class="pkbStubText">SIN MOVIMIENTOS DISPONIBLES.</div>')+'</div>'
    +'<div class="pkbUtilityStrip">'
      +'<button class="pkbUtility" id="pkb-move-position" '+(disabled?'disabled':'')+'>MOVER</button>'
      +'<button class="pkbUtility" id="pkb-reaction-menu" '+(disabled?'disabled':'')+'>REACCIÓN</button>'
      +'<button class="pkbUtility" id="pkb-party" '+(disabled?'disabled':'')+'>CAMBIO</button>'
      +'<button class="pkbUtility" id="pkb-bag" '+(disabled?'disabled':'')+'>BOLSA</button>'
      +'<button class="pkbUtility" id="pkb-run" '+(disabled||text(state&&state.battle_kind).toUpperCase()!=="WILD"?'disabled':'')+'>HUIR</button>'
    +'</div>';
  Array.prototype.forEach.call(body.querySelectorAll("[data-move]"),function(btn){btn.onclick=function(){var id=btn.getAttribute("data-move"),move=moveAt(id);if(move&&move.world_enabled&&Array.isArray(move.world_effects)&&move.world_effects.length){pendingMoveId=id;setMenuMode("MOVE_TARGET")}else sendAction({type:"MOVE",move_id:id})}});
  bindActionButton("pkb-move-position",openPosition);bindActionButton("pkb-reaction-menu",openReaction);bindActionButton("pkb-party",function(){setMenuMode("PARTY")});bindActionButton("pkb-bag",function(){setMenuMode("BAG")});bindActionButton("pkb-run",function(){sendAction({type:"RUN"})});
}
function renderMenu(){
  ensure();var body=byId("pkb-menu-body");if(!body)return;if(forcedSwitch())menuMode="PARTY";byId("pkb-menu-title").textContent=menuTitle(menuMode);var disabled=!battleReady();
  if(menuMode==="ACTION"){renderActionMenu(body,disabled);return}
  if(menuMode==="MOVE"){
    body.innerHTML='<div class="pkbMoveGrid">'+(playerMoves().map(function(m){return moveButton(m,disabled)}).join('')||'<div class="pkbStubText">SIN MOVIMIENTOS.</div>')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-move]"),function(btn){btn.onclick=function(){var id=btn.getAttribute("data-move"),move=moveAt(id);if(move&&move.world_enabled&&Array.isArray(move.world_effects)&&move.world_effects.length){pendingMoveId=id;setMenuMode("MOVE_TARGET")}else sendAction({type:"MOVE",move_id:id})}});byId("pkb-back").onclick=function(){setMenuMode("ACTION")};return;
  }
  if(menuMode==="MOVE_TARGET"){
    var selectedMove=moveAt(pendingMoveId),targets=compatibleWorldTargets(selectedMove);
    body.innerHTML='<div class="pkbChoiceTitle">'+esc(selectedMove&&selectedMove.name||pendingMoveId)+'</div><div class="pkbChoiceGrid"><button class="pkbAction" id="pkb-target-rival" '+(disabled?'disabled':'')+'>RIVAL</button><button class="pkbAction" id="pkb-target-world" '+(disabled||!targets.length?'disabled':'')+'>ENTORNO</button></div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    byId("pkb-target-rival").onclick=function(){sendAction({type:"MOVE",move_id:pendingMoveId})};if(byId("pkb-target-world"))byId("pkb-target-world").onclick=function(){setMenuMode("ENV_TARGET")};byId("pkb-back").onclick=function(){clearPendingMove();setMenuMode("ACTION")};return;
  }
  if(menuMode==="ENV_TARGET"){
    var worldMove=moveAt(pendingMoveId),worldTargets=compatibleWorldTargets(worldMove);
    body.innerHTML='<div class="pkbChoiceTitle">'+esc(worldMove&&worldMove.name||pendingMoveId)+' → ENTORNO</div><div class="pkbBagList">'+(worldTargets.length?worldTargets.map(function(t,index){var mats=(t.materials||[]).concat(t.tags||[]).join(' / ');return '<button class="pkbBagItem" data-env-index="'+index+'"><b>'+esc(t.name||t.object_id||('OBJ '+t.dbref))+'</b><small>'+esc(mats)+'</small></button>'}).join(''):'<div class="pkbStubText">NO HAY OBJETIVOS COMPATIBLES.</div>')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-env-index]"),function(btn){btn.onclick=function(){var target=worldTargets[Number(btn.getAttribute("data-env-index"))];if(!target)return;sendAction({type:"FREE_ORDER",move_id:pendingMoveId,world_target:{object_id:target.object_id||"",dbref:target.dbref,name:target.name||""}})}});byId("pkb-back").onclick=function(){setMenuMode("MOVE_TARGET")};return;
  }
  if(menuMode==="PARTY"){
    var party=partyRows(),intro=forcedSwitch()?'<div class="pkbStubText">ELIGE UN PKM CAPAZ DE CONTINUAR.</div>':'',back=forcedSwitch()?'':'<button class="pkbBack" id="pkb-back">ATRÁS</button>';
    body.innerHTML=intro+'<div class="pkbPartyList">'+(party.length?party.map(function(p){return partySlotHtml(p,disabled,"SWITCH")}).join(''):'<div class="pkbStubText">SIN PARTY DISPONIBLE.</div>')+'</div>'+back;
    Array.prototype.forEach.call(body.querySelectorAll("[data-slot]"),function(btn){btn.onclick=function(){sendAction({type:"SWITCH",slot:Number(btn.getAttribute("data-slot"))})}});var partyBack=byId("pkb-back");if(partyBack)partyBack.onclick=function(){setMenuMode("ACTION")};return;
  }
  if(menuMode==="BAG"){
    var items=bagItems(),profiles=bagProfiles(),keys=Object.keys(items).filter(function(k){return Number(items[k])>0}),wild=state&&text(state.battle_kind).toUpperCase()==="WILD";
    body.innerHTML='<div class="pkbBagList">'+(keys.length?keys.map(function(k){var p=profiles[k]||bagProfile(k),kind=text(p.kind).toUpperCase(),capture=kind==="CAPTURE",support=!!p.battle_usable&&!capture&&kind!=="CAPTURE_RESERVED"&&kind!=="UNKNOWN",usable=!disabled&&((capture&&wild)||support),note=capture?'CAPTURA':support?kind:'NO USABLE';return '<button class="pkbBagItem" data-item="'+esc(k)+'" '+(!usable?'disabled':'')+'><b>'+esc(itemLabel(k,p))+'</b><small>x'+esc(items[k])+' · '+esc(note)+'</small></button>'}).join(''):'<div class="pkbStubText">BOLSA VACÍA.</div>')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-item]"),function(btn){btn.onclick=function(){var item=btn.getAttribute("data-item"),profile=bagProfile(item),kind=text(profile.kind).toUpperCase();if(kind==="CAPTURE")sendAction({type:"CAPTURE",item_id:item});else{pendingItemId=item;pendingItemSlot=null;setMenuMode("ITEM_TARGET")}}});byId("pkb-back").onclick=function(){setMenuMode("ACTION")};return;
  }
  if(menuMode==="ITEM_TARGET"){
    var targetProfile=bagProfile(pendingItemId),targetParty=partyRows();
    body.innerHTML='<div class="pkbChoiceTitle">'+esc(itemLabel(pendingItemId,targetProfile))+'</div><div class="pkbPartyList">'+targetParty.map(function(p){return partySlotHtml(p,disabled||!itemTargetEligible(targetProfile,p),"ITEM")}).join('')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-slot]"),function(btn){btn.onclick=function(){pendingItemSlot=Number(btn.getAttribute("data-slot"));if(targetProfile.requires_move)setMenuMode("ITEM_MOVE");else sendAction({type:"ITEM",item_id:pendingItemId,slot:pendingItemSlot})}});byId("pkb-back").onclick=function(){pendingItemSlot=null;setMenuMode("BAG")};return;
  }
  if(menuMode==="ITEM_MOVE"){
    var target=partyAt(pendingItemSlot),itemP=bagProfile(pendingItemId),itemMoves=target&&Array.isArray(target.moves)?target.moves:[];
    body.innerHTML='<div class="pkbChoiceTitle">'+esc(itemLabel(pendingItemId,itemP))+' → '+esc(target&&(target.nickname||target.species_name)||"PKM")+'</div><div class="pkbMoveGrid">'+itemMoves.map(function(m){var max=Number(m.pp_max!=null?m.pp_max:m.pp)||0,cur=Number(m.pp_current!=null?m.pp_current:max),full=cur>=max;return moveButton(m,disabled||full,'data-item-move')}).join('')+'</div><button class="pkbBack" id="pkb-back">ATRÁS</button>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-item-move]"),function(btn){btn.onclick=function(){sendAction({type:"ITEM",item_id:pendingItemId,slot:pendingItemSlot,move_id:btn.getAttribute("data-item-move")})}});byId("pkb-back").onclick=function(){setMenuMode("ITEM_TARGET")};return;
  }
}
function showNarration(title,copy){
  ensure();var log=byId("pkb-log"),label=byId("pkb-narrator-label");if(label)label.textContent=text(title)||"NARRADOR";if(log)log.innerHTML='<div class="pkbLogLine pkbShotNarration">'+esc(copy||title||"")+'</div>';
}
function restoreNarration(){
  if(!state)return;var log=byId("pkb-log"),label=byId("pkb-narrator-label");if(label)label.textContent="NARRADOR";if(!log)return;var rows=(state.log||[]).slice(-4);log.innerHTML=rows.map(function(row){return '<div class="pkbLogLine">'+esc(row.text||row.kind||"")+'</div>'}).join('')||'<div class="pkbLogLine">ESPERANDO ORDEN.</div>';
}
function render(packet){
  state=clone(packet||{});if(forcedSwitch())menuMode="PARTY";var root=ensure();root.setAttribute("data-open","true");root.setAttribute("data-complete",text(state.status).toUpperCase()==="COMPLETE"?"true":"false");root.setAttribute("data-forced-switch",forcedSwitch()?"true":"false");document.body.classList.add("pkCombatMode");
  var site=state.site||{},bg=text(site.scene_image&&site.scene_image.src),backdrop=byId("pkb-battle-bg");if(backdrop)backdrop.style.backgroundImage=bg?'url("'+bg.replace(/"/g,'%22')+'")':'';
  byId("pkb-site").textContent=text(site.name)||"COMBATE";byId("pkb-phase").textContent=forcedSwitch()?"CAMBIO":(text(state.phase)||"COMMAND");byId("pkb-turn").textContent="TURNO "+(state.turn||1);
  byId("pkb-player-info").innerHTML=infoHtml(state.player||{});byId("pkb-enemy-info").innerHTML=infoHtml(state.enemy||{});byId("pkb-player-sprite").innerHTML=spriteHtml(state.player||{},"PLAYER");byId("pkb-enemy-sprite").innerHTML=spriteHtml(state.enemy||{},"ENEMY");restoreNarration();
  if(text(state.status).toUpperCase()==="COMPLETE"){byId("pkb-outcome-title").textContent=outcomeText(state.outcome);var collection=state.capture_collection_result||{},collectionText=text(collection.status)==="ADDED_TO_PARTY"?' · EQUIPO':text(collection.status)==="SENT_TO_STORAGE"?' · STORAGE':'';byId("pkb-outcome-text").textContent=(state.player&&state.player.name?state.player.name+" · ":"")+(state.enemy&&state.enemy.name?state.enemy.name:"")+collectionText}
  renderMenu();
}
function encode(value){var json=JSON.stringify(value),raw=unescape(encodeURIComponent(json)),bin="";for(var i=0;i<raw.length;i++)bin+=String.fromCharCode(raw.charCodeAt(i));return btoa(bin).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"")}
function sendAction(action){if(!battleReady())return;if(forcedSwitch()&&text(action&&action.type).toUpperCase()!=="SWITCH")return;if(!window.Evennia||!Evennia.isConnected())return;disableCommands();Evennia.msg("text",["pokerol-battle-action "+encode(action)],{})}
function disableCommands(){var root=ensure();Array.prototype.forEach.call(root.querySelectorAll("button"),function(btn){if(!btn.classList.contains("pkbReturn"))btn.disabled=true})}
function closeBattle(){
  var root=ensure();root.setAttribute("data-closing","true");window.setTimeout(function(){root.removeAttribute("data-open");root.removeAttribute("data-complete");root.removeAttribute("data-forced-switch");root.removeAttribute("data-closing");document.body.classList.remove("pkCombatMode");state=null;menuMode="ACTION";clearPending();if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("EXPLORATION")},220);
}
function onState(args){var packet=args&&args[0];if(!packet||typeof packet!=="object")return;clearPending();menuMode=packet.forced_switch?"PARTY":"ACTION";if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("COMBAT");render(packet)}
function onError(args){var packet=args&&args[0];if(!packet)return;var log=byId("pkb-log");if(log)log.innerHTML+='<div class="pkbLogLine pkbErrorLine">ACCIÓN RECHAZADA: '+esc(packet.status)+'</div>';renderMenu()}
function onKey(event){if(!state||!byId("pokerol-pokemon-battle")||byId("pokerol-pokemon-battle").getAttribute("data-open")!=="true")return;if(event.key==="Escape"&&menuMode!=="ACTION"&&!forcedSwitch()){event.preventDefault();if(menuMode==="ITEM_MOVE")setMenuMode("ITEM_TARGET");else if(menuMode==="ITEM_TARGET")setMenuMode("BAG");else if(menuMode==="ENV_TARGET")setMenuMode("MOVE_TARGET");else setMenuMode("ACTION")}}
function init(){ensure();document.addEventListener("keydown",onKey);if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function"){Evennia.emitter.on("pokerol_pokemon_battle_state",onState);Evennia.emitter.on("pokerol_pokemon_battle_error",onError)}}
window.PokerolPokemonBattleV01=Object.freeze({BUILD:BUILD,render:render,close:closeBattle,getState:function(){return clone(state)},setMenuMode:setMenuMode,showNarration:showNarration,restoreNarration:restoreNarration});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
