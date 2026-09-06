(function(){
  'use strict';

  var BUILD='0.1.0-world-backed-editor';
  var lastPacket=null;
  var emitterBound=false;
  var actorObserver=null;
  var selectionObserver=null;
  var activeSelection=null;
  var spriteValue='';
  var spriteDirty=false;
  var spriteClear=false;
  var boundActors=new WeakSet();

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).replace(/\s+/g,' ').trim()}
  function num(v,fallback){var n=parseFloat(v);return Number.isFinite(n)?n:fallback}
  function clamp(v,min,max){return Math.max(min,Math.min(max,v))}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function roomKey(){return clean((byId('pk-room-id')&&byId('pk-room-id').textContent)||'')||clean((byId('pk-room-name')&&byId('pk-room-name').textContent)||'UNASSIGNED')}
  function selectedActor(){return document.querySelector('.pkActor.pkSelectedHotspot')}
  function labelOf(actor){var n=actor&&actor.querySelector('.pkActorLabel');return clean(n&&n.textContent)}
  function encodePayload(data){
    var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';
    for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function sendEditor(command,data){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',[command+' '+encodePayload(data)],{});return true}catch(e){return false}
  }
  function requestState(){
    if(window.PokerolPlayableClientV01&&PokerolPlayableClientV01.requestRoomState)PokerolPlayableClientV01.requestRoomState();
  }
  function status(text,error){
    var n=byId('pk-world-editor-status');if(n){n.textContent=clean(text);n.classList.toggle('pkWorldEditorError',!!error)}
  }
  function roomStatus(text,error){
    var n=byId('pk-room-editor-status');if(n){n.textContent=clean(text);n.classList.toggle('pkWorldEditorError',!!error)}
  }

  function packetRows(){
    var p=lastPacket||{},rows=[];
    (p.visible_npcs||p.people||[]).forEach(function(r){rows.push({kind:'NPC',row:r})});
    (p.visible_objects||p.objects||[]).forEach(function(r){rows.push({kind:'OBJECT',row:r})});
    return rows;
  }
  function exactRow(kind,name){
    var wanted=clean(name).toLowerCase();
    return packetRows().find(function(entry){return entry.kind===kind&&clean(entry.row&&entry.row.name).toLowerCase()===wanted})||null;
  }
  function exitRow(name){
    var wanted=clean(name).toLowerCase();
    return ((lastPacket&&lastPacket.exits)||[]).find(function(r){return clean(r&&r.name).toLowerCase()===wanted||clean(r&&r.command).toLowerCase()===wanted})||null;
  }
  function setActorSprite(actor,src){
    if(!actor)return;
    var image=actor.querySelector('.pkActorSprite'),placeholder=actor.querySelector('.pkActorPlaceholder');
    if(src){
      if(!image){image=document.createElement('img');image.className='pkActorSprite';actor.insertBefore(image,actor.firstChild)}
      image.src=src;image.alt=labelOf(actor)||'Sprite';
      if(placeholder)placeholder.style.display='none';
    }else if(image&&actor.dataset.pkWorldSceneSprite==='1'){
      image.remove();if(placeholder)placeholder.style.display='';
    }
  }
  function applyRow(actor,kind,row){
    if(!actor||!row||row.dbref==null)return;
    actor.dataset.pkWorldDbref=String(row.dbref);
    actor.dataset.pkWorldKind=kind;
    actor.dataset.pkHotspotKey='DBREF:'+String(row.dbref);
    actor.dataset.pkWorldDescription=String(row.description||'');
    actor.dataset.pkWorldDialogue=String(row.dialogue_greeting||'');
    actor.dataset.pkWorldSceneSprite=row.scene_sprite?'1':'0';
    if(Number.isFinite(Number(row.scene_x)))actor.style.left=clamp(Number(row.scene_x),0,100)+'%';
    if(Number.isFinite(Number(row.scene_y)))actor.style.bottom=clamp(Number(row.scene_y),0,100)+'%';
    var scale=Number(row.scene_scale);if(Number.isFinite(scale)){scale=clamp(scale,.2,4);actor.style.setProperty('--pk-world-actor-scale',String(scale));actor.dataset.pkWorldScale=String(scale)}
    if(row.scene_sprite)setActorSprite(actor,String(row.scene_sprite));
    bindWorldActor(actor);
  }
  function annotateActors(){
    var layer=byId('pk-actor-layer');if(!layer||!lastPacket)return;
    Array.from(layer.querySelectorAll('.pkActor')).forEach(function(actor){
      if(actor.dataset.pkCustom==='1')return;
      var kind=clean(actor.dataset.kind).toUpperCase(),name=labelOf(actor),match=null;
      if(kind==='NPC'||kind==='OBJECT')match=exactRow(kind,name);
      else if(kind==='EXIT'){
        var row=exitRow(name);if(row)match={kind:'EXIT',row:row};
      }
      if(match&&match.row)applyRow(actor,match.kind||kind,match.row);
      else if(match)applyRow(actor,kind,match);
      else bindWorldActor(actor);
    });
    if(selectedActor())fillSelection(selectedActor());
  }
  function bindWorldActor(actor){
    if(!actor||boundActors.has(actor))return;boundActors.add(actor);
    actor.addEventListener('pointerup',function(){
      if(!actor.dataset.pkWorldDbref)return;
      var stage=byId('pk-stage');if(!stage||!stage.classList.contains('pkHotspotEditing'))return;
      setTimeout(function(){saveWorldPosition(actor)},30);
    });
  }
  function saveWorldPosition(actor){
    if(!actor||!actor.dataset.pkWorldDbref)return;
    var payload={
      dbref:Number(actor.dataset.pkWorldDbref),
      scene_x:clamp(num(actor.style.left,50),0,100),
      scene_y:clamp(num(actor.style.bottom,2),0,100),
      scene_scale:clamp(num(actor.dataset.pkWorldScale||actor.style.getPropertyValue('--pk-world-actor-scale'),1),.2,4)
    };
    sendEditor('pokerol-editor-update',payload);
  }

  function customMetaKey(actor){return 'pokerol_custom_hotspot_meta_v1:'+roomKey()+':'+String(actor&&actor.dataset.pkHotspotKey||'')}
  function loadCustomMeta(actor){try{return JSON.parse(localStorage.getItem(customMetaKey(actor))||'{}')||{}}catch(e){return {}}}
  function saveCustomMeta(actor,meta){try{localStorage.setItem(customMetaKey(actor),JSON.stringify(meta||{}))}catch(e){}}
  function applyCustomMeta(actor){
    if(!actor||actor.dataset.pkCustom!=='1')return;
    var meta=loadCustomMeta(actor),scale=clamp(num(meta.scale,1),.2,4);actor.dataset.pkWorldScale=String(scale);actor.style.setProperty('--pk-world-actor-scale',String(scale));
    if(meta.sprite)setActorSprite(actor,meta.sprite);
  }

  function injectHotspotFields(){
    var panel=byId('pk-hotspot-panel');if(!panel||byId('pk-world-editor-extra'))return !!panel;
    var commandField=byId('pk-hotspot-command');var anchor=commandField&&commandField.closest('.pkHotspotField');
    var extra=document.createElement('div');extra.id='pk-world-editor-extra';extra.className='pkWorldEditorExtra';
    extra.innerHTML=''
      +'<div class="pkWorldEditorKind" id="pk-world-editor-kind">HOTSPOT</div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-description">DESCRIPCIÓN / CONTENIDO</label><textarea id="pk-hotspot-description" rows="3" maxlength="6000" placeholder="Qué es y qué ve el jugador"></textarea></div>'
      +'<div class="pkHotspotField pkNpcOnly" id="pk-hotspot-dialogue-wrap"><label for="pk-hotspot-dialogue">SALUDO DEL NPC</label><textarea id="pk-hotspot-dialogue" rows="2" maxlength="2000" placeholder="Primera línea al hablar"></textarea></div>'
      +'<div class="pkWorldSpriteRow"><div id="pk-hotspot-sprite-preview" class="pkWorldSpritePreview"><span>SPRITE</span></div><div class="pkWorldSpriteButtons"><button id="pk-hotspot-sprite-load" type="button">CARGAR SPRITE</button><button id="pk-hotspot-sprite-clear" type="button">QUITAR</button><input id="pk-hotspot-sprite-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden></div></div>'
      +'<div class="pkHotspotField"><label for="pk-hotspot-scale">ESCALA</label><input id="pk-hotspot-scale" type="number" min="0.2" max="4" step="0.05" value="1"></div>'
      +'<div id="pk-world-editor-status" class="pkWorldEditorStatus"></div>';
    if(anchor)anchor.insertAdjacentElement('afterend',extra);else panel.appendChild(extra);

    var load=byId('pk-hotspot-sprite-load'),file=byId('pk-hotspot-sprite-file'),clear=byId('pk-hotspot-sprite-clear'),scale=byId('pk-hotspot-scale'),save=byId('pk-hotspot-save');
    if(load&&file)load.addEventListener('click',function(){if(!activeSelection)return;file.value='';file.click()});
    if(file)file.addEventListener('change',function(){
      var selected=file.files&&file.files[0];if(!selected||!activeSelection)return;
      if(!/^image\/(png|jpeg|webp|gif)$/i.test(selected.type||'')){status('Formato no admitido.',true);return}
      if(selected.size>1000000){status('El sprite supera 1 MB.',true);return}
      var reader=new FileReader();reader.onload=function(){spriteValue=String(reader.result||'');spriteDirty=true;spriteClear=false;setActorSprite(activeSelection,spriteValue);renderPreview(spriteValue);status('Sprite listo para guardar.',false)};reader.readAsDataURL(selected);
    });
    if(clear)clear.addEventListener('click',function(){if(!activeSelection)return;spriteValue='';spriteDirty=true;spriteClear=true;var img=activeSelection.querySelector('.pkActorSprite');if(img)img.remove();var ph=activeSelection.querySelector('.pkActorPlaceholder');if(ph)ph.style.display='';renderPreview('');status('Sprite marcado para quitar.',false)});
    if(scale)scale.addEventListener('input',function(){if(!activeSelection)return;var s=clamp(num(scale.value,1),.2,4);activeSelection.dataset.pkWorldScale=String(s);activeSelection.style.setProperty('--pk-world-actor-scale',String(s))});
    if(save)save.addEventListener('click',function(){setTimeout(saveSelectionToAuthority,0)});
    return true;
  }

  function renderPreview(src){
    var root=byId('pk-hotspot-sprite-preview');if(!root)return;root.innerHTML='';
    if(src){var img=document.createElement('img');img.src=src;img.alt='Preview del sprite';root.appendChild(img)}else{var span=document.createElement('span');span.textContent='SIN SPRITE';root.appendChild(span)}
  }
  function fillSelection(actor){
    if(!byId('pk-world-editor-extra'))return;
    activeSelection=actor||null;spriteValue='';spriteDirty=false;spriteClear=false;
    var kind=actor?clean(actor.dataset.pkWorldKind||actor.dataset.kind||'CUSTOM').toUpperCase():'HOTSPOT';
    var badge=byId('pk-world-editor-kind');if(badge)badge.textContent=kind+(actor&&actor.dataset.pkWorldDbref?' · #'+actor.dataset.pkWorldDbref:'');
    var desc=byId('pk-hotspot-description'),dialog=byId('pk-hotspot-dialogue'),wrap=byId('pk-hotspot-dialogue-wrap'),scale=byId('pk-hotspot-scale');
    if(!actor){if(desc)desc.value='';if(dialog)dialog.value='';if(scale)scale.value='1';if(wrap)wrap.hidden=true;renderPreview('');status('',false);return}
    var custom=actor.dataset.pkCustom==='1',meta=custom?loadCustomMeta(actor):{};
    if(desc)desc.value=custom?String(meta.description||''):String(actor.dataset.pkWorldDescription||'');
    if(dialog)dialog.value=String(actor.dataset.pkWorldDialogue||'');
    if(wrap)wrap.hidden=kind!=='NPC';
    var sc=custom?num(meta.scale,1):num(actor.dataset.pkWorldScale||actor.style.getPropertyValue('--pk-world-actor-scale'),1);if(scale)scale.value=clamp(sc,.2,4).toFixed(2);
    var image=actor.querySelector('.pkActorSprite');renderPreview(image&&image.src||'');
    status(actor.dataset.pkWorldDbref?'WORLD ENGINE · los cambios son compartidos':'LOCAL · hotspot visual del navegador',false);
  }
  function saveSelectionToAuthority(){
    var actor=selectedActor()||activeSelection;if(!actor)return;
    activeSelection=actor;
    var description=String(byId('pk-hotspot-description')&&byId('pk-hotspot-description').value||'').trim();
    var scale=clamp(num(byId('pk-hotspot-scale')&&byId('pk-hotspot-scale').value,1),.2,4);
    var x=clamp(num(actor.style.left,50),0,100),y=clamp(num(actor.style.bottom,2),0,100);
    if(actor.dataset.pkWorldDbref){
      var payload={dbref:Number(actor.dataset.pkWorldDbref),name:clean(byId('pk-hotspot-name')&&byId('pk-hotspot-name').value)||labelOf(actor),description:description,scene_x:x,scene_y:y,scene_scale:scale};
      if(clean(actor.dataset.pkWorldKind).toUpperCase()==='NPC')payload.dialogue_greeting=String(byId('pk-hotspot-dialogue')&&byId('pk-hotspot-dialogue').value||'').trim();
      if(spriteDirty){if(spriteClear)payload.clear_sprite=true;else payload.scene_sprite=spriteValue}
      status('GUARDANDO EN WORLD ENGINE…',false);
      if(!sendEditor('pokerol-editor-update',payload))status('No se pudo enviar el cambio.',true);
    }else if(actor.dataset.pkCustom==='1'){
      var meta={description:description,scale:scale,sprite:spriteClear?'':(spriteDirty?spriteValue:(loadCustomMeta(actor).sprite||''))};saveCustomMeta(actor,meta);applyCustomMeta(actor);status('Hotspot local guardado.',false);
    }
  }

  function injectRoomEditor(){
    var stage=byId('pk-stage'),menu=byId('pk-edit-menu');if(!stage||!menu)return false;
    if(!byId('pk-edit-room')){
      var btn=document.createElement('button');btn.id='pk-edit-room';btn.type='button';btn.textContent='CUARTO';
      var player=byId('pk-edit-player');menu.insertBefore(btn,player||null);
    }
    if(!byId('pk-room-panel')){
      var panel=document.createElement('aside');panel.id='pk-room-panel';panel.className='pkRoomPanel';panel.hidden=true;
      panel.innerHTML=''
        +'<div class="pkRoomPanelHead"><strong>CUARTO / MAPA</strong><button id="pk-room-close" type="button" aria-label="Cerrar">×</button></div>'
        +'<div class="pkRoomSectionTitle">CUARTO ACTUAL</div>'
        +'<div class="pkHotspotField"><label for="pk-room-current-name">NOMBRE</label><input id="pk-room-current-name" type="text" maxlength="96"></div>'
        +'<div class="pkHotspotField"><label for="pk-room-current-desc">DESCRIPCIÓN</label><textarea id="pk-room-current-desc" rows="4" maxlength="6000"></textarea></div>'
        +'<button id="pk-room-current-save" type="button" class="pkRoomWide">GUARDAR CUARTO</button>'
        +'<div class="pkRoomDivider"></div>'
        +'<div class="pkRoomSectionTitle">NUEVO CUARTO CONECTADO</div>'
        +'<div class="pkHotspotField"><label for="pk-room-new-name">NOMBRE</label><input id="pk-room-new-name" type="text" maxlength="96" placeholder="Ej. Sendero norte"></div>'
        +'<div class="pkHotspotField"><label for="pk-room-new-desc">DESCRIPCIÓN</label><textarea id="pk-room-new-desc" rows="4" maxlength="6000" placeholder="Qué ve el jugador al entrar"></textarea></div>'
        +'<div class="pkHotspotField"><label for="pk-room-new-exit">SALIDA DESDE AQUÍ</label><input id="pk-room-new-exit" type="text" maxlength="96" placeholder="Ej. Ir hacia el sendero"></div>'
        +'<div class="pkHotspotField"><label for="pk-room-new-return">SALIDA DE REGRESO</label><input id="pk-room-new-return" type="text" maxlength="96" placeholder="Ej. Volver al pueblo"></div>'
        +'<button id="pk-room-create" type="button" class="pkRoomWide">+ CREAR CUARTO</button>'
        +'<div id="pk-room-editor-status" class="pkWorldEditorStatus"></div>';
      stage.appendChild(panel);bindRoomDrag(panel,panel.querySelector('.pkRoomPanelHead'));
    }
    var open=byId('pk-edit-room'),panel=byId('pk-room-panel'),close=byId('pk-room-close'),save=byId('pk-room-current-save'),create=byId('pk-room-create');
    if(open&&open.dataset.pkWorldBound!=='1'){open.dataset.pkWorldBound='1';open.addEventListener('click',function(){var m=byId('pk-edit-menu');if(m)m.hidden=true;fillRoomPanel();panel.hidden=false})}
    if(close&&close.dataset.pkWorldBound!=='1'){close.dataset.pkWorldBound='1';close.addEventListener('click',function(){panel.hidden=true})}
    if(save&&save.dataset.pkWorldBound!=='1'){save.dataset.pkWorldBound='1';save.addEventListener('click',saveCurrentRoom)}
    if(create&&create.dataset.pkWorldBound!=='1'){create.dataset.pkWorldBound='1';create.addEventListener('click',createRoom)}
    return true;
  }
  function fillRoomPanel(){
    var p=lastPacket||{},room=p.room_editor||{};var name=byId('pk-room-current-name'),desc=byId('pk-room-current-desc');if(name)name.value=String(room.name||p.room_name||'');if(desc)desc.value=String(room.description||p.room_description||'');roomStatus('',false)
  }
  function saveCurrentRoom(){
    if(!lastPacket||lastPacket.room_dbref==null){roomStatus('No hay cuarto activo.',true);return}
    var payload={dbref:Number(lastPacket.room_dbref),name:clean(byId('pk-room-current-name')&&byId('pk-room-current-name').value),description:String(byId('pk-room-current-desc')&&byId('pk-room-current-desc').value||'').trim()};
    roomStatus('GUARDANDO…',false);if(!sendEditor('pokerol-editor-update',payload))roomStatus('No se pudo enviar.',true)
  }
  function createRoom(){
    var name=clean(byId('pk-room-new-name')&&byId('pk-room-new-name').value);if(!name){roomStatus('Escribe un nombre para el cuarto.',true);return}
    var payload={name:name,description:String(byId('pk-room-new-desc')&&byId('pk-room-new-desc').value||'').trim(),exit_name:clean(byId('pk-room-new-exit')&&byId('pk-room-new-exit').value),return_exit_name:clean(byId('pk-room-new-return')&&byId('pk-room-new-return').value)};
    roomStatus('CREANDO CUARTO…',false);if(!sendEditor('pokerol-editor-create-room',payload))roomStatus('No se pudo enviar.',true)
  }
  function bindRoomDrag(panel,handle){
    if(!panel||!handle||panel.dataset.pkDragBound==='1')return;panel.dataset.pkDragBound='1';handle.classList.add('pkEditorDragHandle');
    try{var saved=JSON.parse(localStorage.getItem('pokerol_editor_panel_pos_v1:'+panel.id)||'null');if(saved&&saved.left){panel.style.left=saved.left;panel.style.top=saved.top;panel.style.right='auto'}}catch(e){}
    handle.addEventListener('pointerdown',function(ev){
      if(ev.target.closest('button,input,textarea,select'))return;var stage=byId('pk-stage');if(!stage)return;ev.preventDefault();
      var sr=stage.getBoundingClientRect(),pr=panel.getBoundingClientRect(),startX=ev.clientX,startY=ev.clientY,startL=pr.left-sr.left,startT=pr.top-sr.top,id=ev.pointerId;handle.setPointerCapture&&handle.setPointerCapture(id);
      function move(e){if(e.pointerId!==id)return;var l=clamp(startL+e.clientX-startX,0,Math.max(0,sr.width-panel.offsetWidth)),t=clamp(startT+e.clientY-startY,0,Math.max(0,sr.height-panel.offsetHeight));panel.style.left=l+'px';panel.style.top=t+'px';panel.style.right='auto'}
      function up(e){if(e.pointerId!==id)return;handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',up);handle.removeEventListener('pointercancel',up);try{localStorage.setItem('pokerol_editor_panel_pos_v1:'+panel.id,JSON.stringify({left:panel.style.left,top:panel.style.top}))}catch(err){}}
      handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',up);handle.addEventListener('pointercancel',up);
    });
  }

  function onSnapshot(args){lastPacket=packetFrom(args);annotateActors();fillRoomPanel();setTimeout(annotateActors,0);setTimeout(annotateActors,40)}
  function onEditorResult(args){
    var p=packetFrom(args),ok=p.status==='UPDATED'||p.status==='ROOM_CREATED';
    status(p.message||p.status,!ok);roomStatus(p.message||p.status,!ok);
    if(ok){spriteDirty=false;spriteClear=false;if(p.status==='ROOM_CREATED'){var n=byId('pk-room-new-name'),d=byId('pk-room-new-desc'),e=byId('pk-room-new-exit'),r=byId('pk-room-new-return');if(n)n.value='';if(d)d.value='';if(e)e.value='';if(r)r.value=''}setTimeout(requestState,80)}
  }
  function bindEmitter(){
    if(emitterBound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);Evennia.emitter.on('pokerol_editor_result',onEditorResult);emitterBound=true;return true;
  }
  function watchDom(){
    var layer=byId('pk-actor-layer');if(layer&&!actorObserver){actorObserver=new MutationObserver(function(){annotateActors();Array.from(layer.querySelectorAll('.pkCustomHotspot')).forEach(applyCustomMeta)});actorObserver.observe(layer,{childList:true,subtree:true})}
    var stage=byId('pk-stage');if(stage&&!selectionObserver){selectionObserver=new MutationObserver(function(records){if(records.some(function(r){return r.type==='attributes'&&r.attributeName==='class'})){var s=selectedActor();if(s!==activeSelection)fillSelection(s)}});selectionObserver.observe(stage,{subtree:true,attributes:true,attributeFilter:['class']})}
  }
  function init(){
    var tries=0;(function wait(){tries++;var ready=injectHotspotFields()&&injectRoomEditor();watchDom();bindEmitter();if(ready&&emitterBound){requestState();return}if(tries<180)setTimeout(wait,50)})();
  }

  window.PokerolWorldEditorV01=Object.freeze({BUILD:BUILD,requestState:requestState,saveSelection:saveSelectionToAuthority});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
