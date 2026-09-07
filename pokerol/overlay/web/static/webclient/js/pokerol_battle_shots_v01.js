(function(){
"use strict";
var BUILD="0.1.0-authoritative-anime-shots";
var queue=[],active=null,index=0,timer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==="object"?p:{}}
function ensure(){
  var root=byId("pkb-shot-layer");if(root)return root;
  root=document.createElement("div");root.id="pkb-shot-layer";root.className="pkbShotLayer";root.hidden=true;
  root.innerHTML='<div class="pkbShotFrame">'
    +'<div class="pkbShotMedia" id="pkb-shot-media"></div>'
    +'<div class="pkbShotText"><small id="pkb-shot-kind">TOMA</small><h2 id="pkb-shot-title"></h2><p id="pkb-shot-copy"></p></div>'
    +'<div class="pkbShotControls"><button id="pkb-shot-next" type="button">SIGUIENTE</button><button id="pkb-shot-skip" type="button">SALTAR</button></div>'
    +'</div>';
  document.body.appendChild(root);
  byId("pkb-shot-next").onclick=next;
  byId("pkb-shot-skip").onclick=finish;
  root.addEventListener("click",function(ev){if(ev.target===root)next()});
  return root;
}
function mediaHtml(shot){
  var src=text(shot.media_src),kind=text(shot.media_type).toLowerCase();
  if(!src)return '<div class="pkbShotNoMedia">'+esc(text(shot.shot)||"POKEROL")+'</div>';
  if(kind==="video")return '<video class="pkbShotAsset" src="'+esc(src)+'" autoplay muted playsinline></video>';
  return '<img class="pkbShotAsset" src="'+esc(src)+'" alt="">';
}
function show(){
  clearTimeout(timer);timer=null;
  var root=ensure();
  if(!active||!Array.isArray(active.shots)||index>=active.shots.length){finish();return}
  var shot=active.shots[index]||{};
  root.hidden=false;root.dataset.shot=text(shot.shot).toUpperCase();
  byId("pkb-shot-media").innerHTML=mediaHtml(shot);
  byId("pkb-shot-kind").textContent=(text(shot.shot)||"TOMA").replace(/_/g," ");
  byId("pkb-shot-title").textContent=text(shot.title)||"";
  byId("pkb-shot-copy").textContent=text(shot.text)||"";
  var wait=Math.max(500,Math.min(3500,Number(shot.duration_ms)||950));
  timer=setTimeout(next,wait);
}
function play(packet){
  if(!packet||!Array.isArray(packet.shots)||!packet.shots.length)return;
  if(active){queue.push(packet);return}
  active=packet;index=0;show();
}
function next(){if(!active)return;index+=1;show()}
function finish(){
  clearTimeout(timer);timer=null;
  var root=ensure();root.hidden=true;
  active=null;index=0;
  if(queue.length){active=queue.shift();show()}
}
function onShots(args){play(packetFrom(args));return true}
function onKey(ev){if(!active)return;if(ev.key==="Enter"||ev.key===" "||ev.key==="ArrowRight"){ev.preventDefault();next()}else if(ev.key==="Escape"){ev.preventDefault();finish()}}
function init(){ensure();document.addEventListener("keydown",onKey);if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function")Evennia.emitter.on("pokerol_battle_shots",onShots)}
window.PokerolBattleShotsV01=Object.freeze({BUILD:BUILD,play:play,next:next,finish:finish});
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
