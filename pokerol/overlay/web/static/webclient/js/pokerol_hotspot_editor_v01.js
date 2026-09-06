(function(){
  'use strict';

  var DB_NAME='pokerol_hotspot_editor_v1';
  var STORE='room_hotspots';
  var editing=false;
  var selected=null;
  var drag=null;
  var observer=null;
  var applying=false;
  var roomCache={};

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function roomKey(){return clean((byId('pk-room-id')&&byId('pk-room-id').textContent)||'')||clean((byId('pk-room-name')&&byId('pk-room-name').textContent)||'UNASSIGNED')}
  function uid(){return 'HS-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7)}

  function openDb(){
    return new Promise(function(resolve,reject){
      var req=indexedDB.open(DB_NAME,1);
      req.onupgradeneeded=function(e){var db=e.target.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:'roomKey'})};
      req.onsuccess=function(){resolve(req.result)};
      req.onerror=function(){reject(req.error)};
    });
  }
  function loadRoom(key){
    if(roomCache[key])return Promise.resolve(roomCache[key]);
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction(STORE,'readonly');var req=tx.objectStore(STORE).get(key);
      req.onsuccess=function(){var data=req.result||{roomKey:key,overrides:{},custom:[]};roomCache[key]=data;resolve(data)};
      req.onerror=function(){reject(req.error)};
    })});
  }
  function saveRoom(data){
    roomCache[data.roomKey]=data;
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(data);tx.oncomplete=function(){resolve(true)};tx.onerror=function(){reject(tx.error)};
    })});
  }

  function labelNode(actor){return actor&&actor.querySelector('.pkActorLabel')}
  function originalKey(actor){
    if(!actor)return '';
    if(actor.dataset.pkHotspotKey)return actor.dataset.pkHotspotKey;
    var label=clean(labelNode(actor)&&labelNode(actor).textContent)||'HOTSPOT';
    actor.dataset.pkHotspotKey='WORLD:'+label.toLowerCase();
    return actor.dataset.pkHotspotKey;
  }
  function normalizeActor(actor){
    if(!actor)return;
    originalKey(actor);
    if(actor.dataset.pkHotspotBound==='1')return;
    actor.dataset.pkHotspotBound='1';
    actor.addEventListener('pointerdown',function(ev){
      if(!editing)return;
      ev.preventDefault();ev.stopPropagation();selectActor(actor);
      var layer=byId('pk-actor-layer');if(!layer)return;
      actor.setPointerCapture&&actor.setPointerCapture(ev.pointerId);
      drag={actor:actor,rect:layer.getBoundingClientRect(),pointerId:ev.pointerId};
    },true);
    actor.addEventListener('pointermove',function(ev){
      if(!editing||!drag||drag.actor!==actor)return;
      ev.preventDefault();
      var r=drag.rect;
      var x=Math.max(2,Math.min(98,((ev.clientX-r.left)/r.width)*100));
      var y=Math.max(0,Math.min(92,((r.bottom-ev.clientY)/r.height)*100));
      actor.style.left=x.toFixed(2)+'%';actor.style.bottom=y.toFixed(2)+'%';
      updatePositionFields(x,y);
    },true);
    actor.addEventListener('pointerup',function(ev){if(drag&&drag.actor===actor){drag=null;persistSelected()}},true);
    actor.addEventListener('click',function(ev){if(editing){ev.preventDefault();ev.stopImmediatePropagation();selectActor(actor)}},true);
  }

  function actorSnapshot(actor){
    var left=parseFloat(actor.style.left)||50,bottom=parseFloat(actor.style.bottom)||2;
    return {name:clean(labelNode(actor)&&labelNode(actor).textContent)||'Hotspot',x:left,y:bottom,hidden:actor.classList.contains('pkHotspotHidden')};
  }
  function applyOverride(actor,ov){
    if(!actor||!ov)return;
    var label=labelNode(actor);if(label&&ov.name)label.textContent=ov.name;
    if(Number.isFinite(Number(ov.x)))actor.style.left=Number(ov.x)+'%';
    if(Number.isFinite(Number(ov.y)))actor.style.bottom=Number(ov.y)+'%';
    actor.classList.toggle('pkHotspotHidden',!!ov.hidden);
  }
  function makeCustom(row){
    var layer=byId('pk-actor-layer');if(!layer)return null;
    var actor=document.createElement('button');actor.type='button';actor.className='pkActor pkCustomHotspot';actor.dataset.kind='CUSTOM';actor.dataset.pkHotspotKey=row.id;actor.dataset.pkCustom='1';
    actor.style.left=(row.x==null?50:row.x)+'%';actor.style.bottom=(row.y==null?20:row.y)+'%';
    var dot=document.createElement('span');dot.className='pkActorPlaceholder';actor.appendChild(dot);
    var label=document.createElement('span');label.className='pkActorLabel';label.textContent=row.name||'NUEVO HOTSPOT';actor.appendChild(label);
    actor.addEventListener('click',function(ev){
      if(editing)return;
      var cmd=clean(row.command)||('observar '+clean(row.name||'hotspot'));
      var field=byId('inputfield'),send=byId('inputsend');if(field&&send){field.value=cmd;field.dispatchEvent(new Event('input',{bubbles:true}));send.click()}
    });
    layer.appendChild(actor);normalizeActor(actor);return actor;
  }

  function applyRoomLayout(){
    if(applying)return;var layer=byId('pk-actor-layer');if(!layer)return;
    applying=true;
    var key=roomKey();
    loadRoom(key).then(function(data){
      Array.from(layer.querySelectorAll('.pkActor:not(.pkCustomHotspot)')).forEach(function(actor){normalizeActor(actor);applyOverride(actor,data.overrides[originalKey(actor)])});
      Array.from(layer.querySelectorAll('.pkCustomHotspot')).forEach(function(n){n.remove()});
      (data.custom||[]).forEach(makeCustom);
      if(editing)setEditingVisuals(true);
    }).finally(function(){applying=false});
  }

  function panel(){return byId('pk-hotspot-panel')}
  function setEditingVisuals(on){
    var stage=byId('pk-stage');if(stage)stage.classList.toggle('pkHotspotEditing',on);
    var btn=byId('pk-edit-hotspots');if(btn){btn.classList.toggle('pkActive',on);btn.textContent=on?'LISTO':'HOTSPOTS'}
    var p=panel();if(p)p.hidden=!on;
  }
  function toggleEditing(){editing=!editing;selected=null;setEditingVisuals(editing);applyRoomLayout();if(!editing)clearSelection()}
  function clearSelection(){Array.from(document.querySelectorAll('.pkActor.pkSelectedHotspot')).forEach(function(a){a.classList.remove('pkSelectedHotspot')});selected=null;fillForm(null)}
  function selectActor(actor){
    clearSelection();selected=actor;actor.classList.add('pkSelectedHotspot');fillForm(actor);
  }
  function fillForm(actor){
    var name=byId('pk-hotspot-name'),cmd=byId('pk-hotspot-command'),x=byId('pk-hotspot-x'),y=byId('pk-hotspot-y'),del=byId('pk-hotspot-delete'),hide=byId('pk-hotspot-hide');
    if(!actor){if(name)name.value='';if(cmd)cmd.value='';if(x)x.value='';if(y)y.value='';if(del)del.disabled=true;if(hide)hide.disabled=true;return}
    var snap=actorSnapshot(actor);if(name)name.value=snap.name;if(x)x.value=snap.x.toFixed(1);if(y)y.value=snap.y.toFixed(1);
    if(cmd){cmd.disabled=actor.dataset.pkCustom!=='1';cmd.value=actor.dataset.pkCommand||''}
    if(del)del.disabled=actor.dataset.pkCustom!=='1';if(hide){hide.disabled=actor.dataset.pkCustom==='1';hide.textContent=actor.classList.contains('pkHotspotHidden')?'MOSTRAR':'OCULTAR'}
  }
  function updatePositionFields(x,y){var fx=byId('pk-hotspot-x'),fy=byId('pk-hotspot-y');if(fx)fx.value=Number(x).toFixed(1);if(fy)fy.value=Number(y).toFixed(1)}

  function persistSelected(){
    if(!selected)return Promise.resolve(false);
    var key=roomKey(),hotKey=originalKey(selected),name=clean(byId('pk-hotspot-name')&&byId('pk-hotspot-name').value)||'Hotspot';
    var x=parseFloat(selected.style.left)||50,y=parseFloat(selected.style.bottom)||2;
    var lbl=labelNode(selected);if(lbl)lbl.textContent=name;
    return loadRoom(key).then(function(data){
      if(selected.dataset.pkCustom==='1'){
        var cmd=clean(byId('pk-hotspot-command')&&byId('pk-hotspot-command').value)||('observar '+name);selected.dataset.pkCommand=cmd;
        var row=(data.custom||[]).find(function(r){return r.id===hotKey});
        if(!row){row={id:hotKey};data.custom.push(row)}
        row.name=name;row.command=cmd;row.x=x;row.y=y;
      }else{
        data.overrides[hotKey]={name:name,x:x,y:y,hidden:selected.classList.contains('pkHotspotHidden')};
      }
      return saveRoom(data);
    });
  }
  function createNew(){
    var key=roomKey();loadRoom(key).then(function(data){
      var row={id:uid(),name:'NUEVO HOTSPOT',command:'observar hotspot',x:50,y:24};data.custom.push(row);return saveRoom(data).then(function(){var a=makeCustom(row);if(a)selectActor(a)})
    })
  }
  function deleteSelected(){
    if(!selected||selected.dataset.pkCustom!=='1')return;
    var id=originalKey(selected),node=selected,key=roomKey();loadRoom(key).then(function(data){data.custom=(data.custom||[]).filter(function(r){return r.id!==id});return saveRoom(data)}).then(function(){node.remove();clearSelection()})
  }
  function toggleHide(){
    if(!selected||selected.dataset.pkCustom==='1')return;selected.classList.toggle('pkHotspotHidden');var b=byId('pk-hotspot-hide');if(b)b.textContent=selected.classList.contains('pkHotspotHidden')?'MOSTRAR':'OCULTAR';persistSelected()
  }

  function bindPanel(){
    var edit=byId('pk-edit-hotspots'),add=byId('pk-hotspot-new'),save=byId('pk-hotspot-save'),del=byId('pk-hotspot-delete'),hide=byId('pk-hotspot-hide');
    if(edit)edit.addEventListener('click',toggleEditing);if(add)add.addEventListener('click',createNew);if(save)save.addEventListener('click',persistSelected);if(del)del.addEventListener('click',deleteSelected);if(hide)hide.addEventListener('click',toggleHide);
    ['pk-hotspot-name','pk-hotspot-command'].forEach(function(id){var n=byId(id);if(n)n.addEventListener('change',persistSelected)});
    ['pk-hotspot-x','pk-hotspot-y'].forEach(function(id){var n=byId(id);if(n)n.addEventListener('change',function(){if(!selected)return;var x=parseFloat(byId('pk-hotspot-x').value),y=parseFloat(byId('pk-hotspot-y').value);if(Number.isFinite(x))selected.style.left=Math.max(2,Math.min(98,x))+'%';if(Number.isFinite(y))selected.style.bottom=Math.max(0,Math.min(92,y))+'%';persistSelected()})});
  }

  function watchActors(){
    var layer=byId('pk-actor-layer');if(!layer)return false;
    observer=new MutationObserver(function(){if(!applying)setTimeout(applyRoomLayout,0)});observer.observe(layer,{childList:true,subtree:true});
    var rid=byId('pk-room-id'),rname=byId('pk-room-name');
    var roomObserver=new MutationObserver(function(){clearSelection();setTimeout(applyRoomLayout,20)});if(rid)roomObserver.observe(rid,{childList:true,characterData:true,subtree:true});if(rname)roomObserver.observe(rname,{childList:true,characterData:true,subtree:true});
    applyRoomLayout();return true;
  }

  function init(){bindPanel();var tries=0;(function wait(){tries++;if(watchActors())return;if(tries<100)setTimeout(wait,100)})()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
