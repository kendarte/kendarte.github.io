(function(){
"use strict";
var BUILD="0.4.0-inline-tsubasa-shots";
var queue=[],active=null,index=0,timer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==="object"?p:{}}
function battleRoot(){return byId("pokerol-pokemon-battle")}
function viewport(){return byId("pkb-battle-viewport")}
function ensure(){
  var root=byId("pkb-shot-layer");if(root)return root;
  var parent=viewport()||battleRoot();if(!parent)return null;
  root=document.createElement("div");root.id="pkb-shot-layer";root.className="pkbShotLayer";root.hidden=true;
  root.innerHTML='<div class="pkbShotSpeed" aria-hidden="true"></div><div class="pkbShotMedia" id="pkb-shot-media"></div><div class="pkbShotCorner"><span id="pkb-shot-kind">TOMA</span><b id="pkb-shot-progress">1/1</b></div>';
  parent.appendChild(root);return root;
}
function clamp(v,min,max,def){v=Number(v);return isFinite(v)?Math.max(min,Math.min(max,v)):def}
function assetHtml(src,kind,klass,style){src=text(src);kind=text(kind).toLowerCase();if(!src)return'';if(kind==="video"||/\.(mp4|webm|ogg)(\?|$)/i.test(src))return '<video class="'+klass+'" src="'+esc(src)+'" autoplay muted loop playsinline style="'+style+'"></video>';return '<img class="'+klass+'" src="'+esc(src)+'" alt="" style="'+style+'">'}
function mediaHtml(shot){
  var src=text(shot.media_src),kind=text(shot.media_type).toLowerCase();
  var scale=clamp(shot.media_scale,.25,4,1),ax=clamp(shot.media_anchor_x!=null?shot.media_anchor_x:shot.anchor_x,0,100,50),ay=clamp(shot.media_anchor_y!=null?shot.media_anchor_y:shot.anchor_y,0,100,100);
  var style='--pkb-shot-scale:'+scale+';--pkb-shot-ax:'+ax+'%;--pkb-shot-ay:'+ay+'%';
  var base=src?assetHtml(src,kind,'pkbShotAsset',style):'<div class="pkbShotNoMedia">'+esc(text(shot.pose||shot.shot)||"ACTION")+'</div>';
  var fx=text(shot.effect_asset),impact=text(shot.impact_asset);if(fx)base+=assetHtml(fx,'','pkbShotFx','');if(impact)base+=assetHtml(impact,'','pkbShotImpactFx','');return base;
}
function playSound(shot){var src=text(shot.sound_asset);if(!src)return;try{var audio=new Audio(src);audio.volume=.55;var p=audio.play();if(p&&typeof p.catch==='function')p.catch(function(){})}catch(e){}}
function narration(shot){
  var title=text(shot.title),copy=text(shot.text),line=title;
  if(copy&&copy.toUpperCase()!==title.toUpperCase())line+=(line?' — ':'')+copy;
  if(window.PokerolPokemonBattleV01&&typeof window.PokerolPokemonBattleV01.showNarration==='function')window.PokerolPokemonBattleV01.showNarration('NARRADOR',line||'...');
}
function shotFamily(name){name=text(name).toUpperCase();if(name.indexOf('DECLARATION_PLAYER')>=0||name==='EXECUTION')return'ATTACKER';if(name.indexOf('DECLARATION_ENEMY')>=0)return'ENEMY';if(name==='TARGET'||name==='REACTION'||name==='IMPACT')return'TARGET';if(name==='CONSEQUENCE')return'CONSEQUENCE';if(name==='END')return'END';return'ESTABLISHING'}
function show(){
  clearTimeout(timer);timer=null;
  if(!active||!Array.isArray(active.shots)||index>=active.shots.length){finish();return}
  var root=ensure();if(!root){timer=setTimeout(show,40);return}
  var shot=active.shots[index]||{},kind=text(shot.shot).toUpperCase();
  root.hidden=false;root.dataset.shot=kind;root.dataset.family=shotFamily(kind);root.dataset.pose=text(shot.pose).toUpperCase();
  byId("pkb-shot-media").innerHTML=mediaHtml(shot);byId("pkb-shot-kind").textContent=(kind||"TOMA").replace(/_/g," ");byId("pkb-shot-progress").textContent=(index+1)+"/"+active.shots.length;
  narration(shot);playSound(shot);
  timer=setTimeout(next,Math.max(520,Math.min(3200,Number(shot.duration_ms)||900)));
}
function play(packet){if(!packet||!Array.isArray(packet.shots)||!packet.shots.length)return;if(active){queue.push(packet);return}active=packet;index=0;show()}
function next(){if(!active)return;index+=1;show()}
function finish(){
  clearTimeout(timer);timer=null;var root=byId("pkb-shot-layer");if(root)root.hidden=true;active=null;index=0;
  if(window.PokerolPokemonBattleV01&&typeof window.PokerolPokemonBattleV01.restoreNarration==='function')window.PokerolPokemonBattleV01.restoreNarration();
  if(queue.length){active=queue.shift();show()}
}
function onShots(args){play(packetFrom(args));return true}
function onKey(ev){if(!active)return;if(ev.key==="Enter"||ev.key===" "||ev.key==="ArrowRight"){ev.preventDefault();next()}else if(ev.key==="Escape"){ev.preventDefault();finish()}}
function init(){document.addEventListener("keydown",onKey);if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function")Evennia.emitter.on("pokerol_battle_shots",onShots)}
window.PokerolBattleShotsV01=Object.freeze({BUILD:BUILD,play:play,next:next,finish:finish});if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
