'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/webclient/js/pokerol_player_editor_v01.js'),'utf8');
function browser(){
  const nodes={},listeners={},events={},observers=[],sent=[];
  class Node{
    constructor(id){this.id=id;this.dataset={};this.value='';this.hidden=false;this.handlers={};this.styles={};
      this.style={setProperty:(k,v)=>{this.styles[k]=v}};
      this.classList={add(){},remove(){},toggle(){}};
    }
    addEventListener(name,fn){this.handlers[name]=fn}
    appendChild(node){nodes[node.id]=node}
  }
  for(const id of ['pk-player-avatar','pk-player-sprite','pk-stage','pk-player-panel','pk-edit-player','pk-player-save','pk-player-close','pk-player-reset','pk-player-anchor','pk-player-x','pk-player-y','pk-player-scale','pk-player-status'])nodes[id]=new Node(id);
  const context={console,Number,TextEncoder,Uint8Array,btoa:s=>Buffer.from(s,'binary').toString('base64'),
    setTimeout:()=>1,clearTimeout(){},
    MutationObserver:class{constructor(fn){observers.push(fn)}observe(){}},
    document:{body:{},readyState:'complete',documentElement:{dataset:{}},getElementById:id=>nodes[id]||null,
      createElement:()=>new Node(''),addEventListener(){}},
    Evennia:{msg:(...args)=>sent.push(args),emitter:{on:(name,fn)=>{events[name]=fn}}},
    addEventListener:(name,fn)=>{listeners[name]=fn}};
  context.window=context;vm.runInNewContext(source,context);
  return {editor:context.PokerolPlayerEditorV01,nodes,events,sent,
    replace(){nodes['pk-player-avatar']=new Node('pk-player-avatar');delete nodes['pk-player-resize-handle'];observers.forEach(fn=>fn())},
    transition(){listeners['pokerol-room-transition-complete']()}};
}
function packet(character,room,revision,x=63.4,y=118,scale=1.72){return {room_dbref:room,player_editor:{character_dbref:character,scene_x:x,scene_y:y,scene_scale:scale,revision,anchored:false}}}
function check(b,x=63.4,y=118,scale=1.72){
  const a=b.nodes['pk-player-avatar'];assert.equal(a.dataset.pkPlayerX,String(x));assert.equal(a.dataset.pkPlayerY,String(y));assert.equal(a.dataset.pkPlayerScale,String(scale));
  assert.equal(a.styles.width,96*scale+'px');assert.equal(a.styles.height,140*scale+'px');assert.equal(a.styles.transform,'translateX(-50%)');
}
let b=browser();
b.editor.applyPacket(packet(1,101,7));check(b);
for(const room of [102,103,101]){b.editor.applyPacket(packet(1,room,7));b.transition();check(b)}
assert.equal(b.editor.applyPacket(packet(1,103,6,11,94,1)),false);check(b);
assert.equal(b.editor.applyPacket(packet(1,104,0,11,94,1)),false);check(b);
assert.equal(b.editor.applyPacket({room_dbref:105}),false);check(b);
b.replace();check(b);assert.ok(b.nodes['pk-player-avatar'].handlers.pointerdown);
b=browser();b.editor.applyPacket(packet(1,103,7));check(b);
b.editor.applyPacket(packet(2,101,1,27.8,156,.83));check(b,27.8,156,.83);
b.nodes['pk-edit-player'].handlers.click();
b.nodes['pk-player-x'].value='32.1';b.nodes['pk-player-y'].value='125';b.nodes['pk-player-scale'].value='1.25';
b.nodes['pk-player-save'].handlers.click();
const payload=JSON.parse(Buffer.from(b.sent.at(-1)[1][0].split(' ')[1],'base64url').toString());
assert.equal(payload.character_dbref,2);assert.equal(payload.anchored,false);
assert.equal(b.editor.applyPacket(packet(2,102,1,11,94,1)),false);check(b,32.1,125,1.25);
b.events.pokerol_asset_result([{status:'PLAYER_STATE_SAVED',seq:payload.seq,character_dbref:1,layout:{x:1,y:2,scale:3},revision:99}]);check(b,32.1,125,1.25);assert.equal(b.editor.isDirty(),true);
b.events.pokerol_asset_result([{status:'PLAYER_STATE_SAVED',seq:payload.seq,character_dbref:2,layout:{x:32.1,y:125,scale:1.25},revision:2}]);
assert.equal(b.editor.isDirty(),false);b.nodes['pk-player-close'].handlers.click();check(b,32.1,125,1.25);
b.editor.applyPacket(packet(2,103,2,32.1,125,1.25));check(b,32.1,125,1.25);
b.editor.applyPacket(packet(1,101,7));check(b);
console.log('PASS: three Rooms, stale/default packets, DOM replacement, reload, two characters, pending save, wrong-character ACK, confirmed save and close');
