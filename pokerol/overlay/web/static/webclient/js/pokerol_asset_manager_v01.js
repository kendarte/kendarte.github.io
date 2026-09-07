(function(){
  'use strict';

  var BUILD='0.1.0-persistent-assets';
  var waiters=[];
  var bound=false;

  function clean(v){return String(v==null?'':v).trim()}
  function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
  function encodePayload(data){
    var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';
    for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function bytesToBase64(bytes){
    var bin='',step=8192;
    for(var i=0;i<bytes.length;i+=step){
      var slice=bytes.subarray(i,Math.min(bytes.length,i+step));
      for(var j=0;j<slice.length;j++)bin+=String.fromCharCode(slice[j]);
    }
    return btoa(bin);
  }
  function send(command,data){
    if(!window.Evennia||typeof Evennia.msg!=='function')throw new Error('POKEROL no está conectado.');
    Evennia.msg('text',[command+' '+encodePayload(data)],{});
  }
  function onResult(args){
    var packet=packetFrom(args);
    if(!packet.status)return true;
    var copy=waiters.slice();
    copy.forEach(function(w){
      var matched=false;
      try{matched=w.test(packet)}catch(e){}
      if(!matched)return;
      var index=waiters.indexOf(w);if(index>=0)waiters.splice(index,1);
      clearTimeout(w.timer);
      if(packet.status==='ERROR')w.reject(new Error(clean(packet.message)||'Error de asset.'));else w.resolve(packet);
    });
    return true;
  }
  function waitFor(test,timeout){
    return new Promise(function(resolve,reject){
      var w={test:test,resolve:resolve,reject:reject,timer:null};
      w.timer=setTimeout(function(){var i=waiters.indexOf(w);if(i>=0)waiters.splice(i,1);reject(new Error('El servidor no confirmó la carga.'))},timeout||15000);
      waiters.push(w);
    });
  }
  function bindEmitter(){
    if(bound)return true;
    if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;
    Evennia.emitter.on('pokerol_asset_result',onResult);
    bound=true;return true;
  }
  function ensureBound(){
    if(bindEmitter())return Promise.resolve(true);
    return new Promise(function(resolve,reject){var tries=0;(function wait(){tries++;if(bindEmitter()){resolve(true);return}if(tries>100){reject(new Error('No se pudo conectar el gestor de assets.'));return}setTimeout(wait,50)})()});
  }
  function uploadFile(meta,file,onProgress){
    if(!file)return Promise.reject(new Error('No hay archivo.'));
    if(!/^image\/(png|jpeg|webp|gif)$/i.test(file.type||''))return Promise.reject(new Error('Formato de imagen no permitido.'));
    if(file.size<=0||file.size>8*1024*1024)return Promise.reject(new Error('La imagen debe pesar menos de 8 MB.'));
    return ensureBound().then(function(){
      send('pokerol-asset-begin',{kind:meta.kind,dbref:meta.dbref||null,hotspot_id:meta.hotspot_id||'',mime:file.type,size:file.size,name:file.name||''});
      return waitFor(function(p){return p.status==='UPLOAD_READY'||p.status==='ERROR'},15000);
    }).then(function(ready){
      var token=ready.token,chunkSize=Number(ready.chunk_size)||32768;
      return file.arrayBuffer().then(function(buffer){
        var bytes=new Uint8Array(buffer),index=0,offset=0;
        function next(){
          if(offset>=bytes.length){
            send('pokerol-asset-finish',{token:token});
            return waitFor(function(p){return (p.token===token&&p.status==='UPLOAD_DONE')||p.status==='ERROR'},20000);
          }
          var chunk=bytes.subarray(offset,Math.min(bytes.length,offset+chunkSize));
          var thisIndex=index;
          send('pokerol-asset-chunk',{token:token,index:thisIndex,data:bytesToBase64(chunk)});
          return waitFor(function(p){return (p.token===token&&p.status==='CHUNK_OK'&&Number(p.index)===thisIndex)||p.status==='ERROR'},15000).then(function(){
            offset+=chunk.length;index+=1;
            if(typeof onProgress==='function')onProgress(Math.min(1,offset/bytes.length));
            return next();
          });
        }
        return next();
      });
    });
  }
  function clearAsset(meta){
    return ensureBound().then(function(){
      send('pokerol-asset-clear',{kind:meta.kind,dbref:meta.dbref||null,hotspot_id:meta.hotspot_id||''});
      return waitFor(function(p){return p.status==='ASSET_CLEARED'||p.status==='ERROR'},15000);
    });
  }

  window.PokerolAssetManagerV01=Object.freeze({BUILD:BUILD,uploadFile:uploadFile,clearAsset:clearAsset,send:send});
  ensureBound().catch(function(){});
})();
