const fs=require('fs'),vm=require('vm');
const context={window:{}};vm.createContext(context);vm.runInContext(fs.readFileSync('siza-core/creature-rules.js','utf8'),context);
const R=context.window.SizaCreatureRules;if(!R)throw new Error('SizaCreatureRules unavailable');
const results=[],test=(name,fn)=>{try{results.push({name,pass:!!fn()})}catch(error){results.push({name,pass:false,error:error.message})}};
function player(){return{battlefield:['a','b','c'],powerCounters:[2,1,0],summonedOn:[1,2,3],ownTurn:4,exhausted:[0,2],equipment:[{id:'blade',target:1},{id:'charm',target:2}],hand:[],graveyard:[]}}

test('addCreature agrega carta contador cero y turno de entrada',()=>{const P={battlefield:['a'],powerCounters:[3],summonedOn:[2],ownTurn:5,equipment:[],exhausted:[],hand:[],graveyard:[]},i=R.addCreature(P,'new');return i===1&&JSON.stringify(P.battlefield)==='["a","new"]'&&JSON.stringify(P.powerCounters)==='[3,0]'&&JSON.stringify(P.summonedOn)==='[2,5]'});
test('removeAt manda al Cementerio y alinea arrays paralelos',()=>{const P=player(),id=R.removeAt(P,1);return id==='b'&&JSON.stringify(P.battlefield)==='["a","c"]'&&JSON.stringify(P.graveyard)==='["b"]'&&JSON.stringify(P.powerCounters)==='[2,0]'&&JSON.stringify(P.summonedOn)==='[1,3]'});
test('removeAt puede devolver a la mano',()=>{const P=player(),id=R.removeAt(P,0,'hand');return id==='a'&&JSON.stringify(P.hand)==='["a"]'&&P.graveyard.length===0});
test('removeAt elimina y rebasa índices agotados',()=>{const P=player();R.removeAt(P,1);return JSON.stringify(P.exhausted)==='[0,1]'});
test('Equipment sobre criatura removida queda sin objetivo',()=>{const P=player();R.removeAt(P,1);return P.equipment[0].target===null});
test('Equipment posterior a criatura removida rebasa su objetivo',()=>{const P=player();R.removeAt(P,1);return P.equipment[1].target===1});
test('Índice inválido no muta estado',()=>{const P=player(),before=JSON.stringify(P),id=R.removeAt(P,9);return id===null&&JSON.stringify(P)===before});

for(const r of results)console.log(`${r.pass?'PASS':'FAIL'} ${r.name}${r.error?` :: ${r.error}`:''}`);const passed=results.filter(r=>r.pass).length;console.log(`SIZA creature state regression: ${passed}/${results.length}`);if(passed!==results.length)process.exit(1);
