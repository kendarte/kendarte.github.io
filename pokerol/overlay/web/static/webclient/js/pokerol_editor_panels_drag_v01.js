(function(){
  'use strict';
  var PREFIX='pokerol_editor_panel_pos_v1:';
  function byId(id){return document.getElementById(id)}
  function clamp(v,min,max){return Math.max(min,Math.min(max,v))}
  function save(panel){
    try{localStorage.setItem(PREFIX+panel.id,JSON.stringify({left:panel.style.left,top:panel.style.top}))}catch(e){}
  }
  function restore(panel){
    try{
      var raw=localStorage.getItem(PREFIX+panel.id);if(!raw)return;
      var pos=JSON.parse(raw);if(pos.left)panel.style.left=pos.left;if(pos.top)panel.style.top=pos.top;
      panel.style.right='auto';panel.style.bottom='auto';
    }catch(e){}
  }
  function bind(panel,handle){
    if(!panel||!handle||panel.dataset.pkDragBound==='1')return;
    panel.dataset.pkDragBound='1';restore(panel);handle.classList.add('pkEditorDragHandle');
    handle.addEventListener('pointerdown',function(ev){
      if(ev.target.closest('button,input,select,textarea'))return;
      var stage=byId('pk-stage');if(!stage)return;
      ev.preventDefault();
      var sr=stage.getBoundingClientRect(),pr=panel.getBoundingClientRect();
      var start={id:ev.pointerId,x:ev.clientX,y:ev.clientY,left:pr.left-sr.left,top:pr.top-sr.top,sr:sr};
      handle.setPointerCapture&&handle.setPointerCapture(ev.pointerId);
      function move(e){
        if(e.pointerId!==start.id)return;e.preventDefault();
        var maxL=Math.max(0,start.sr.width-panel.offsetWidth),maxT=Math.max(0,start.sr.height-panel.offsetHeight);
        var left=clamp(start.left+(e.clientX-start.x),0,maxL),top=clamp(start.top+(e.clientY-start.y),0,maxT);
        panel.style.left=left+'px';panel.style.top=top+'px';panel.style.right='auto';panel.style.bottom='auto';
      }
      function up(e){
        if(e.pointerId!==start.id)return;handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',up);handle.removeEventListener('pointercancel',up);save(panel);
      }
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',up);handle.addEventListener('pointercancel',up);
    });
  }
  function init(){
    var tries=0;(function wait(){
      tries++;
      var menu=byId('pk-edit-menu'),hot=byId('pk-hotspot-panel'),player=byId('pk-player-panel');
      if(menu&&hot&&player){
        bind(menu,menu.querySelector('.pkEditMenuHead'));
        bind(hot,hot.querySelector('.pkHotspotPanelHead'));
        bind(player,player.querySelector('.pkPlayerPanelHead'));
        return;
      }
      if(tries<160)setTimeout(wait,50);
    })();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
