(function(){
  'use strict';

  var BUILD='0.1.0-editor-input-guard';
  var EDITOR_ROOTS='#pk-hotspot-panel,#pk-room-panel,#pk-player-panel,#pk-edit-menu,.pkHotspotPanel,.pkRoomPanel,.pkPlayerPanel,.pkEditMenu';
  var EDITABLE='input,textarea,select,[contenteditable="true"]';

  function isEditorField(target){
    if(!target||!target.matches||!target.closest)return false;
    return target.matches(EDITABLE)&&!!target.closest(EDITOR_ROOTS);
  }

  function guardKeyboardEvent(event){
    if(isEditorField(event.target))event.stopPropagation();
  }

  function bind(){
    var stage=document.getElementById('pk-stage');
    if(!stage||stage.dataset.pkEditorInputGuard==='1')return false;
    stage.dataset.pkEditorInputGuard='1';
    stage.addEventListener('keydown',guardKeyboardEvent,false);
    stage.addEventListener('keyup',guardKeyboardEvent,false);
    stage.addEventListener('keypress',guardKeyboardEvent,false);
    return true;
  }

  function init(){
    var tries=0;
    (function wait(){
      tries+=1;
      if(bind())return;
      if(tries<160)setTimeout(wait,50);
    })();
  }

  window.PokerolEditorInputGuardV01=Object.freeze({BUILD:BUILD});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
