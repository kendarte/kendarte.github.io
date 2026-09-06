(function(){
  'use strict';

  var BUILD='0.1.0-visual-recovery';
  var visualDbPromise=null;
  var bgObjectUrl='';
  var scheduled=0;
  var lastRoomSignature='';

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}

  function rememberTrainer(name){
    name=clean(name).replace(/[.]+$/,'');
    if(!name)return;
    try{localStorage.setItem('pokerol.last_user',name)}catch(e){}
    if(window.PokerolTrainerSpriteEditorV01&&typeof PokerolTrainerSpriteEditorV01.applyStoredSprite==='function'){
      try{PokerolTrainerSpriteEditorV01.applyStoredSprite()}catch(e){}
    }
  }

  function scanTrainerSignals(){
    var feed=byId('messagewindow');if(!feed)return;
    var nodes=feed.querySelectorAll('.pkAuthBridgeSignal,.pkFeedLine');
    for(var i=Math.max(0,nodes.length-12);i<nodes.length;i++){
      var text=clean(nodes[i]&&nodes[i].textContent);
      var match=text.match(/you become\s+([^\.\n]+)/i);
      if(match&&match[1]){rememberTrainer(match[1]);return}
    }
  }

  function openVisualDb(){
    if(visualDbPromise)return visualDbPromise;
    visualDbPromise=new Promise(function(resolve,reject){
      if(!window.indexedDB){reject(new Error('IndexedDB no disponible'));return}
      var req=indexedDB.open('pokerol_visuals_v1',1);
      req.onupgradeneeded=function(ev){
        var db=ev.target.result;
        if(!db.objectStoreNames.contains('room_backgrounds'))db.createObjectStore('room_backgrounds',{keyPath:'roomKey'});
      };
      req.onsuccess=function(){resolve(req.result)};
      req.onerror=function(){reject(req.error||new Error('No se pudo abrir pokerol_visuals_v1'))};
    });
    return visualDbPromise;
  }

  function getRecord(key){
    if(!key)return Promise.resolve(null);
    return openVisualDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction('room_backgrounds','readonly');
      var req=tx.objectStore('room_backgrounds').get(key);
      req.onsuccess=function(){resolve(req.result||null)};
      req.onerror=function(){reject(req.error)};
    })});
  }

  function putAlias(key,record){
    if(!key||!record||!record.blob)return Promise.resolve(false);
    return openVisualDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction('room_backgrounds','readwrite');
      tx.objectStore('room_backgrounds').put({
        roomKey:key,
        blob:record.blob,
        name:record.name||'background',
        type:record.type||'',
        updatedAt:record.updatedAt||Date.now(),
        recoveredFrom:record.roomKey||''
      });
      tx.oncomplete=function(){resolve(true)};
      tx.onerror=function(){reject(tx.error)};
    })});
  }

  function roomKeys(){
    var id=clean(byId('pk-room-id')&&byId('pk-room-id').textContent);
    var name=clean(byId('pk-room-name')&&byId('pk-room-name').textContent);
    var keys=[];
    if(id)keys.push(id);
    if(name){
      keys.push('ROOMNAME:'+name.toLowerCase());
      keys.push(name);
      keys.push(name.toLowerCase());
    }
    return {id:id,name:name,keys:keys.filter(function(v,i,a){return v&&a.indexOf(v)===i})};
  }

  function releaseBgUrl(){
    if(bgObjectUrl){try{URL.revokeObjectURL(bgObjectUrl)}catch(e){}bgObjectUrl=''}
  }

  function applyRecord(record){
    var bg=byId('pk-stage-bg');if(!bg||!record||!record.blob)return false;
    releaseBgUrl();
    bgObjectUrl=URL.createObjectURL(record.blob);
    bg.style.backgroundImage='url("'+bgObjectUrl+'")';
    var status=byId('pk-bg-status');
    if(status){status.textContent='LOCAL · '+clean(record.name||'BACKGROUND');status.classList.add('pkVisible')}
    return true;
  }

  function clearMalformedServerBackground(){
    var bg=byId('pk-stage-bg');if(!bg)return;
    var value=clean(bg.style.backgroundImage);
    if(/\{'src'|%7B['\"]?src|\[object Object\]/i.test(value)){
      bg.style.backgroundImage='';
      var status=byId('pk-bg-status');if(status&&/WORLD BACKGROUND/i.test(status.textContent||'')){status.textContent='';status.classList.remove('pkVisible')}
    }
  }

  function recoverRoomBackground(){
    var info=roomKeys();
    var signature=info.id+'|'+info.name;
    if(!info.id&&!info.name)return;
    clearMalformedServerBackground();
    var index=0;
    function next(){
      if(index>=info.keys.length)return Promise.resolve(null);
      var key=info.keys[index++];
      return getRecord(key).then(function(record){return record||next()});
    }
    next().then(function(record){
      if(!record)return;
      var now=roomKeys();if((now.id+'|'+now.name)!==signature)return;
      applyRecord(record);
      if(info.id&&record.roomKey!==info.id)putAlias(info.id,record).catch(function(){});
    }).catch(function(){});
  }

  function scheduleRecovery(delay){
    clearTimeout(scheduled);
    scheduled=setTimeout(function(){scanTrainerSignals();recoverRoomBackground()},delay==null?40:delay);
  }

  function init(){
    var root=document.documentElement;
    var observer=new MutationObserver(function(records){
      var relevant=false;
      for(var i=0;i<records.length;i++){
        var target=records[i].target;
        if(target===byId('pk-room-name')||target===byId('pk-room-id')||target===byId('messagewindow')||(target&&target.closest&&target.closest('#messagewindow'))){relevant=true;break}
      }
      if(relevant)scheduleRecovery(60);
    });
    observer.observe(root,{childList:true,subtree:true,characterData:true});
    [100,350,900,1800].forEach(function(ms){setTimeout(function(){scheduleRecovery(0)},ms)});
  }

  window.PokerolVisualRecoveryV01=Object.freeze({BUILD:BUILD,recover:recoverRoomBackground,rememberTrainer:rememberTrainer});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
