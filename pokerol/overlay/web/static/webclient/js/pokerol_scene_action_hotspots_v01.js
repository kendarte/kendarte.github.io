(function(){
  'use strict';

  var scheduled=false;
  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function norm(v){return clean(v).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,' ').trim()}
  function coreLabel(v){
    var s=norm(v);
    return s.replace(/^(examinar|observar|mirar|hablar con|hablar|interactuar con|interactuar|usar|preguntar a|preguntar|entrar al|entrar a la|entrar a|ir hacia|ir a|ir al|salir hacia|salir a|salir|volver a|volver|cruzar hacia|cruzar)\s+/,'').trim();
  }
  function isExitLabel(v){return /^(entrar|ir\b|salir|volver|cruzar|subir|bajar|avanzar|seguir)/i.test(clean(v))}
  function representedByActor(core,actors){
    if(!core)return false;
    return actors.some(function(a){
      if(!a)return false;
      return a===core || (a.length>4&&core.indexOf(a)!==-1) || (core.length>4&&a.indexOf(core)!==-1);
    });
  }
  function currentActorCores(layer){
    return Array.from(layer.querySelectorAll('.pkActor:not(.pkActionHotspot) .pkActorLabel')).map(function(n){return coreLabel(n.textContent)}).filter(Boolean);
  }
  function removeOld(layer){Array.from(layer.querySelectorAll('.pkActionHotspot')).forEach(function(n){n.remove()})}
  function build(){
    scheduled=false;
    var actionsRoot=byId('pk-context-actions'),layer=byId('pk-actor-layer');
    if(!actionsRoot||!layer)return;
    removeOld(layer);
    var buttons=Array.from(actionsRoot.querySelectorAll('.pkContextButton'));
    if(!buttons.length)return;
    var actorCores=currentActorCores(layer);
    var candidates=[];
    buttons.forEach(function(button,index){
      var label=clean(button.textContent);if(!label)return;
      var core=coreLabel(label);if(!core)return;
      if(representedByActor(core,actorCores))return;
      candidates.push({button:button,label:label,core:core,index:index,isExit:isExitLabel(label)});
    });
    var exitRows=candidates.filter(function(r){return r.isExit}), otherRows=candidates.filter(function(r){return !r.isExit});
    candidates.forEach(function(row){
      var actor=document.createElement('button');
      actor.type='button';actor.className='pkActor pkActionHotspot';actor.dataset.kind=row.isExit?'EXIT':'ACTION';
      actor.dataset.pkHotspotKey='ACTION:'+row.core;
      var list=row.isExit?exitRows:otherRows;var pos=list.indexOf(row);var count=list.length;
      var x=count<=1?78:(22+(56*(pos/(count-1))));
      var y=row.isExit?8:(24+(pos%3)*12);
      actor.style.left=x.toFixed(2)+'%';actor.style.bottom=y.toFixed(2)+'%';
      var marker=document.createElement('span');marker.className='pkActionHotspotMarker';marker.textContent=row.isExit?'▶':'◆';actor.appendChild(marker);
      var label=document.createElement('span');label.className='pkActorLabel';label.textContent=row.label;actor.appendChild(label);
      actor.addEventListener('click',function(ev){
        if(byId('pk-stage')&&byId('pk-stage').classList.contains('pkHotspotEditing'))return;
        ev.preventDefault();row.button.click();
      });
      layer.appendChild(actor);
    });
  }
  function schedule(){if(scheduled)return;scheduled=true;setTimeout(build,0)}
  function init(){
    var tries=0;(function wait(){
      tries++;var root=byId('pk-context-actions'),layer=byId('pk-actor-layer');
      if(root&&layer){
        new MutationObserver(schedule).observe(root,{childList:true,subtree:true});
        schedule();return;
      }
      if(tries<120)setTimeout(wait,50);
    })();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
