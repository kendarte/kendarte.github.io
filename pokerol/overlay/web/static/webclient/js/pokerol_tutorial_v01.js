(function(){
  'use strict';

  var BUILD='0.1.0-oak-starter-rival';
  var BATTLE_SOURCE='TUTORIAL-RIVAL-1';
  var emitterBound=false;

  function clean(value){return String(value==null?'':value).trim()}
  function packetFrom(args){
    var packet=args&&args.length?args[0]:args;
    if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
    return packet&&typeof packet==='object'?packet:{};
  }
  function client(){return window.PokerolPlayableClientV01||null}
  function show(speaker,text){
    speaker=clean(speaker)||'NARRADOR';text=clean(text);if(!text)return;
    var api=client();
    if(api&&typeof api.setDialogue==='function')api.setDialogue(text,speaker,false);
    if(api&&typeof api.appendFeed==='function')api.appendFeed(speaker.toUpperCase()+': '+text,'narrative',false);
  }
  function requestRoom(){
    var api=client();
    if(api&&typeof api.requestRoomState==='function')api.requestRoomState();
  }
  function onDialogue(args){
    var packet=packetFrom(args);
    show(packet.speaker,packet.text);
    return true;
  }
  function onBattleEnded(args){
    var packet=packetFrom(args);
    if(clean(packet.source_event_id)!==BATTLE_SOURCE)return true;
    var outcome=clean(packet.outcome).toUpperCase();
    var line='Eso estuvo más parejo de lo que esperaba. La próxima lo resolvemos de verdad.';
    if(outcome==='PLAYER_WIN')line='Tch... esta vez ganaste. La próxima no te lo voy a dejar tan fácil.';
    else if(outcome==='PLAYER_LOSS')line='¿Ves? Tener un Pokémon no basta. Tendrás que entrenar si quieres alcanzarme.';
    show('Rival',line);
    window.setTimeout(requestRoom,120);
    window.setTimeout(requestRoom,500);
    return true;
  }
  function bindEmitter(){
    if(emitterBound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_tutorial_dialogue',onDialogue);
    Evennia.emitter.on('pokerol_pokemon_battle_ended',onBattleEnded);
    emitterBound=true;
    return true;
  }
  function init(){
    var tries=0;
    (function wait(){
      tries+=1;
      if(bindEmitter())return;
      if(tries<120)window.setTimeout(wait,100);
    })();
  }

  window.PokerolTutorialV01=Object.freeze({BUILD:BUILD,requestRoomState:requestRoom});
  bindEmitter();
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
