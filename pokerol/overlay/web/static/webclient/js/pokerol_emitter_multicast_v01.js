(function(){
  'use strict';

  var BUILD='0.1.0-multicast-emitter';

  function patchEmitter(){
    if(!window.Evennia||!Evennia.emitter||Evennia.emitter.__pkMulticast)return false;

    var emitter=Evennia.emitter;
    var originalOn=typeof emitter.on==='function'?emitter.on.bind(emitter):null;
    var originalOff=typeof emitter.off==='function'?emitter.off.bind(emitter):null;
    if(!originalOn)return false;

    var groups=Object.create(null);

    emitter.on=function(name,listener){
      if(typeof listener!=='function')return;
      var key=String(name||'');
      if(!key)return;
      var group=groups[key];
      if(!group){
        group=[];
        groups[key]=group;
        originalOn(key,function(){
          var args=arguments;
          group.slice().forEach(function(fn){
            try{fn.apply(this,args)}catch(err){if(window.console&&console.error)console.error('[POKEROL emitter]',key,err)}
          },this);
        });
      }
      if(group.indexOf(listener)===-1)group.push(listener);
    };

    emitter.off=function(name,listener){
      var key=String(name||'');
      var group=groups[key];
      if(!group){if(originalOff&&!listener)originalOff(key);return}
      if(typeof listener==='function'){
        var index=group.indexOf(listener);
        if(index!==-1)group.splice(index,1);
        if(group.length)return;
      }
      delete groups[key];
      if(originalOff)originalOff(key);
    };

    emitter.__pkMulticast=true;
    emitter.__pkGroups=groups;
    return true;
  }

  if(window.Evennia){
    var originalInit=typeof Evennia.init==='function'?Evennia.init.bind(Evennia):null;
    if(originalInit&&!Evennia.__pkMulticastInitWrapped){
      Evennia.init=function(opts){
        var result=originalInit(opts);
        patchEmitter();
        return result;
      };
      Evennia.__pkMulticastInitWrapped=true;
    }
    if(Evennia.initialized)patchEmitter();
  }

  window.PokerolEmitterMulticastV01=Object.freeze({BUILD:BUILD,patch:patchEmitter});
})();
