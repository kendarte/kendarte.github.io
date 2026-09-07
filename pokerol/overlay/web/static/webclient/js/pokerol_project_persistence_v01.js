(function(){
  'use strict';

  var BUILD='0.2.0-project-persistence';
  var lastPacket=null;
  var emitterBound=false;
  var roomMigrationTried={};
  var trainerMigrationTried=false;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function manager(){return window.PokerolAssetManagerV01}
  function requestRoom(){if(window.PokerolPlayableClientV01&&typeof PokerolPlayableClientV01.requestRoomState==='function')PokerolPlayableClientV01.requestRoomState();else if(window.Evennia&&typeof Evennia.msg==='function')Evennia.msg('text',['pokerol-room-state'],{})}
  function dialogue(text){var n=byId('pk-dialogue-text');if(n)n.textContent=String(text||'');var s=byId('pk-speaker');if(s)s.textContent='SISTEMA'}
  function bgStatus(text){var n=byId('pk-bg-status');if(n){n.textContent=String(text||'');n.classList.toggle('pkVisible',!!text)}}
  function worldStatus(text,error){var n=byId('pk-world-editor-status');if(n){n.textContent=String(text||'');n.classList.toggle('pkWorldEditorError',!!error)}}
  function selectedActor(){return document.querySelector('.pkActor.pkSelectedHotspot')}

  function backgroundKeys(packet){
    var keys=[],id=clean(packet&&packet.room_id),name=clean(packet&&(packet.room_name||packet.location));if(id)keys.push(id);if(name)keys.push('ROOMNAME:'+name.toLowerCase(),name,name.toLowerCase());return keys.filter(function(v,i,a){return v&&a.indexOf(v)===i});
  }
  function getLocalBackground(packet){
    var keys=backgroundKeys(packet);if(!window.indexedDB||!keys.length)return Promise.resolve(null);
    return new Promise(function(resolve){
      try{
        var req=indexedDB.open('pokerol_visuals_v1',1);req.onerror=function(){resolve(null)};req.onsuccess=function(){
          var db=req.result;if(!db.objectStoreNames.contains('room_backgrounds')){resolve(null);return}
          var store=db.transaction('room_backgrounds','readonly').objectStore('room_backgrounds'),index=0;
          (function next(){if(index>=keys.length){resolve(null);return}var r=store.get(keys[index++]);r.onerror=next;r.onsuccess=function(){if(r.result&&r.result.blob)resolve(r.result);else next()}})();
        };
      }catch(e){resolve(null)}
    });
  }
  function purgeLocalBackgrounds(packet){
    if(!window.indexedDB)return;var keys=backgroundKeys(packet);if(!keys.length)return;
    try{var req=indexedDB.open('pokerol_visuals_v1',1);req.onsuccess=function(){var db=req.result;if(!db.objectStoreNames.contains('room_backgrounds'))return;var store=db.transaction('room_backgrounds','readwrite').objectStore('room_backgrounds');keys.forEach(function(k){try{store.delete(k)}catch(e){}})}}catch(e){}
  }
  function activeGender(){
    try{var user=clean(localStorage.getItem('pokerol.last_user'));if(!user)return 'boy';var p=JSON.parse(localStorage.getItem('pokerol.profile.'+user.toLowerCase())||'{}')||{};return clean(p.gender).toLowerCase()==='girl'?'girl':'boy'}catch(e){return 'boy'}
  }
  function getLocalTrainerSprite(){
    if(!window.indexedDB)return Promise.resolve(null);var gender=activeGender();
    return new Promise(function(resolve){try{var req=indexedDB.open('pokerol_trainer_sprite_v1',1);req.onerror=function(){resolve(null)};req.onsuccess=function(){var db=req.result;if(!db.objectStoreNames.contains('sprites')){resolve(null);return}var r=db.transaction('sprites','readonly').objectStore('sprites').get(gender);r.onerror=function(){resolve(null)};r.onsuccess=function(){resolve(r.result&&r.result.blob?r.result:null)}}}catch(e){resolve(null)}});
  }
  function clearLocalTrainerSprites(){
    if(!window.indexedDB)return;try{var req=indexedDB.open('pokerol_trainer_sprite_v1',1);req.onsuccess=function(){var db=req.result;if(!db.objectStoreNames.contains('sprites'))return;try{db.transaction('sprites','readwrite').objectStore('sprites').clear()}catch(e){}}}catch(e){}
  }
  function forceServerBackground(packet){
    var url=clean(packet&&packet.scene_image);if(!url||!url.startsWith('/pokerol-assets/'))return;var bg=byId('pk-stage-bg');if(bg)bg.style.backgroundImage='url("'+url.replace(/"/g,'%22')+'")';bgStatus('PROJECT ASSET');
  }
  function forceServerPlayer(packet){
    var editor=packet&&packet.player_editor||{},url=clean(editor.scene_sprite);if(!url||!url.startsWith('/pokerol-assets/'))return;clearLocalTrainerSprites();
    var img=byId('pk-player-sprite');if(img){img.dataset.pkProjectSprite='1';if(img.getAttribute('src')!==url)img.src=url;img.style.objectFit='contain';img.style.objectPosition='center bottom';img.style.imageRendering='pixelated'}
    var preview=byId('pk-player-sprite-preview');if(preview){preview.src=url;preview.hidden=false}
  }
  function migrateLocalBackground(packet){
    var key=clean(packet&&packet.room_id)||clean(packet&&(packet.room_name||packet.location));if(!key||roomMigrationTried[key]||clean(packet.scene_image))return;roomMigrationTried[key]=true;
    getLocalBackground(packet).then(function(row){if(!row||!row.blob||!manager())return;bgStatus('MIGRANDO BACKGROUND AL PROYECTO…');return manager().uploadFile({kind:'room_background'},row.blob,function(p){bgStatus('MIGRANDO '+Math.round(p*100)+'%')}).then(function(result){packet.scene_image=result.url;purgeLocalBackgrounds(packet);forceServerBackground(packet);dialogue('Background recuperado y guardado permanentemente en el proyecto.');requestRoom()})}).catch(function(){});
  }
  function migrateLocalTrainer(packet){
    var editor=packet&&packet.player_editor||{};if(trainerMigrationTried||clean(editor.scene_sprite))return;trainerMigrationTried=true;
    getLocalTrainerSprite().then(function(row){if(!row||!row.blob||!manager())return;dialogue('Migrando sprite del entrenador al proyecto…');return manager().uploadFile({kind:'player_sprite'},row.blob).then(function(result){editor.scene_sprite=result.url;packet.player_editor=editor;clearLocalTrainerSprites();forceServerPlayer(packet);dialogue('Sprite recuperado y guardado permanentemente.');requestRoom()})}).catch(function(){});
  }
  function onSnapshot(args){
    lastPacket=packetFrom(args);var hasBg=clean(lastPacket.scene_image).startsWith('/pokerol-assets/'),hasPlayer=clean(lastPacket.player_editor&&lastPacket.player_editor.scene_sprite).startsWith('/pokerol-assets/');
    if(hasBg){purgeLocalBackgrounds(lastPacket);forceServerBackground(lastPacket)}else migrateLocalBackground(lastPacket);
    if(hasPlayer)forceServerPlayer(lastPacket);else migrateLocalTrainer(lastPacket);
    [40,140,500].forEach(function(ms){setTimeout(function(){forceServerBackground(lastPacket);forceServerPlayer(lastPacket)},ms)});return true;
  }
  function bindEmitter(){if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);emitterBound=true;return true}

  function setActorSprite(actor,url){
    if(!actor)return;var img=actor.querySelector('.pkActorSprite'),ph=actor.querySelector('.pkActorPlaceholder');
    if(url){if(!img){img=document.createElement('img');img.className='pkActorSprite';actor.insertBefore(img,actor.firstChild)}img.src=url;img.alt=clean(actor.querySelector('.pkActorLabel')&&actor.querySelector('.pkActorLabel').textContent)||'Sprite';if(ph)ph.style.display='none'}else{if(img)img.remove();if(ph)ph.style.display=''}
    var preview=byId('pk-hotspot-sprite-preview');if(preview){preview.innerHTML='';if(url){var p=document.createElement('img');p.src=url;p.alt='Preview';preview.appendChild(p)}else{var s=document.createElement('span');s.textContent='SIN SPRITE';preview.appendChild(s)}}
  }
  function uploadBackground(file){
    var m=manager();if(!m)return;bgStatus('GUARDANDO EN PROYECTO 0%');dialogue('Guardando background en el proyecto…');
    m.uploadFile({kind:'room_background'},file,function(p){bgStatus('GUARDANDO EN PROYECTO '+Math.round(p*100)+'%')}).then(function(result){bgStatus('PROJECT ASSET');if(lastPacket)lastPacket.scene_image=result.url;purgeLocalBackgrounds(lastPacket||{});forceServerBackground(lastPacket||{scene_image:result.url});dialogue('Background guardado permanentemente en el proyecto.');requestRoom()}).catch(function(err){bgStatus('NO GUARDADO');dialogue(err.message||'No se pudo guardar el background.')});
  }
  function clearBackground(){var m=manager();if(!m)return;m.clearAsset({kind:'room_background'}).then(function(){bgStatus('');if(lastPacket)lastPacket.scene_image='';dialogue('Background del proyecto eliminado.');requestRoom()}).catch(function(err){dialogue(err.message||'No se pudo quitar el background.')})}
  function uploadPlayer(file){
    var m=manager();if(!m)return;dialogue('Guardando sprite del entrenador en el proyecto…');
    m.uploadFile({kind:'player_sprite'},file).then(function(result){clearLocalTrainerSprites();var img=byId('pk-player-sprite');if(img){img.dataset.pkProjectSprite='1';img.src=result.url}var preview=byId('pk-player-sprite-preview');if(preview){preview.src=result.url;preview.hidden=false}dialogue('Sprite del entrenador guardado permanentemente.');requestRoom()}).catch(function(err){dialogue(err.message||'No se pudo guardar el sprite.')});
  }
  function uploadHotspot(file,actor){
    var m=manager();if(!m||!actor)return;var meta=null;if(actor.dataset.pkWorldDbref)meta={kind:'entity_sprite',dbref:Number(actor.dataset.pkWorldDbref)};else if(actor.dataset.pkCustom==='1')meta={kind:'custom_hotspot_sprite',hotspot_id:String(actor.dataset.pkHotspotKey||'')};if(!meta){worldStatus('Ese hotspot no tiene destino persistente.',true);return}
    worldStatus('GUARDANDO SPRITE EN PROYECTO…',false);m.uploadFile(meta,file,function(p){worldStatus('GUARDANDO SPRITE '+Math.round(p*100)+'%',false)}).then(function(result){setActorSprite(actor,result.url);actor.dataset.pkProjectSprite=result.url;if(actor.dataset.pkCustom==='1'){actor.dataset.pkCustomSprite=result.url;if(window.PokerolHotspotEditorV01)PokerolHotspotEditorV01.persistSelected()}worldStatus('SPRITE GUARDADO EN PROYECTO',false);requestRoom()}).catch(function(err){worldStatus(err.message||'No se pudo guardar el sprite.',true)});
  }
  function clearHotspotSprite(actor){
    var m=manager();if(!m||!actor)return;var meta=null;if(actor.dataset.pkWorldDbref)meta={kind:'entity_sprite',dbref:Number(actor.dataset.pkWorldDbref)};else if(actor.dataset.pkCustom==='1')meta={kind:'custom_hotspot_sprite',hotspot_id:String(actor.dataset.pkHotspotKey||'')};if(!meta)return;
    m.clearAsset(meta).then(function(){setActorSprite(actor,'');actor.dataset.pkProjectSprite='';actor.dataset.pkCustomSprite='';if(actor.dataset.pkCustom==='1'&&window.PokerolHotspotEditorV01)PokerolHotspotEditorV01.persistSelected();worldStatus('SPRITE QUITADO DEL PROYECTO',false);requestRoom()}).catch(function(err){worldStatus(err.message||'No se pudo quitar el sprite.',true)});
  }
  function onChangeCapture(ev){
    var t=ev.target;if(!t||t.type!=='file')return;var file=t.files&&t.files[0];if(!file)return;
    if(t.id==='pk-background-file'){ev.stopImmediatePropagation();uploadBackground(file);t.value='';return}
    if(t.id==='pk-player-sprite-file'&&clean(byId('pk-room-id')&&byId('pk-room-id').textContent)){ev.stopImmediatePropagation();uploadPlayer(file);t.value='';return}
    if(t.id==='pk-hotspot-sprite-file'){var actor=selectedActor();if(!actor)return;ev.stopImmediatePropagation();uploadHotspot(file,actor);t.value='';return}
  }
  function onClickCapture(ev){
    var t=ev.target;if(!t)return;if(t.id==='pk-reset-background'){ev.preventDefault();ev.stopImmediatePropagation();clearBackground();return}
    if(t.id==='pk-hotspot-sprite-clear'){var actor=selectedActor();if(!actor)return;ev.preventDefault();ev.stopImmediatePropagation();clearHotspotSprite(actor);return}
  }
  function init(){document.addEventListener('change',onChangeCapture,true);document.addEventListener('click',onClickCapture,true);var tries=0;(function wait(){tries++;if(bindEmitter())return;if(tries<160)setTimeout(wait,50)})()}

  window.PokerolProjectPersistenceV01=Object.freeze({BUILD:BUILD,requestRoom:requestRoom});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
