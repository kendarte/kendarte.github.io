(function(){
"use strict";
var BUILD="0.3.0-fakemon-visual-pack";
var queue=[],active=null,index=0,timer=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?"":v).trim()}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[c]})}
function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==="object"?p:{}}
function ensure(){
  var root=byId("pkb-shot-layer");if(root)return root;
  root=document.createElement("div");root.id="pkb-shot-layer";root.className="pkbShotLayer";root.hidden=true;
  root.innerHTML='<div class="pkbShotFrame">'
    +'<div class="pkbShotRound"><span id="pkb-shot-mode">COMBATE</span><b id="pkb-shot-progress">1 / 1</b></div>'
    +'<div class="pkbShotMedia" id="pkb-shot-media"></div>'
    +'<div class="pkbShotText"><small id="pkb-shot-kind">TOMA</small><h2 id="pkb-shot-title"></h2><p id="pkb-shot-copy"></p></div>'
    +'<div class="pkbShotControls"><button id="pkb-shot-next" type="button">SIGUIENTE</button><button id="pkb-shot-skip" type="button">SALTAR SECUENCIA</button></div>'
    +'</div>';
  document.body.appendChild(root);
  byId("pkb-shot-next").onclick=next;byId("pkb-shot-skip").onclick=finish;
  root.addEventListener("click",function(ev){if(ev.target===root)next()});return root;
}
function clamp(v,min,max,def){v=Number(v);return isFinite(v)?Math.max(min,Math.min(max,v)):def}
function assetHtml(src,kind,klass,style){src=text(src);kind=text(kind).toLowerCase();if(!src)return'';if(kind==="video"||/\.(mp4|webm|ogg)(\?|$)/i.test(src))return '<video class="'+klass+'" src="'+esc(src)+'" autoplay muted loop playsinline style="'+style+'"></video>';return '<img class="'+klass+'" src="'+esc(src)+'" alt="" style="'+style+'">'}
function mediaHtml(shot){
  var src=text(shot.media_src),kind=text(shot.media_type).toLowerCase();
  var scale=clamp(shot.media_scale,.25,4,1),ax=clamp(shot.media_anchor_x!=null?shot.media_anchor_x:shot.anchor_x,0,100,50),ay=clamp(shot.media_anchor_y!=null?shot.media_anchor_y:shot.anchor_y,0,100,100);
  var style='--pkb-shot-scale:'+scale+';--pkb-shot-ax:'+ax+'%;--pkb-shot-ay:'+ay+'%';
  var base=src?assetHtml(src,kind,'pkbShotAsset',style):'<div class="pkbShotNoMedia">'+esc(text(shot.pose||shot.shot)||"POKEROL")+'</div>';
  var fx=text(shot.effect_asset),impact=text(shot.impact_asset);if(fx)base+=assetHtml(fx,'','pkbShotFx','');if(impact)base+=assetHtml(impact,'','pkbShotImpactFx','');return base;
}
function playSound(shot){var src=text(shot.sound_asset);if(!src)return;try{var audio=new Audio(src);audio.volume=.55;var p=audio.play();if(p&&typeof p.catch==='function')p.catch(function(){})}catch(e){}}
function show(){
  clearTimeout(timer);timer=null;var root=ensure();if(!active||!Array.isArray(active.shots)||index>=active.shots.length){finish();return}
  var shot=active.shots[index]||{};root.hidden=false;root.dataset.shot=text(shot.shot).toUpperCase();root.dataset.pose=text(shot.pose).toUpperCase();byId("pkb-shot-media").innerHTML=mediaHtml(shot);playSound(shot);
  byId("pkb-shot-mode").textContent='TURNO '+(active.turn||1);byId("pkb-shot-progress").textContent=(index+1)+' / '+active.shots.length;byId("pkb-shot-kind").textContent=(text(shot.shot)||"TOMA").replace(/_/g," ");byId("pkb-shot-title").textContent=text(shot.title)||"";byId("pkb-shot-copy").textContent=text(shot.text)||"";
  timer=setTimeout(next,Math.max(650,Math.min(4200,Number(shot.duration_ms)||950)));
}
function play(packet){if(!packet||!Array.isArray(packet.shots)||!packet.shots.length)return;if(active){queue.push(packet);return}active=packet;index=0;show()}
function next(){if(!active)return;index+=1;show()}
function finish(){clearTimeout(timer);timer=null;var root=ensure();root.hidden=true;active=null;index=0;if(queue.length){active=queue.shift();show()}}
function onShots(args){play(packetFrom(args));return true}
function onKey(ev){if(!active)return;if(ev.key==="Enter"||ev.key===" "||ev.key==="ArrowRight"){ev.preventDefault();next()}else if(ev.key==="Escape"){ev.preventDefault();finish()}}
function init(){ensure();document.addEventListener("keydown",onKey);if(!window.Evennia)return;Evennia.init();if(Evennia.emitter&&typeof Evennia.emitter.on==="function")Evennia.emitter.on("pokerol_battle_shots",onShots)}
window.PokerolBattleShotsV01=Object.freeze({BUILD:BUILD,play:play,next:next,finish:finish});if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();