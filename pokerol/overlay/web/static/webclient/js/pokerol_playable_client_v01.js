(function(){
  'use strict';
  var BUILD='0.2.0-playable-room-runtime';
  var emitterBound=false;
  var lastSnapshot=null;
  var lastActions=null;

  function byId(id){return document.getElementById(id)}
  function clean(value){return String(value==null?'':value).replace(/\s+/g,' ').trim()}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }
  function send(command){
    var field=byId('inputfield');
    var button=byId('inputsend');
    if(!field||!button)return false;
    field.value=String(command||'');
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

  function onText(args){
    var value=args&&args.length?String(args[0]||''):'';
    if(/you become/i.test(value)){
      window.setTimeout(requestRoomState,120);
      window.setTimeout(requestRoomState,650);
    }
  }

  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('siza_room_snapshot',renderSnapshot);
    Evennia.emitter.on('siza_room_state',renderSnapshot);
    Evennia.emitter.on('siza_context_actions',renderContextActions);
    Evennia.emitter.on('text',onText);
    emitterBound=true;
    return true;
  }

  function init(){
    document.title='POKEROL';
    bind('pk-look','look');
    bind('pk-party','equipo');
    bind('pk-bag','bolsa');
    bind('pk-test','solo-prueba');
    var field=byId('inputfield');
    if(field){
      field.setAttribute('placeholder','Escribe una acción o comando…');
      window.setTimeout(function(){field.focus()},250);
    }
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
  window.PokerolPlayableClientV01=Object.freeze({BUILD:BUILD,send:send,requestRoomState:requestRoomState,renderSnapshot:renderSnapshot});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
