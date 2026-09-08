(function(){
'use strict';
var BUILD='0.1.0-battle-scene-editor';
var battleState=null,sceneState=null,editing=false,selectedId='',bound=false,waiters=[],drag=null;
function byId(id){return document.getElementById(id)}
function text(v){return String(v==null?'':v).trim()}
function num(v,d){v=parseFloat(v);return Number.isFinite(v)?v:d}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function esc(v){return text(v).replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]})}
function packetFrom(args){var p=args&&args.length?args[0]:args;if(Array.isArray(p)&&p.length===1)p=p[0];return p&&typeof p==='object'?p:{}}
function encode(data){var bytes=new TextEncoder().encode(JSON.stringify(data||{})),bin='';for(var i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);return btoa(bin).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')}
function bytes64(bytes){var bin='',step=8192;for(var i=0;i<bytes.length;i+=step){var part=bytes.subarray(i,Math.min(bytes.length,i+step));for(var j=0;j<part.length;j++)bin+=String.fromCharCode(part[j])}return btoa(bin)}
function send(cmd,data){if(!window.Evennia||typeof Evennia.msg!=='function'||!Evennia.isConnected())return false;Evennia.msg('text',[cmd+(data?' '+encode(data):'')],{});return true}
function viewport(){return byId('pkb-battle-viewport')}
function isOpen(){var root=byId('pokerol-pokemon-battle');return !!root&&root.getAttribute('data-open')==='true'}
function fallbackBackground(){var site=battleState&&battleState.site||{},img=site.scene_image;return text(img&&typeof img==='object'?img.src:img)}
function currentBackground(){return text(sceneState&&sceneState.background)||fallbackBackground()}
function applyBackground(){var bg=byId('pkb-battle-bg');if(!bg)return;var src=currentBackground();bg.style.backgroundImage=src?'url("'+src.replace(/"/g,'%22')+'")':''}
function sceneHotspots(){return sceneState&&Array.isArray(sceneState.hotspots)?sceneState.hotspots:[]}
function selected(){var id=selectedId;return sceneHotspots().find(function(r){return text(r.id)===id})||null}
function ensure(){
  var vp=viewport();if(!vp)return false;
  if(!byId('pkb-battle-hotspots')){var layer=document.createElement('div');layer.id='pkb-battle-hotspots';layer.className='pkbBattleHotspotLayer';vp.appendChild(layer)}
  if(!byId('pkb-scene-edit-toggle')){var btn=document.createElement('button');btn.id='pkb-scene-edit-toggle';btn.className='pkbSceneEditToggle';btn.type='button';btn.textContent='EDITAR ESCENA';btn.onclick=function(){editing=!editing;selectedId='';refreshEditor();renderHotspots()};vp.appendChild(btn)}
  if(!byId('pkb-scene-editor')){
    var panel=document.createElement('aside');panel.id='pkb-scene-editor';panel.className='pkbSceneEditor';panel.hidden=true;
    panel.innerHTML=''
      +'<div class="pkbSceneEditorHead"><b>ESCENA DE COMBATE</b><button id="pkb-scene-close" type="button">×</button></div>'
      +'<div class="pkbSceneEditorRow"><button id="pkb-scene-bg-load" type="button">CARGAR FONDO</button><button id="pkb-scene-bg-clear" type="button">QUITAR FONDO</button><input id="pkb-scene-bg-file" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden></div>'
      +'<div class="pkbSceneEditorRow"><button id="pkb-hotspot-add" type="button">+ HOTSPOT</button><button id="pkb-hotspots-save" type="button">GUARDAR HOTSPOTS</button></div>'
      +'<div class="pkbSceneFields" id="pkb-scene-fields">'
        +'<label>NOMBRE<input id="pkb-hotspot-name" type="text" maxlength="96"></label>'
        +'<label>COMANDO<input id="pkb-hotspot-command" type="text" maxlength="500" placeholder="mirar mesa / usar árbol / etc."></label>'
        +'<label>DESCRIPCIÓN<textarea id="pkb-hotspot-description" rows="2" maxlength="6000"></textarea></label>'
        +'<div class="pkbSceneGrid"><label>X<input id="pkb-hotspot-x" type="number" min="0" max="100" step="0.5"></label><label>Y<input id="pkb-hotspot-y" type="number" min="0" max="100" step="0.5"></label><label>ANCHO<input id="pkb-hotspot-w" type="number" min="2" max="80" step="0.5"></label><label>ALTO<input id="pkb-hotspot-h" type="number" min="2" max="80" step="0.5"></label></div>'
        +'<div class="pkbSceneEditorRow"><button id="pkb-hotspot-apply" type="button">APLICAR</button><button id="pkb-hotspot-delete" type="button">BORRAR</button></div>'
      +'</div>'
      +'<div id="pkb-scene-status" class="pkbSceneStatus"></div>';
    vp.appendChild(panel);
    byId('pkb-scene-close').onclick=function(){editing=false;selectedId='';refreshEditor();renderHotspots()};
    byId('pkb-scene-bg-load').onclick=function(){var f=byId('pkb-scene-bg-file');if(f){f.value='';f.click()}};
    byId('pkb-scene-bg-file').onchange=function(){var f=this.files&&this.files[0];if(f)uploadBackground(f)};
    byId('pkb-scene-bg-clear').onclick=clearBackground;
    byId('pkb-hotspot-add').onclick=addHotspot;
    byId('pkb-hotspots-save').onclick=saveHotspots;
    byId('pkb-hotspot-apply').onclick=applyFields;
    byId('pkb-hotspot-delete').onclick=deleteSelected;
  }
  return true;
}
function status(v,error){var n=byId('pkb-scene-status');if(!n)return;n.textContent=text(v);n.dataset.error=error?'true':'false'}
function refreshEditor(){if(!ensure())return;var panel=byId('pkb-scene-editor'),toggle=byId('pkb-scene-edit-toggle');panel.hidden=!editing;if(toggle)toggle.textContent=editing?'SALIR EDICIÓN':'EDITAR ESCENA';var row=selected();var fields=byId('pkb-scene-fields');if(fields)fields.dataset.selected=row?'true':'false';if(!row)return;byId('pkb-hotspot-name').value=text(row.name);byId('pkb-hotspot-command').value=text(row.command);byId('pkb-hotspot-description').value=text(row.description);byId('pkb-hotspot-x').value=num(row.x,50);byId('pkb-hotspot-y').value=num(row.y,50);byId('pkb-hotspot-w').value=num(row.width,12);byId('pkb-hotspot-h').value=num(row.height,12)}
function bindHotspot(el,row){
  el.onclick=function(ev){ev.stopPropagation();if(editing){selectedId=text(row.id);refreshEditor();renderHotspots();return}if(text(row.command))send(text(row.command))};
  el.onpointerdown=function(ev){if(!editing)return;ev.preventDefault();ev.stopPropagation();selectedId=text(row.id);var vp=viewport(),rect=vp.getBoundingClientRect();drag={id:selectedId,pid:ev.pointerId,rect:rect,dx:ev.clientX-(rect.left+rect.width*num(row.x,50)/100),dy:ev.clientY-(rect.top+rect.height*num(row.y,50)/100)};try{el.setPointerCapture(ev.pointerId)}catch(e){};refreshEditor()};
  el.onpointermove=function(ev){if(!drag||drag.pid!==ev.pointerId||drag.id!==text(row.id))return;var x=clamp((ev.clientX-drag.rect.left-drag.dx)/drag.rect.width*100,0,100),y=clamp((ev.clientY-drag.rect.top-drag.dy)/drag.rect.height*100,0,100);row.x=x;row.y=y;el.style.left=x+'%';el.style.top=y+'%';if(selectedId===text(row.id)){byId('pkb-hotspot-x').value=x.toFixed(1);byId('pkb-hotspot-y').value=y.toFixed(1)}};
  el.onpointerup=function(ev){if(drag&&drag.pid===ev.pointerId)drag=null};
}
function renderHotspots(){if(!ensure())return;var layer=byId('pkb-battle-hotspots');layer.innerHTML='';layer.dataset.editing=editing?'true':'false';sceneHotspots().forEach(function(row){if(row.hidden&&!editing)return;var el=document.createElement('button');el.type='button';el.className='pkbBattleHotspot';if(text(row.id)===selectedId)el.classList.add('pkbSelectedBattleHotspot');el.dataset.hotspotId=text(row.id);el.style.left=clamp(num(row.x,50),0,100)+'%';el.style.top=clamp(num(row.y,50),0,100)+'%';el.style.width=clamp(num(row.width,12),2,80)+'%';el.style.height=clamp(num(row.height,12),2,80)+'%';el.innerHTML='<span>'+esc(row.name||'HOTSPOT')+'</span>';bindHotspot(el,row);layer.appendChild(el)})}
function addHotspot(){if(!sceneState)sceneState={hotspots:[]};if(!Array.isArray(sceneState.hotspots))sceneState.hotspots=[];var id='BATTLE-HOTSPOT-'+Date.now().toString(36).toUpperCase();sceneState.hotspots.push({id:id,name:'HOTSPOT',command:'',description:'',x:50,y:50,width:12,height:12,hidden:false,target_dbref:null});selectedId=id;refreshEditor();renderHotspots();status('Hotspot creado. Ajuste y guarde.',false)}
function applyFields(){var row=selected();if(!row)return;row.name=text(byId('pkb-hotspot-name').value)||'HOTSPOT';row.command=text(byId('pkb-hotspot-command').value);row.description=text(byId('pkb-hotspot-description').value);row.x=clamp(num(byId('pkb-hotspot-x').value,row.x),0,100);row.y=clamp(num(byId('pkb-hotspot-y').value,row.y),0,100);row.width=clamp(num(byId('pkb-hotspot-w').value,row.width),2,80);row.height=clamp(num(byId('pkb-hotspot-h').value,row.height),2,80);renderHotspots();status('Cambios aplicados. Pulse GUARDAR HOTSPOTS.',false)}
function deleteSelected(){if(!selectedId||!sceneState)return;sceneState.hotspots=sceneHotspots().filter(function(r){return text(r.id)!==selectedId});selectedId='';refreshEditor();renderHotspots();status('Hotspot quitado. Pulse GUARDAR HOTSPOTS.',false)}
function saveHotspots(){applyFields();if(!send('pokerol-battle-scene-save',{hotspots:sceneHotspots()})){status('No se pudo enviar el guardado.',true);return}status('GUARDANDO…',false)}
function requestState(){send('pokerol-battle-scene-state')}
function waitFor(test,timeout){return new Promise(function(resolve,reject){var w={test:test,resolve:resolve,reject:reject,timer:null};w.timer=setTimeout(function(){var i=waiters.indexOf(w);if(i>=0)waiters.splice(i,1);reject(new Error('El servidor no confirmó la carga.'))},timeout||15000);waiters.push(w)})}
function onResult(args){var p=packetFrom(args);waiters.slice().forEach(function(w){var ok=false;try{ok=w.test(p)}catch(e){}if(!ok)return;var i=waiters.indexOf(w);if(i>=0)waiters.splice(i,1);clearTimeout(w.timer);if(p.status==='ERROR')w.reject(new Error(text(p.message)||'Error'));else w.resolve(p)});if(p.status==='BATTLE_SCENE_SAVED')status('HOTSPOTS GUARDADOS',false);else if(p.status==='ERROR')status(text(p.message)||'ERROR',true)}
function uploadBackground(file){
  if(!/^image\/(png|jpeg|webp|gif)$/i.test(file.type||'')||file.size<=0||file.size>8*1024*1024){status('Imagen inválida o mayor a 8 MB.',true);return}
  status('CARGANDO FONDO…',false);
  send('pokerol-battle-scene-asset-begin',{mime:file.type,size:file.size,name:file.name||''});
  waitFor(function(p){return p.status==='UPLOAD_READY'||p.status==='ERROR'},15000).then(function(ready){return file.arrayBuffer().then(function(buffer){var bytes=new Uint8Array(buffer),offset=0,index=0,chunk=Number(ready.chunk_size)||32768;function next(){if(offset>=bytes.length){send('pokerol-battle-scene-asset-finish',{token:ready.token});return waitFor(function(p){return (p.status==='UPLOAD_DONE'&&p.token===ready.token)||p.status==='ERROR'},20000)}var part=bytes.subarray(offset,Math.min(bytes.length,offset+chunk)),idx=index;send('pokerol-battle-scene-asset-chunk',{token:ready.token,index:idx,data:bytes64(part)});return waitFor(function(p){return (p.status==='CHUNK_OK'&&p.token===ready.token&&Number(p.index)===idx)||p.status==='ERROR'},15000).then(function(){offset+=part.length;index+=1;return next()})}return next()})}).then(function(){status('BATTLE BACKGROUND GUARDADO',false);requestState()}).catch(function(err){status(err.message||'No se pudo cargar el fondo.',true)})
}
function clearBackground(){if(!send('pokerol-battle-scene-asset-clear')){status('No se pudo enviar.',true);return}status('QUITANDO FONDO…',false)}
function onScene(args){sceneState=packetFrom(args);applyBackground();renderHotspots();refreshEditor()}
function onBattle(args){battleState=packetFrom(args);window.setTimeout(function(){if(!isOpen())return;ensure();applyBackground();renderHotspots();refreshEditor();requestState()},0)}
function onEnded(){editing=false;selectedId='';battleState=null;var p=byId('pkb-scene-editor');if(p)p.hidden=true}
function bind(){if(bound)return true;if(!window.Evennia||!Evennia.emitter||typeof Evennia.emitter.on!=='function')return false;Evennia.emitter.on('pokerol_pokemon_battle_state',onBattle);Evennia.emitter.on('pokerol_battle_scene_state',onScene);Evennia.emitter.on('pokerol_battle_scene_result',onResult);Evennia.emitter.on('pokerol_pokemon_battle_ended',onEnded);bound=true;return true}
function init(){var tries=0;(function retry(){tries++;if(bind())return;if(tries<100)setTimeout(retry,100)})()}
window.PokerolBattleSceneEditorV01=Object.freeze({BUILD:BUILD,requestState:requestState,getState:function(){return sceneState},render:renderHotspots});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();