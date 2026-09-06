(function(){
  'use strict';

  var BUILD='0.1.0-trainer-sprite-editor';
  var DB_NAME='pokerol_trainer_sprite_v1';
  var STORE='sprites';
  var defaultMaleSrc='';
  var objectUrls={};
  var applying=false;
  var observer=null;

  function byId(id){return document.getElementById(id)}
  function clean(v){return String(v==null?'':v).trim()}
  function lastUser(){try{return clean(localStorage.getItem('pokerol.last_user'))}catch(e){return ''}}
  function profile(){
    var user=lastUser();if(!user)return {};
    try{return JSON.parse(localStorage.getItem('pokerol.profile.'+user.toLowerCase())||'{}')||{}}catch(e){return {}}
  }
  function activeGender(){var g=clean(profile().gender).toLowerCase();return g==='girl'?'girl':'boy'}

  function openDb(){
    return new Promise(function(resolve,reject){
      var req=indexedDB.open(DB_NAME,1);
      req.onupgradeneeded=function(e){var db=e.target.result;if(!db.objectStoreNames.contains(STORE))db.createObjectStore(STORE,{keyPath:'gender'})};
      req.onsuccess=function(){resolve(req.result)};
      req.onerror=function(){reject(req.error)};
    });
  }
  function getSprite(gender){
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var req=db.transaction(STORE,'readonly').objectStore(STORE).get(gender);
      req.onsuccess=function(){resolve(req.result||null)};
      req.onerror=function(){reject(req.error)};
    })});
  }
  function putSprite(gender,file){
    var row={gender:gender,blob:file,name:file.name||'',type:file.type||'',updatedAt:Date.now()};
    return openDb().then(function(db){return new Promise(function(resolve,reject){
      var tx=db.transaction(STORE,'readwrite');tx.objectStore(STORE).put(row);
      tx.oncomplete=function(){resolve(row)};tx.onerror=function(){reject(tx.error)};
    })});
  }
  function urlFor(gender,blob){
    if(objectUrls[gender]){try{URL.revokeObjectURL(objectUrls[gender])}catch(e){}}
    objectUrls[gender]=URL.createObjectURL(blob);return objectUrls[gender];
  }

  function normalizeGameSprite(img){
    if(!img)return;
    img.style.width='100%';img.style.height='100%';img.style.maxWidth='100%';
    img.style.objectFit='contain';img.style.objectPosition='center bottom';img.style.imageRendering='pixelated';
  }
  function setGameSrc(src){
    var img=byId('pk-player-sprite');if(!img||!src)return;
    applying=true;img.src=src;normalizeGameSprite(img);
    setTimeout(function(){applying=false;refreshPlayerPanelPreview()},0);
  }
  function applyStoredSprite(gender){
    gender=gender||activeGender();
    return getSprite(gender).then(function(row){
      if(row&&row.blob){setGameSrc(urlFor(gender,row.blob));return true}
      if(gender==='boy'&&defaultMaleSrc){setGameSrc(defaultMaleSrc);return true}
      refreshPlayerPanelPreview();return false;
    }).catch(function(){refreshPlayerPanelPreview();return false});
  }

  function makePlaceholder(slot,label){
    var p=slot.querySelector('.pkGenderSpritePlaceholder');
    if(!p){p=document.createElement('div');p.className='pkGenderSpritePlaceholder';p.textContent=label||'CARGAR SPRITE';slot.appendChild(p)}
    p.hidden=false;return p;
  }
  function showGenderImage(img,src,slot){
    if(!img||!src)return false;
    var placeholder=slot&&slot.querySelector('.pkGenderSpritePlaceholder');
    img.hidden=false;img.classList.remove('pkSpriteBroken');
    img.onerror=function(){img.hidden=true;img.classList.add('pkSpriteBroken');if(slot)makePlaceholder(slot,'CARGAR SPRITE')};
    img.onload=function(){img.hidden=false;img.classList.remove('pkSpriteBroken');if(placeholder)placeholder.hidden=true};
    img.src=src;return true;
  }
  function loadGenderPreview(gender,button){
    if(!button)return;
    var img=button.querySelector('.pkGenderSprite'),slot=button.querySelector('.pkGenderSpriteSlot');if(!img||!slot)return;
    getSprite(gender).then(function(row){
      if(row&&row.blob){showGenderImage(img,urlFor('preview-'+gender,row.blob),slot);return}
      if(gender==='boy'&&defaultMaleSrc){showGenderImage(img,defaultMaleSrc,slot);return}
      if(!img.getAttribute('src')){img.hidden=true;makePlaceholder(slot,'CARGAR SPRITE')}
    }).catch(function(){if(!img.getAttribute('src')){img.hidden=true;makePlaceholder(slot,'CARGAR SPRITE')}});
  }
  function saveFromInput(gender,input){
    var file=input&&input.files&&input.files[0];if(!file)return;
    if(!/^image\/(png|webp|jpeg|gif)$/i.test(file.type||'')){input.value='';return}
    putSprite(gender,file).then(function(){
      var button=byId(gender==='girl'?'pk-gender-girl':'pk-gender-boy');
      loadGenderPreview(gender,button);
      if(activeGender()===gender)setGameSrc(urlFor(gender,file));
      refreshPlayerPanelPreview();input.value='';
    }).catch(function(){input.value=''})
  }

  function enhanceGenderButton(gender,id){
    var button=byId(id);if(!button||button.dataset.pkSpriteEditor==='1')return;
    button.dataset.pkSpriteEditor='1';button.style.position='relative';
    var img=button.querySelector('.pkGenderSprite');
    if(img&&!img.parentNode.classList.contains('pkGenderSpriteSlot')){
      var slot=document.createElement('div');slot.className='pkGenderSpriteSlot';img.parentNode.insertBefore(slot,img);slot.appendChild(img);
    }
    var slot2=button.querySelector('.pkGenderSpriteSlot');
    var badge=document.createElement('span');badge.className='pkGenderUploadBadge';badge.textContent='CARGAR SPRITE';badge.setAttribute('role','button');badge.tabIndex=0;
    button.appendChild(badge);
    var input=document.createElement('input');input.type='file';input.accept='image/png,image/webp,image/jpeg,image/gif';input.className='pkTrainerSpriteFile';input.hidden=true;
    button.parentNode.appendChild(input);
    function openFile(ev){if(ev){ev.preventDefault();ev.stopPropagation()}input.click()}
    badge.addEventListener('pointerdown',function(ev){ev.preventDefault();ev.stopPropagation()});
    badge.addEventListener('click',openFile);
    badge.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){openFile(ev)}});
    input.addEventListener('change',function(){saveFromInput(gender,input)});
    button.addEventListener('click',function(){setTimeout(function(){applyStoredSprite(gender)},0)});
    if(img){img.addEventListener('error',function(){img.hidden=true;if(slot2)makePlaceholder(slot2,'CARGAR SPRITE')})}
    loadGenderPreview(gender,button);
  }
  function enhanceGenderGrid(){
    if(!document.querySelector('.pkGenderGrid'))return;
    enhanceGenderButton('boy','pk-gender-boy');enhanceGenderButton('girl','pk-gender-girl');
  }

  function refreshPlayerPanelPreview(){
    var preview=byId('pk-player-sprite-preview'),game=byId('pk-player-sprite');if(!preview||!game)return;
    var src=game.currentSrc||game.getAttribute('src')||game.src||'';
    if(src){preview.src=src;preview.hidden=false}else{preview.hidden=true}
  }
  function enhancePlayerPanel(){
    var panel=byId('pk-player-panel');if(!panel||panel.dataset.pkSpriteEditor==='1')return;
    panel.dataset.pkSpriteEditor='1';
    var head=panel.querySelector('.pkPlayerPanelHead');
    var editor=document.createElement('div');editor.className='pkPlayerSpriteEditor';
    editor.innerHTML='<div class="pkPlayerSpritePreviewFrame"><img id="pk-player-sprite-preview" alt="Sprite actual del entrenador"></div><button id="pk-player-sprite-load" type="button">CARGAR SPRITE</button><input id="pk-player-sprite-file" class="pkTrainerSpriteFile" type="file" accept="image/png,image/webp,image/jpeg,image/gif" hidden>';
    if(head&&head.nextSibling)panel.insertBefore(editor,head.nextSibling);else panel.appendChild(editor);
    var load=byId('pk-player-sprite-load'),input=byId('pk-player-sprite-file');
    if(load&&input)load.addEventListener('click',function(){input.click()});
    if(input)input.addEventListener('change',function(){saveFromInput(activeGender(),input)});
    refreshPlayerPanelPreview();
  }

  function bindGameSprite(){
    var img=byId('pk-player-sprite');if(!img||img.dataset.pkSpriteEditor==='1')return;
    img.dataset.pkSpriteEditor='1';
    if(!defaultMaleSrc)defaultMaleSrc=img.getAttribute('src')||img.src||'';
    normalizeGameSprite(img);
    new MutationObserver(function(){
      if(applying)return;
      getSprite(activeGender()).then(function(row){if(row&&row.blob)setGameSrc(urlFor(activeGender(),row.blob));else refreshPlayerPanelPreview()}).catch(refreshPlayerPanelPreview);
    }).observe(img,{attributes:true,attributeFilter:['src']});
    img.addEventListener('load',refreshPlayerPanelPreview);
  }
  function scan(){bindGameSprite();enhanceGenderGrid();enhancePlayerPanel()}
  function init(){
    bindGameSprite();scan();
    observer=new MutationObserver(function(){scan()});
    observer.observe(document.documentElement,{childList:true,subtree:true});
    setTimeout(function(){applyStoredSprite(activeGender())},150);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
  window.PokerolTrainerSpriteEditorV01={BUILD:BUILD,applyStoredSprite:applyStoredSprite,refresh:scan};
})();