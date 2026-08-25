(function(global){
'use strict';

const COLORS=Object.freeze(['U','R','G','W','B']);

function crystalReq(card){
  const req={};
  for(const [key,count] of Object.entries(card?.pips||{}))if(count>0)req[key]=count;
  return req;
}

function spellCost(card){
  if(card?.type==='Land')return 0;
  return Math.max(1,Object.values(crystalReq(card)).reduce((sum,count)=>sum+count,0));
}

function directPlan(player,card){
  const req=crystalReq(card),spent={};
  for(const [key,count] of Object.entries(req)){
    if((player?.crystals?.[key]||0)<count)return null;
    spent[key]=count;
  }
  if(!Object.keys(req).length){
    const options=COLORS.filter(key=>(player?.crystals?.[key]||0)>0);
    return options.length?{kind:'flex',options}:null;
  }
  return {kind:'direct',spent};
}

global.SizaCrystalRules=Object.freeze({COLORS,crystalReq,spellCost,directPlan});
})(window);
