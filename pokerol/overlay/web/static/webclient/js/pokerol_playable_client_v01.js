(function(){
  'use strict';
  var BUILD='0.3.0-playable-narrative-feed';
  var emitterBound=false;
  var lastSnapshot=null;
  var lastActions=null;
  var lastNarratedRoomKey='';

  function byId(id){return document.getElementById(id)}
  function clean(value){return String(value==null?'':value).replace(/\s+/g,' ').trim()}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }
  function scrollFeed(){
    var feed=byId('messagewindow');
    if(feed)feed.scrollTop=feed.scrollHeight;
  }
  function appendFeed(value,kind,allowHtml){
    var feed=byId('messagewindow');
    if(!feed)return;
    var raw=String(value==null?'':value);
    if(!raw.trim())return;
    var row=document.createElement('div');
    row.className='pkFeedLine pkFeed-'+(kind||'world');
    if(allowHtml)row.innerHTML=raw;
    else row.textContent=raw;
    feed.appendChild(row);
    while(feed.children.length>180)feed.removeChild(feed.firstChild);
    scrollFeed();
  }
  function appendSystem(text){appendFeed(text,'system',false)}
  function appendCommand(text){appendFeed('> '+text,'command',false)}

  function send(command){
    var field=byId('inputfield');
    var button=byId('inputsend');
    if(!field||!button)return false;
    var outgoing=String(command||'').trim();
    if(!outgoing)return false;
    appendCommand(outgoing);
    field.value=outgoing;
    field.dispatchEvent(new Event('input',{bubbles:true}));
    button.click();
    window.setTimeout(function(){field.focus()},40);
    return true;
  }
  function bind(id,command){var el=byId(id);if(el)el.addEventListener('click',function(){send(command)})}

  function renderMeta(packet){
    var root=byId('pk-room-meta');
    if(!root)return;
    root.innerHTML='';
    var groups=[];
    var exits=Array.isArray(packet.exits)?packet.exits:[];
    var people=Array.isArray(packet.visible_npcs)?packet.visible_npcs:(Array.isArray(packet.people)?packet.people:[]);
    var objects=Array.isArray(packet.visible_objects)?packet.visible_objects:(Array.isArray(packet.objects)?packet.objects:[]);
    function names(rows){return rows.map(function(row){return clean(typeof row==='string'?row:(row&&(row.name||row.label||row.target)))}).filter(Boolean)}
    var exitNames=names(exits),peopleNames=names(people),objectNames=names(objects);
    if(exitNames.length)groups.push(['SALIDAS',exitNames.join(' · ')]);
    if(peopleNames.length)groups.push(['PERSONAS',peopleNames.join(' · ')]);
    if(objectNames.length)groups.push(['VISIBLE',objectNames.join(' · ')]);
    groups.forEach(function(group){
      var chip=document.createElement('div');
      chip.className='pkMetaChip';
      var label=document.createElement('b');label.textContent=group[0];
      var value=document.createElement('span');value.textContent=group[1];
      chip.appendChild(label);chip.appendChild(value);root.appendChild(chip);
    });
  }

  function renderActions(packet){
    lastActions=packet||lastActions||{};
    var root=byId('pk-context-actions');
    if(!root)return;
    root.innerHTML='';
    var actions=(packet&&(packet.available_actions||packet.actions))||[];
    if(!Array.isArray(actions))actions=[];
    if(!actions.length){
      var empty=document.createElement('span');
      empty.className='pkNoActions';
      empty.textContent='No hay acciones contextuales visibles.';
      root.appendChild(empty);
      return;
    }
    actions.forEach(function(action){
      if(!action)return;
      var command=clean(action.command);
      var label=clean(action.label||action.name||command||'ACCIÓN');
      if(!command)return;
      var button=document.createElement('button');
      button.type='button';
      button.className='pkContextButton';
      button.textContent=label;
      button.addEventListener('click',function(){send(command)});
      root.appendChild(button);
    });
  }

  function narrateSnapshot(packet){
    var name=clean(packet.room_name||packet.location||'');
    var description=clean(packet.room_description||packet.description||'');
    var roomId=clean(packet.room_id||'');
    var key=(roomId||name)+'|'+description;
    if(!name||key===lastNarratedRoomKey)return;
    lastNarratedRoomKey=key;
    appendFeed(name.toUpperCase(),'location',false);
    if(description)appendFeed(description,'narrative',false);
    var exits=Array.isArray(packet.exits)?packet.exits:[];
    if(exits.length){
      var labels=exits.map(function(row){return clean(typeof row==='string'?row:(row&&(row.name||row.label||row.target)))}).filter(Boolean);
      if(labels.length)appendFeed('Salidas visibles: '+labels.join(', ')+'.','system',false);
    }
  }

  function renderSnapshot(args){
    var packet=packetFrom(args);
    if(packet.status&&packet.status!=='ROOM_SNAPSHOT')return;
    lastSnapshot=packet;
    var name=clean(packet.room_name||packet.location||'Ubicación actual');
    var description=clean(packet.room_description||packet.description||'');
    var roomId=clean(packet.room_id||'');
    var nameNode=byId('pk-room-name');if(nameNode)nameNode.textContent=name||'Ubicación actual';
    var descNode=byId('pk-room-description');if(descNode)descNode.textContent=description||'Sin descripción disponible.';
    var idNode=byId('pk-room-id');if(idNode)idNode.textContent=roomId||'';
    renderMeta(packet);
    renderActions(packet);
    narrateSnapshot(packet);
  }

  function renderContextActions(args){
    var packet=packetFrom(args);
    lastActions=packet;
    renderActions(packet);
  }

  function requestRoomState(){
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',['siza-room-state'],{});return true}catch(e){return false}
  }

  function onText(args,kwargs){
    var value=args&&args.length?String(args[0]||''):'';
    if(value)appendFeed(value,(kwargs&&kwargs.cls==='err')?'error':'world',true);
    if(/you become/i.test(value)){
      window.setTimeout(requestRoomState,120);
      window.setTimeout(requestRoomState,650);
    }
    return true;
  }
  function onPrompt(args){
    var value=args&&args.length?String(args[0]||''):'';
    var node=byId('prompt');
    if(node)node.innerHTML=value;
    return true;
  }
  function onConnectionOpen(){appendSystem('Conectado a POKEROL.');window.setTimeout(requestRoomState,300)}
  function onConnectionClose(){appendFeed('La conexión con POKEROL se cerró.','error',false)}
  function onDefault(cmdname,args){
    if(/^siza_/i.test(String(cmdname||'')))return true;
    appendFeed('Evento no manejado: '+String(cmdname||''),'error',false);
    return true;
  }

  function bindManualEcho(){
    var field=byId('inputfield');
    if(!field||field.dataset.pkEchoBound==='1')return;
    field.dataset.pkEchoBound='1';
    field.addEventListener('keydown',function(ev){
      if(ev.key==='Enter'&&!ev.shiftKey){
        var line=String(field.value||'').trim();
        if(line)appendCommand(line);
      }
    });
  }

  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('siza_room_snapshot',renderSnapshot);
    Evennia.emitter.on('siza_room_state',renderSnapshot);
    Evennia.emitter.on('siza_context_actions',renderContextActions);
    Evennia.emitter.on('text',onText);
    Evennia.emitter.on('prompt',onPrompt);
    Evennia.emitter.on('connection_open',onConnectionOpen);
    Evennia.emitter.on('connection_close',onConnectionClose);
    Evennia.emitter.on('default',onDefault);
    emitterBound=true;
    return true;
  }

  function init(){
    document.title='POKEROL';
    bind('pk-look','look');
    bind('pk-party','equipo');
    bind('pk-bag','bolsa');
    bind('pk-test','solo-prueba');
    bindManualEcho();
    var field=byId('inputfield');
    if(field){
      field.setAttribute('placeholder','Escribe una acción o comando…');
      window.setTimeout(function(){field.focus()},250);
    }
    appendSystem('POKEROL listo. Inicia sesión o crea tu entrenador para comenzar.');
    if(lastSnapshot)renderSnapshot(lastSnapshot);
    else if(lastActions)renderActions(lastActions);
    var tries=0;
    (function retryBind(){
      tries+=1;
      if(bindEmitter()){
        window.setTimeout(requestRoomState,250);
        return;
      }
      if(tries<80)window.setTimeout(retryBind,100);
    })();
  }

  bindEmitter();
  window.PokerolPlayableClientV01=Object.freeze({BUILD:BUILD,send:send,requestRoomState:requestRoomState,renderSnapshot:renderSnapshot,appendFeed:appendFeed});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();