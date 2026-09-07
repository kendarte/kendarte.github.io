(function(){
  'use strict';

  var BUILD='0.4.0-hotspot-size-delete';
  var editing=false;
  var selected=null;
  var drag=null;
  var observer=null;
  var applying=false;
  var roomCache={};
  var emitterBound=false;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function roomKey(){return clean((byId('pk-room-id')&&byId('pk-room-id').textContent)||'')||clean((byId('pk-room-name')&&byId('pk-room-name').textContent)||'UNASSIGNED')}
  function uid(){return 'HS-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7)}
  function clamp(v,min,max){var n=Number(v);if(!Number.isFinite(n))n=min;return Math.max(min,Math.min(max,n))}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
  function sendSave(data){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',['pokerol-editor-save-hotspots '+encodePayload({custom:data.custom||[],actions:data.actions||{}})],{});return true}catch(e){return false}
  }
  function sendGeometry(data){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',['pokerol-editor-hotspot-geometry '+encodePayload({geometry:data.geometry||{}})],{});return true}catch(e){return false}
  }

  function currentData(){var key=roomKey();if(!roomCache[key])roomCache[key]={roomKey:key,custom:[],actions:{},geometry:{}};return roomCache[key]}
  function setServerRows(packet){
    var key=clean(packet.room_id)||clean(packet.room_name||packet.location)||roomKey();
    var actionLayouts=packet.action_hotspot_layouts&&typeof packet.action_hotspot_layouts==='object'?packet.action_hotspot_layouts:{};
    var geometry=packet.hotspot_geometry&&typeof packet.hotspot_geometry==='object'?packet.hotspot_geometry:{};
    roomCache[key]={roomKey:key,custom:(packet.custom_hotspots||[]).map(function(r){return Object.assign({},r)}),actions:Object.assign({},actionLayouts),geometry:Object.assign({},geometry)};
    var current=roomKey();if(current===key||!roomCache[current])roomCache[current]=roomCache[key];
  }
  function saveRoom(data){roomCache[data.roomKey]=data;sendSave(data);sendGeometry(data);return Promise.resolve(true)}

  function labelNode(actor){return actor&&actor.querySelector('.pkActorLabel')}
  function originalKey(actor){
    if(!actor)return '';
    if(actor.dataset.pkHotspotKey)return actor.dataset.pkHotspotKey;
    var label=clean(labelNode(actor)&&labelNode(actor).textContent)||'HOTSPOT';
    actor.dataset.pkHotspotKey='WORLD:'+label.toLowerCase();
    return actor.dataset.pkHotspotKey;
  }
  function safeActionKey(actor){return String(originalKey(actor)||'').replace(/[^A-Za-z0-9_.:-]+/g,'_').slice(0,96)}
  function geometryKey(actor){return safeActionKey(actor)}
  function defaultDimension(actor,axis){
    if(!actor)return 80;
    var rect=actor.getBoundingClientRect();
    var value=axis==='height'?rect.height:rect.width;
    if(!Number.isFinite(value)||value<12)value=80;
    return clamp(Math.round(value),12,axis==='height'?500:600);
  }
  function geometryRow(actor,data,create){
    var key=geometryKey(actor);if(!key)return null;
    data.geometry=data.geometry||{};
    var row=data.geometry[key];
    if(!row&&create){row={width:defaultDimension(actor,'width'),height:defaultDimension(actor,'height'),hidden:false};data.geometry[key]=row}
    return row||null;
  }
  function applyGeometry(actor,data){
    if(!actor)return;
    var row=geometryRow(actor,data,false);
    if(!row){actor.classList.remove('pkHotspotSized','pkHotspotDeleted');actor.style.removeProperty('--pk-hotspot-width');actor.style.removeProperty('--pk-hotspot-height');return}
    var width=clamp(row.width==null?80:row.width,12,600),height=clamp(row.height==null?80:row.height,12,500);
    actor.dataset.pkHotspotWidth=String(width);actor.dataset.pkHotspotHeight=String(height);
    actor.style.setProperty('--pk-hotspot-width',width+'px');actor.style.setProperty('--pk-hotspot-height',height+'px');
    actor.classList.add('pkHotspotSized');actor.classList.toggle('pkHotspotDeleted',!!row.hidden);
  }
  function normalizeActor(actor){
    if(!actor)return;originalKey(actor);
    if(actor.dataset.pkHotspotBound==='1')return;
    actor.dataset.pkHotspotBound='1';
    actor.addEventListener('pointerdown',function(ev){
      if(!editing)return;ev.preventDefault();ev.stopPropagation();selectActor(actor);
      var layer=byId('pk-actor-layer');if(!layer)return;
      actor.setPointerCapture&&actor.setPointerCapture(ev.pointerId);
      drag={actor:actor,rect:layer.getBoundingClientRect(),pointerId:ev.pointerId};
    },true);
    actor.addEventListener('pointermove',function(ev){
      if(!editing||!drag||drag.actor!==actor)return;ev.preventDefault();
      var r=drag.rect,x=Math.max(2,Math.min(98,((ev.clientX-r.left)/r.width)*100)),y=Math.max(0,Math.min(92,((r.bottom-ev.clientY)/r.height)*100));
      actor.style.left=x.toFixed(2)+'%';actor.style.bottom=y.toFixed(2)+'%';updatePositionFields(x,y);
    },true);
    actor.addEventListener('pointerup',function(){if(drag&&drag.actor===actor){drag=null;persistSelected()}},true);
    actor.addEventListener('click',function(ev){if(editing){ev.preventDefault();ev.stopImmediatePropagation();selectActor(actor)}},true);
  }
  function actorSnapshot(actor){
    var data=currentData(),geo=geometryRow(actor,data,false),rect=actor&&actor.getBoundingClientRect?actor.getBoundingClientRect():{width:80,height:80};
    return {
      name:clean(labelNode(actor)&&labelNode(actor).textContent)||'Hotspot',
      x:parseFloat(actor.style.left)||50,
      y:parseFloat(actor.style.bottom)||2,
      width:clamp(geo&&geo.width!=null?geo.width:rect.width||80,12,600),
      height:clamp(geo&&geo.height!=null?geo.height:rect.height||80,12,500)
    };
  }
  function setActorSprite(actor,src){
    var img=actor.querySelector('.pkActorSprite'),ph=actor.querySelector('.pkActorPlaceholder');
    if(src){if(!img){img=document.createElement('img');img.className='pkActorSprite';actor.insertBefore(img,actor.firstChild)}img.src=src;if(ph)ph.style.display='none'}
    else{if(img)img.remove();if(ph)ph.style.display=''}
  }
  function makeCustom(row){
    var layer=byId('pk-actor-layer');if(!layer)return null;
    var actor=document.createElement('button');actor.type='button';actor.className='pkActor pkCustomHotspot';actor.dataset.kind='CUSTOM';actor.dataset.pkHotspotKey=row.id;actor.dataset.pkCustom='1';
    actor.dataset.pkCommand=clean(row.command);actor.dataset.pkCustomDescription=String(row.description||'');actor.dataset.pkWorldScale=String(row.scale==null?1:row.scale);actor.dataset.pkCustomSprite=String(row.sprite||'');
    actor.style.left=(row.x==null?50:row.x)+'%';actor.style.bottom=(row.y==null?20:row.y)+'%';actor.style.setProperty('--pk-world-actor-scale',String(row.scale==null?1:row.scale));
    var dot=document.createElement('span');dot.className='pkActorPlaceholder';actor.appendChild(dot);if(row.sprite)setActorSprite(actor,row.sprite);
    var label=document.createElement('span');label.className='pkActorLabel';label.textContent=row.name||'NUEVO HOTSPOT';actor.appendChild(label);
    actor.addEventListener('click',function(){if(editing)return;var cmd=clean(actor.dataset.pkCommand)||('observar '+clean(label.textContent||'hotspot'));var field=byId('inputfield'),send=byId('inputsend');if(field&&send){field.value=cmd;field.dispatchEvent(new Event('input',{bubbles:true}));send.click()}});
    layer.appendChild(actor);normalizeActor(actor);applyGeometry(actor,currentData());return actor;
  }
  function applyActionLayout(actor,data){
    if(!actor||!actor.classList.contains('pkActionHotspot'))return;
    var row=(data.actions||{})[safeActionKey(actor)];if(!row)return;
    if(Number.isFinite(Number(row.x)))actor.style.left=clamp(row.x,2,98)+'%';
    if(Number.isFinite(Number(row.y)))actor.style.bottom=clamp(row.y,0,92)+'%';
    var scale=clamp(row.scale==null?1:row.scale,.2,4);actor.dataset.pkWorldScale=String(scale);actor.style.setProperty('--pk-world-actor-scale',String(scale));
  }

  function applyRoomLayout(){
    if(applying)return;var layer=byId('pk-actor-layer');if(!layer)return;applying=true;var data=currentData();
    Array.from(layer.querySelectorAll('.pkActor:not(.pkCustomHotspot)')).forEach(function(actor){normalizeActor(actor);applyActionLayout(actor,data);applyGeometry(actor,data)});
    Array.from(layer.querySelectorAll('.pkCustomHotspot')).forEach(function(n){n.remove()});
    (data.custom||[]).forEach(makeCustom);
    if(editing)setEditingVisuals(true);applying=false;
  }
  function panel(){return byId('pk-hotspot-panel')}
  function setEditingVisuals(on){var stage=byId('pk-stage');if(stage)stage.classList.toggle('pkHotspotEditing',on);var btn=byId('pk-edit-hotspots');if(btn){btn.classList.toggle('pkActive',on);btn.textContent=on?'LISTO':'HOTSPOTS'}var p=panel();if(p)p.hidden=!on}
  function toggleEditing(){editing=!editing;selected=null;setEditingVisuals(editing);applyRoomLayout();if(!editing)clearSelection()}
  function clearSelection(){Array.from(document.querySelectorAll('.pkActor.pkSelectedHotspot')).forEach(function(a){a.classList.remove('pkSelectedHotspot')});selected=null;fillForm(null)}
  function selectActor(actor){clearSelection();selected=actor;actor.classList.add('pkSelectedHotspot');fillForm(actor);setTimeout(function(){if(actor.dataset.pkCustom==='1'){var d=byId('pk-hotspot-description'),s=byId('pk-hotspot-scale');if(d)d.value=actor.dataset.pkCustomDescription||'';if(s)s.value=clamp(actor.dataset.pkWorldScale||1,.2,4).toFixed(2)}else if(actor.classList.contains('pkActionHotspot')){var sc=byId('pk-hotspot-scale');if(sc)sc.value=clamp(actor.dataset.pkWorldScale||1,.2,4).toFixed(2)}},0)}
  function fillForm(actor){
    var name=byId('pk-hotspot-name'),cmd=byId('pk-hotspot-command'),x=byId('pk-hotspot-x'),y=byId('pk-hotspot-y'),w=byId('pk-hotspot-width'),h=byId('pk-hotspot-height'),del=byId('pk-hotspot-delete'),hide=byId('pk-hotspot-hide');
    if(!actor){if(name)name.value='';if(cmd)cmd.value='';if(x)x.value='';if(y)y.value='';if(w)w.value='';if(h)h.value='';if(del)del.disabled=true;if(hide)hide.disabled=true;return}
    var snap=actorSnapshot(actor);if(name)name.value=snap.name;if(x)x.value=snap.x.toFixed(1);if(y)y.value=snap.y.toFixed(1);if(w)w.value=Math.round(snap.width);if(h)h.value=Math.round(snap.height);
    if(cmd){cmd.disabled=actor.dataset.pkCustom!=='1';cmd.value=actor.dataset.pkCommand||''}if(del)del.disabled=false;if(hide)hide.disabled=true;
  }
  function updatePositionFields(x,y){var fx=byId('pk-hotspot-x'),fy=byId('pk-hotspot-y');if(fx)fx.value=Number(x).toFixed(1);if(fy)fy.value=Number(y).toFixed(1)}
  function updateGeometryFromForm(actor,data){
    if(!actor)return null;
    var row=geometryRow(actor,data,true),w=byId('pk-hotspot-width'),h=byId('pk-hotspot-height');
    row.width=clamp(w&&w.value!==''?w.value:row.width,12,600);row.height=clamp(h&&h.value!==''?h.value:row.height,12,500);row.hidden=false;
    applyGeometry(actor,data);return row;
  }

  function persistSelected(){
    if(!selected)return Promise.resolve(false);
    var data=currentData();updateGeometryFromForm(selected,data);
    if(selected.dataset.pkCustom==='1'){
      var id=originalKey(selected),name=clean(byId('pk-hotspot-name')&&byId('pk-hotspot-name').value)||'Hotspot';
      var row=(data.custom||[]).find(function(r){return r.id===id});if(!row){row={id:id};data.custom.push(row)}
      row.name=name;row.command=clean(byId('pk-hotspot-command')&&byId('pk-hotspot-command').value)||('observar '+name);row.x=parseFloat(selected.style.left)||50;row.y=parseFloat(selected.style.bottom)||2;
      row.description=String((byId('pk-hotspot-description')&&byId('pk-hotspot-description').value)||selected.dataset.pkCustomDescription||'').trim();
      row.scale=clamp((byId('pk-hotspot-scale')&&byId('pk-hotspot-scale').value)||selected.dataset.pkWorldScale||1,.2,4);
      row.sprite=String(selected.dataset.pkCustomSprite||selected.dataset.pkProjectSprite||row.sprite||'');
      selected.dataset.pkCommand=row.command;selected.dataset.pkCustomDescription=row.description;selected.dataset.pkWorldScale=String(row.scale);selected.style.setProperty('--pk-world-actor-scale',String(row.scale));
      var lbl=labelNode(selected);if(lbl)lbl.textContent=name;
      return saveRoom(data);
    }
    if(selected.classList.contains('pkActionHotspot')){
      var actionKey=safeActionKey(selected);if(!actionKey)return Promise.resolve(false);
      var scale=clamp((byId('pk-hotspot-scale')&&byId('pk-hotspot-scale').value)||selected.dataset.pkWorldScale||1,.2,4);
      data.actions=data.actions||{};data.actions[actionKey]={x:parseFloat(selected.style.left)||50,y:parseFloat(selected.style.bottom)||2,scale:scale};
      selected.dataset.pkWorldScale=String(scale);selected.style.setProperty('--pk-world-actor-scale',String(scale));
    }
    return saveRoom(data);
  }
  function createNew(){
    var data=currentData(),row={id:uid(),name:'NUEVO HOTSPOT',command:'observar hotspot',x:50,y:24,description:'',scale:1,sprite:''};data.custom.push(row);data.geometry=data.geometry||{};data.geometry[row.id]={width:80,height:80,hidden:false};saveRoom(data).then(function(){var a=makeCustom(row);if(a)selectActor(a)})
  }
  function deleteSelected(){
    if(!selected)return;var node=selected,data=currentData(),key=geometryKey(selected);if(!key)return;
    if(selected.dataset.pkCustom==='1'){
      var id=originalKey(selected);data.custom=(data.custom||[]).filter(function(r){return r.id!==id});if(data.geometry)delete data.geometry[key];
      saveRoom(data).then(function(){node.remove();clearSelection()});return;
    }
    data.geometry=data.geometry||{};var row=geometryRow(selected,data,true);row.hidden=true;
    saveRoom(data).then(function(){node.classList.add('pkHotspotDeleted');clearSelection()});
  }

  function bindPanel(){
    var edit=byId('pk-edit-hotspots'),add=byId('pk-hotspot-new'),save=byId('pk-hotspot-save'),del=byId('pk-hotspot-delete');
    if(edit)edit.addEventListener('click',toggleEditing);if(add)add.addEventListener('click',createNew);if(save)save.addEventListener('click',function(){setTimeout(persistSelected,0)});if(del)del.addEventListener('click',deleteSelected);
    ['pk-hotspot-name','pk-hotspot-command','pk-hotspot-description','pk-hotspot-scale','pk-hotspot-width','pk-hotspot-height'].forEach(function(id){var n=byId(id);if(n)n.addEventListener('change',persistSelected)});
    ['pk-hotspot-x','pk-hotspot-y'].forEach(function(id){var n=byId(id);if(n)n.addEventListener('change',function(){if(!selected)return;var x=parseFloat(byId('pk-hotspot-x').value),y=parseFloat(byId('pk-hotspot-y').value);if(Number.isFinite(x))selected.style.left=Math.max(2,Math.min(98,x))+'%';if(Number.isFinite(y))selected.style.bottom=Math.max(0,Math.min(92,y))+'%';persistSelected()})});
  }
  function onSnapshot(args){var packet=packetFrom(args);setServerRows(packet);setTimeout(applyRoomLayout,20);return true}
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true;return true}
  function watchActors(){var layer=byId('pk-actor-layer');if(!layer)return false;observer=new MutationObserver(function(){if(!applying)setTimeout(applyRoomLayout,0)});observer.observe(layer,{childList:true,subtree:true});return true}
  function init(){bindPanel();var tries=0;(function wait(){tries++;bindEmitter();if(watchActors())return;if(tries<120)setTimeout(wait,75)})();}

  window.PokerolHotspotEditorV01=Object.freeze({BUILD:BUILD,persistSelected:persistSelected,applyRoomLayout:applyRoomLayout});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
