(function(){
  'use strict';

  var BUILD='0.1.0-authoritative-scene-layouts';
  var packet=null;
  var emitterBound=false;
  var observer=null;
  var saveTimers=new WeakMap();

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function clamp(v,min,max){var n=Number(v);if(!Number.isFinite(n))n=min;return Math.max(min,Math.min(max,n))}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
  function send(command,data){if(!window.Evennia||typeof Evennia.msg!=='function')return false;try{Evennia.msg('text',[command+' '+encodePayload(data)],{});return true}catch(e){return false}}
  function label(actor){var n=actor&&actor.querySelector('.pkActorLabel');return clean(n&&n.textContent)}
  function safeKey(value){return String(value||'').replace(/[^A-Za-z0-9_.:-]+/g,'_').slice(0,96)}

  function worldRows(){
    var p=packet||{},rows=[];
    (p.visible_npcs||p.people||[]).forEach(function(r){if(r&&typeof r==='object')rows.push({kind:'NPC',row:r})});
    (p.visible_objects||p.objects||[]).forEach(function(r){if(r&&typeof r==='object')rows.push({kind:'OBJECT',row:r})});
    return rows;
  }
  function rowForActor(actor){
    if(!actor)return null;
    var dbref=Number(actor.dataset.pkWorldDbref);
    var kind=clean(actor.dataset.pkWorldKind||actor.dataset.kind).toUpperCase();
    var name=label(actor).toLowerCase();
    var rows=worldRows();
    if(Number.isFinite(dbref)){
      var byIdRow=rows.find(function(entry){return Number(entry.row.dbref)===dbref});
      if(byIdRow)return byIdRow;
    }
    return rows.find(function(entry){return (!kind||entry.kind===kind)&&clean(entry.row.name).toLowerCase()===name})||null;
  }
  function setSprite(actor,url){
    if(!actor)return;
    var img=actor.querySelector('.pkActorSprite'),ph=actor.querySelector('.pkActorPlaceholder');
    if(url){
      if(!img){img=document.createElement('img');img.className='pkActorSprite';actor.insertBefore(img,actor.firstChild)}
      if(img.getAttribute('src')!==url)img.src=url;
      img.alt=label(actor)||'Sprite';if(ph)ph.style.display='none';
    }else if(ph){ph.style.display=''}
  }
  function applyWorld(actor,entry){
    if(!actor||!entry||!entry.row)return;
    var row=entry.row;
    if(row.dbref!=null){actor.dataset.pkWorldDbref=String(row.dbref);actor.dataset.pkHotspotKey='DBREF:'+String(row.dbref)}
    actor.dataset.pkWorldKind=entry.kind;
    actor.dataset.pkWorldDescription=String(row.description||'');
    actor.dataset.pkWorldDialogue=String(row.dialogue_greeting||'');
    if(Number.isFinite(Number(row.scene_x)))actor.style.left=clamp(row.scene_x,0,100)+'%';
    if(Number.isFinite(Number(row.scene_y)))actor.style.bottom=clamp(row.scene_y,0,100)+'%';
    if(Number.isFinite(Number(row.scene_scale))){var s=clamp(row.scene_scale,.2,4);actor.dataset.pkWorldScale=String(s);actor.style.setProperty('--pk-world-actor-scale',String(s))}
    if(clean(row.scene_sprite))setSprite(actor,clean(row.scene_sprite));
  }
  function applyCustom(actor){
    if(!actor||!packet)return;
    var id=String(actor.dataset.pkHotspotKey||'');
    var row=(packet.custom_hotspots||[]).find(function(r){return r&&String(r.id||'')===id});
    if(!row)return;
    actor.style.left=clamp(row.x==null?50:row.x,0,100)+'%';
    actor.style.bottom=clamp(row.y==null?20:row.y,0,100)+'%';
    var s=clamp(row.scale==null?1:row.scale,.2,4);actor.dataset.pkWorldScale=String(s);actor.style.setProperty('--pk-world-actor-scale',String(s));
    actor.dataset.pkCustomDescription=String(row.description||'');actor.dataset.pkCommand=String(row.command||'');actor.dataset.pkCustomSprite=String(row.sprite||'');
    if(clean(row.sprite))setSprite(actor,clean(row.sprite));
  }
  function applyAction(actor){
    if(!actor||!packet)return;
    var key=safeKey(actor.dataset.pkHotspotKey||'');
    var layouts=packet.action_hotspot_layouts||{};var row=layouts[key];if(!row)return;
    actor.style.left=clamp(row.x==null?50:row.x,0,100)+'%';actor.style.bottom=clamp(row.y==null?20:row.y,0,100)+'%';
    var s=clamp(row.scale==null?1:row.scale,.2,4);actor.dataset.pkWorldScale=String(s);actor.style.setProperty('--pk-world-actor-scale',String(s));
  }
  function applyPlayer(){
    var avatar=byId('pk-player-avatar'),row=packet&&packet.player_editor;if(!avatar||!row)return;
    if(Number.isFinite(Number(row.scene_x)))avatar.style.left=clamp(row.scene_x,1,99)+'%';
    if(Number.isFinite(Number(row.scene_y)))avatar.style.bottom=clamp(row.scene_y,0,500)+'px';
    if(Number.isFinite(Number(row.scene_scale))){var s=clamp(row.scene_scale,.35,3);avatar.style.setProperty('--pk-player-edit-scale',String(s));avatar.style.transform='translateX(-50%) scale('+s+')';avatar.style.transformOrigin='bottom center'}
  }
  function applyAll(){
    var layer=byId('pk-actor-layer');if(!layer||!packet)return;
    Array.from(layer.querySelectorAll('.pkActor')).forEach(function(actor){
      if(actor.dataset.pkCustom==='1')applyCustom(actor);
      else if(actor.classList.contains('pkActionHotspot'))applyAction(actor);
      else{var entry=rowForActor(actor);if(entry)applyWorld(actor,entry)}
    });
    applyPlayer();
  }
  function scheduleApply(){[0,30,90,220,500].forEach(function(ms){setTimeout(applyAll,ms)})}

  function persistWorldActor(actor){
    if(!actor||!actor.dataset.pkWorldDbref)return;
    var payload={
      dbref:Number(actor.dataset.pkWorldDbref),
      scene_x:clamp(parseFloat(actor.style.left)||50,0,100),
      scene_y:clamp(parseFloat(actor.style.bottom)||2,0,100),
      scene_scale:clamp(parseFloat(actor.dataset.pkWorldScale||actor.style.getPropertyValue('--pk-world-actor-scale'))||1,.2,4)
    };
    send('pokerol-editor-update',payload);
  }
  function persistActor(actor){
    if(!actor)return;
    if(actor.dataset.pkWorldDbref){persistWorldActor(actor);return}
    if(actor.dataset.pkCustom==='1'||actor.classList.contains('pkActionHotspot')){
      if(window.PokerolHotspotEditorV01&&typeof PokerolHotspotEditorV01.persistSelected==='function')PokerolHotspotEditorV01.persistSelected();
    }
  }
  function queuePersist(actor){
    var old=saveTimers.get(actor);if(old)clearTimeout(old);
    saveTimers.set(actor,setTimeout(function(){saveTimers.delete(actor);persistActor(actor)},60));
  }
  function bindStage(){
    var stage=byId('pk-stage');if(!stage||stage.dataset.pkPersistenceGuard==='1')return false;
    stage.dataset.pkPersistenceGuard='1';
    stage.addEventListener('pointerup',function(ev){
      if(!stage.classList.contains('pkHotspotEditing'))return;
      var actor=ev.target&&ev.target.closest?ev.target.closest('.pkActor'):null;if(actor)queuePersist(actor);
    },true);
    return true;
  }
  function watchLayer(){
    var layer=byId('pk-actor-layer');if(!layer||observer)return !!layer;
    observer=new MutationObserver(function(){scheduleApply()});observer.observe(layer,{childList:true,subtree:true});return true;
  }
  function onSnapshot(args){packet=packetFrom(args);scheduleApply();return true}
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true;return true}
  function init(){var tries=0;(function wait(){tries++;bindEmitter();bindStage();watchLayer();if(emitterBound&&bindStage()&&watchLayer())return;if(tries<200)setTimeout(wait,50)})()}

  window.PokerolScenePersistenceGuardV01=Object.freeze({BUILD:BUILD,apply:applyAll});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
