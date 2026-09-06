(function(){
  'use strict';

  var lastRoomKey='';
  var timer=0;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function currentRoomKey(){
    var id=clean(byId('pk-room-id')&&byId('pk-room-id').textContent);
    var name=clean(byId('pk-room-name')&&byId('pk-room-name').textContent);
    if(id)return id;
    if(name&&!/conectando|ubicaci[oó]n actual/i.test(name))return 'ROOMNAME:'+name.toLowerCase();
    return '';
  }
  function ensureOverlay(){
    var stage=byId('pk-stage');if(!stage)return null;
    var overlay=byId('pk-room-transition');
    if(!overlay){
      overlay=document.createElement('div');
      overlay.id='pk-room-transition';
      overlay.className='pkRoomTransition';
      overlay.setAttribute('aria-hidden','true');
      stage.appendChild(overlay);
    }
    return overlay;
  }
  function playTransition(){
    var stage=byId('pk-stage');if(!stage)return;
    ensureOverlay();
    if(timer){clearTimeout(timer);timer=0}
    stage.classList.remove('pkRoomTransitioning');
    void stage.offsetWidth;
    stage.classList.add('pkRoomTransitioning');
    timer=setTimeout(function(){stage.classList.remove('pkRoomTransitioning');timer=0},620);
  }
  function checkRoom(){
    var key=currentRoomKey();
    if(!key)return;
    if(!lastRoomKey){lastRoomKey=key;return}
    if(key!==lastRoomKey){lastRoomKey=key;playTransition()}
  }
  function init(){
    var tries=0;(function wait(){
      tries++;
      var stage=byId('pk-stage'),rid=byId('pk-room-id'),name=byId('pk-room-name');
      if(stage&&(rid||name)){
        ensureOverlay();
        lastRoomKey=currentRoomKey();
        var observer=new MutationObserver(function(){setTimeout(checkRoom,0)});
        if(rid)observer.observe(rid,{childList:true,subtree:true,characterData:true});
        if(name)observer.observe(name,{childList:true,subtree:true,characterData:true});
        return;
      }
      if(tries<160)setTimeout(wait,50);
    })()}

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
