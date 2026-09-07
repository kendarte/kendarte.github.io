(function(){
  'use strict';

  var BUILD='0.3.0-oak-event-lifecycle';
  var LAB_ROOM='KANTO-PAL-002';
  var BATTLE_SOURCE='TUTORIAL-RIVAL-1';
  var OAK_SRC='https://play.pokemonshowdown.com/sprites/trainers/oak.png';
  var RIVAL_SRC='https://play.pokemonshowdown.com/sprites/trainers/blue.png';
  var STARTER_IMAGE={
    'PKMN-001':'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png',
    'PKMN-004':'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png',
    'PKMN-007':'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/7.png'
  };
  var STARTER_NAME={'PKMN-001':'Bulbasaur','PKMN-004':'Charmander','PKMN-007':'Squirtle'};
  var emitterBound=false;
  var lastSnapshot={};
  var lastTutorial={};
  var lastRoomId='';
  var enterSentFor='';
  var syncSignature='';
  var stageSeen={};

  function clean(value){return String(value==null?'':value).trim()}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }
  function client(){return window.PokerolPlayableClientV01||null}
  function modal(){return window.PokerolEventModalV01||null}
  function send(line){
    line=clean(line);if(!line)return false;
    if(!window.Evennia||typeof Evennia.msg!=='function')return false;
    try{Evennia.msg('text',[line],{});return true}catch(e){return false}
  }
  function showDialogueBox(speaker,text){
    speaker=clean(speaker)||'NARRADOR';text=clean(text);if(!text)return;
    var api=client();
    if(api&&typeof api.setDialogue==='function')api.setDialogue(text,speaker,false);
    if(api&&typeof api.appendFeed==='function')api.appendFeed(speaker.toUpperCase()+': '+text,'narrative',false);
  }
  function openPacket(packet){
    var api=modal();if(api&&typeof api.open==='function'){api.open(packet);return true}
    return false;
  }
  function requestRoom(){
    var api=client();
    if(api&&typeof api.requestRoomState==='function')api.requestRoomState();
  }
  function roomId(packet){
    return clean(packet.room_id||packet.room&&packet.room.room_id||document.getElementById('pk-room-id')&&document.getElementById('pk-room-id').textContent);
  }
  function challengePacket(){
    var rivalId=clean(lastTutorial.rival_starter_id);
    var rivalName=STARTER_NAME[rivalId]||'su Pokémon';
    return {
      modal_id:'OAK:RIVAL_CHALLENGE',
      kind:'RIVAL_CHALLENGE',
      title:'EL RETO DEL RIVAL',
      speaker:'RIVAL',
      text:'Yo me quedo con '+rivalName+'. ¡Ahora que ambos tenemos Pokémon, te reto a una batalla!',
      media_type:'image',
      media_src:STARTER_IMAGE[rivalId]||RIVAL_SRC,
      caption:rivalName.toUpperCase(),
      blocking:true,
      buttons:[
        {label:'ACEPTAR RETO',command:'tutorial-reto',primary:true},
        {label:'AHORA NO',command:'tutorial-oak snooze'}
      ]
    };
  }
  function chooseReminder(){
    return {
      modal_id:'OAK:CHOOSE_STARTER',
      kind:'TUTORIAL',
      title:'ELIGE TU PRIMER POKÉMON',
      speaker:'PROF. OAK',
      text:'Sobre la mesa hay tres Poké Balls. Toca una para ver al Pokémon que contiene y decide si quieres tomarlo.',
      media_type:'image',
      media_src:OAK_SRC,
      caption:'PROFESOR OAK · LABORATORIO DE PUEBLO PALETA',
      blocking:true,
      buttons:[{label:'VER LAS POKÉ BALLS',close:true,primary:true}]
    };
  }
  function scheduleStageModal(stage,factory){
    window.setTimeout(function(){
      if(roomId(lastSnapshot)!==LAB_ROOM)return;
      if(clean(lastTutorial.stage).toUpperCase()!==stage)return;
      if(lastTutorial.completed)return;
      openPacket(factory());
    },120);
  }
  function syncServerState(rid,stage){
    var sig=[rid,stage,clean(lastTutorial.starter_id),clean(lastTutorial.rival_starter_id),clean(lastTutorial.outcome),lastTutorial.completed?'1':'0'].join('|');
    if(syncSignature===sig)return;
    syncSignature=sig;
    window.setTimeout(function(){send('tutorial-oak sync')},35);
  }
  function handleStage(packet){
    lastSnapshot=packet||{};
    lastTutorial=packet&&packet.tutorial&&typeof packet.tutorial==='object'?packet.tutorial:{};
    var rid=roomId(packet),stage=clean(lastTutorial.stage).toUpperCase();

    if(rid!==lastRoomId){
      lastRoomId=rid;
      enterSentFor='';
      syncSignature='';
      stageSeen={};
    }

    if(rid!==LAB_ROOM||!lastTutorial.enabled){
      enterSentFor='';
      return;
    }

    syncServerState(rid,stage);
    if(lastTutorial.completed){
      enterSentFor='';
      return;
    }

    if(stage==='MEET_OAK'&&lastTutorial.autorun!==false){
      stageSeen={};
      var key=rid+':'+stage;
      if(enterSentFor!==key){
        enterSentFor=key;
        window.setTimeout(function(){send('tutorial-oak enter')},110);
      }
      return;
    }

    enterSentFor='';
    if(stage==='CHOOSE_STARTER'&&!stageSeen.CHOOSE_STARTER){
      stageSeen.CHOOSE_STARTER=true;
      scheduleStageModal('CHOOSE_STARTER',chooseReminder);
    }else if(stage==='RIVAL_CHALLENGE'&&!stageSeen.RIVAL_CHALLENGE){
      stageSeen.RIVAL_CHALLENGE=true;
      scheduleStageModal('RIVAL_CHALLENGE',challengePacket);
    }
  }
  function onSnapshot(args){
    handleStage(packetFrom(args));return true;
  }
  function onDialogue(args){
    var packet=packetFrom(args),speaker=clean(packet.speaker)||'NARRADOR',text=clean(packet.text);
    showDialogueBox(speaker,text);
    if(!text)return true;
    var isOak=/oak/i.test(speaker);
    var isRival=/rival/i.test(speaker);
    if(isRival&&(/mu[eé]strale/i.test(text)||/^¡?vamos,/i.test(text))){return true;}
    var stage=clean(lastTutorial.stage).toUpperCase();
    var media=isOak?OAK_SRC:(isRival?RIVAL_SRC:'');
    var title=isOak?'PROFESOR OAK':(isRival?'RIVAL':'EVENTO');
    var caption='';
    var buttons=[{label:'CONTINUAR',close:true,primary:true}];

    if(isRival&&stage==='RIVAL_CHALLENGE'){
      stageSeen.RIVAL_CHALLENGE=true;
      var rivalId=clean(lastTutorial.rival_starter_id);
      if(STARTER_IMAGE[rivalId])media=STARTER_IMAGE[rivalId];
      caption=(STARTER_NAME[rivalId]||'POKÉMON DEL RIVAL').toUpperCase();
      buttons=[{label:'ACEPTAR RETO',command:'tutorial-reto',primary:true},{label:'AHORA NO',command:'tutorial-oak snooze'}];
    }else if(isOak&&stage==='CHOOSE_STARTER'){
      stageSeen.CHOOSE_STARTER=true;
      caption='ELIGE UNA DE LAS POKÉ BALLS DE LA ESCENA';
    }
    openPacket({
      modal_id:'DIALOGUE:'+Date.now(),
      kind:'DIALOGUE',
      title:title,
      speaker:speaker,
      text:text,
      media_type:media?'image':'',
      media_src:media,
      caption:caption,
      blocking:true,
      buttons:buttons
    });
    return true;
  }
  function onBattleEnded(args){
    var packet=packetFrom(args);
    if(clean(packet.source_event_id)!==BATTLE_SOURCE)return true;
    var outcome=clean(packet.outcome).toUpperCase();
    var line='Eso estuvo más parejo de lo que esperaba. La próxima lo resolvemos de verdad.';
    if(outcome==='PLAYER_WIN')line='Tch... esta vez ganaste. La próxima no te lo voy a dejar tan fácil.';
    else if(outcome==='PLAYER_LOSS')line='¿Ves? Tener un Pokémon no basta. Tendrás que entrenar si quieres alcanzarme.';
    showDialogueBox('Rival',line);
    openPacket({
      modal_id:'OAK:FIRST_BATTLE_RESULT',
      kind:'EVENT_RESULT',
      title:'PRIMERA BATALLA',
      speaker:'RIVAL',
      text:line,
      media_type:'image',
      media_src:RIVAL_SRC,
      caption:outcome.replace(/_/g,' '),
      blocking:true,
      buttons:[{label:'CONTINUAR',close:true,primary:true}]
    });
    send('tutorial-oak finalize');
    window.setTimeout(requestRoom,180);
    window.setTimeout(requestRoom,650);
    return true;
  }
  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_tutorial_dialogue',onDialogue);
    Evennia.emitter.on('pokerol_pokemon_battle_ended',onBattleEnded);
    Evennia.emitter.on('pokerol_room_snapshot',onSnapshot);
    emitterBound=true;
    return true;
  }
  function init(){
    var tries=0;
    (function wait(){
      tries+=1;
      if(bindEmitter())return;
      if(tries<160)window.setTimeout(wait,75);
    })();
  }

  window.PokerolTutorialV01=Object.freeze({BUILD:BUILD,requestRoomState:requestRoom});
  bindEmitter();
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();