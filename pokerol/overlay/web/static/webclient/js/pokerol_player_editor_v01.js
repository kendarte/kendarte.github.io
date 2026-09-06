(function(){
  'use strict';

  var DB_NAME='pokerol_player_editor_v1';
  var STORE='room_player_layout';
  var editing=false;
  var drag=null;
  var resize=null;
  var current={x:11,y:94,scale:1};
  var roomObserver=null;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function roomKey(){return clean((byId('pk-room-id')&&byId('pk-room-id').textContent)||'')||clean((byId('pk-room-name')&&byId('pk-room-name').textContent)||'UNASSIGNED')}
  function clamp(v,min,max){return Math.max(min,Math.min(max,Number(v)||0))}

  function openDb(){
    return new Promise(function(resolve,reject){
      var req=indexedDB.open(DB_NAME,1);
      req.onupgradeneeded=function(e){var db=e.target.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:'roomKey'})};
      req.onsuccess=function(){resolve(req.result)};req.onerror=function(){reject(req.error)};
    });
  }
  function loadLayout(key){
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var req=db.transaction(STORE,'readonly').objectStore(STORE).get(key);
      req.onsuccess=function(){resolve(req.result||null)};req.onerror=function(){reject(req.error)};
    })});
  }
  function saveLayout(){
    var row={roomKey:roomKey(),x:current.x,y:current.y,scale:current.scale,updatedAt:Date.now()};
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(row);tx.oncomplete=function(){resolve(true)};tx.onerror=function(){reject(tx.error)};
    })});
  }
  function deleteLayout(){
    var key=roomKey();return openDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).delete(key);tx.oncomplete=function(){resolve(true)};tx.onerror=function(){reject(tx.error)};
    })});
  }

  function apply(){
    var avatar=byId('pk-player-avatar');if(!avatar)return;
    avatar.style.left=current.x+'%';
    avatar.style.bottom=current.y+'px';
    avatar.style.setProperty('--pk-player-edit-scale',String(current.scale));
    avatar.style.transform='translateX(-50%) scale('+current.scale+')';
    avatar.style.transformOrigin='bottom center';
    var x=byId('pk-player-x'),y=byId('pk-player-y'),s=byId('pk-player-scale');
    if(x)x.value=current.x.toFixed(1);if(y)y.value=current.y.toFixed(0);if(s)s.value=current.scale.toFixed(2);
  }
  function loadForRoom(){
    loadLayout(roomKey()).then(function(row){
      if(row){current={x:clamp(row.x,0,100),y:clamp(row.y,0,500),scale:clamp(row.scale,.35,3)}}
      else{current={x:11,y:94,scale:1}}
      apply();
    }).catch(function(){current={x:11,y:94,scale:1};apply()});
  }

  function setEditing(on){
    editing=!!on;
    var stage=byId('pk-stage'),avatar=byId('pk-player-avatar'),panel=byId('pk-player-panel'),btn=byId('pk-edit-player');
    if(stage)stage.classList.toggle('pkPlayerEditing',editing);
    if(avatar)avatar.classList.toggle('pkPlayerEditable',editing);
    if(panel)panel.hidden=!editing;
    if(btn)btn.classList.toggle('pkActive',editing);
    if(editing){ensureHandle();apply()}else{drag=null;resize=null}
  }
  function toggle(){setEditing(!editing)}
  function ensureHandle(){
    var avatar=byId('pk-player-avatar');if(!avatar||byId('pk-player-resize-handle'))return;
    var h=document.createElement('span');h.id='pk-player-resize-handle';h.className='pkPlayerResizeHandle';h.title='Arrastra para cambiar tamaño';avatar.appendChild(h);
  }

  function bindAvatar(){
    var avatar=byId('pk-player-avatar'),stage=byId('pk-stage');if(!avatar||!stage||avatar.dataset.pkPlayerEditBound==='1')return false;
    avatar.dataset.pkPlayerEditBound='1';ensureHandle();
    avatar.addEventListener('pointerdown',function(ev){
      if(!editing||ev.target===byId('pk-player-resize-handle'))return;
      ev.preventDefault();ev.stopPropagation();
      var r=stage.getBoundingClientRect();drag={id:ev.pointerId,rect:r};avatar.setPointerCapture&&avatar.setPointerCapture(ev.pointerId);
    },true);
    avatar.addEventListener('pointermove',function(ev){
      if(!editing||!drag||drag.id!==ev.pointerId)return;
      var r=drag.rect;current.x=clamp(((ev.clientX-r.left)/r.width)*100,1,99);current.y=clamp(r.bottom-ev.clientY,0,Math.max(100,r.height-20));apply();
    },true);
    avatar.addEventListener('pointerup',function(ev){if(drag&&drag.id===ev.pointerId){drag=null;saveLayout()}},true);

    var h=byId('pk-player-resize-handle');if(h&&h.dataset.pkBound!=='1'){
      h.dataset.pkBound='1';
      h.addEventListener('pointerdown',function(ev){if(!editing)return;ev.preventDefault();ev.stopPropagation();resize={id:ev.pointerId,startY:ev.clientY,startScale:current.scale};h.setPointerCapture&&h.setPointerCapture(ev.pointerId)},true);
      h.addEventListener('pointermove',function(ev){if(!editing||!resize||resize.id!==ev.pointerId)return;ev.preventDefault();current.scale=clamp(resize.startScale+((resize.startY-ev.clientY)/120),.35,3);apply()},true);
      h.addEventListener('pointerup',function(ev){if(resize&&resize.id===ev.pointerId){resize=null;saveLayout()}},true);
    }
    return true;
  }

  function bindPanel(){
    var btn=byId('pk-edit-player'),close=byId('pk-player-close'),save=byId('pk-player-save'),reset=byId('pk-player-reset');
    if(btn&&btn.dataset.pkBound!=='1'){btn.dataset.pkBound='1';btn.addEventListener('click',function(){setEditing(true)})}
    if(close)close.addEventListener('click',function(){setEditing(false)});
    if(save)save.addEventListener('click',function(){readFields();saveLayout()});
    if(reset)reset.addEventListener('click',function(){deleteLayout().then(function(){current={x:11,y:94,scale:1};apply()})});
    ['pk-player-x','pk-player-y','pk-player-scale'].forEach(function(id){var n=byId(id);if(n)n.addEventListener('change',function(){readFields();apply();saveLayout()})});
  }
  function readFields(){
    var x=parseFloat(byId('pk-player-x')&&byId('pk-player-x').value),y=parseFloat(byId('pk-player-y')&&byId('pk-player-y').value),s=parseFloat(byId('pk-player-scale')&&byId('pk-player-scale').value);
    if(Number.isFinite(x))current.x=clamp(x,1,99);if(Number.isFinite(y))current.y=clamp(y,0,500);if(Number.isFinite(s))current.scale=clamp(s,.35,3);
  }

  function watchRoom(){
    var rid=byId('pk-room-id'),name=byId('pk-room-name');if(!rid&&!name)return;
    roomObserver=new MutationObserver(function(){setTimeout(loadForRoom,20)});
    if(rid)roomObserver.observe(rid,{childList:true,subtree:true,characterData:true});if(name)roomObserver.observe(name,{childList:true,subtree:true,characterData:true});
  }
  function init(){
    var tries=0;(function wait(){tries++;if(byId('pk-player-avatar')&&byId('pk-edit-player')){bindAvatar();bindPanel();watchRoom();loadForRoom();return}if(tries<120)setTimeout(wait,50)})();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();