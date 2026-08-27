const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const test=require('node:test');
const vm=require('node:vm');

const root=__dirname;
const sandbox={console,window:{}};
sandbox.window.window=sandbox.window;
vm.createContext(sandbox);
for(const file of ['card-effects.js','card-schema.js','cards.js','crystal-rules.js','manifest-rules.js','decks.js']){
  vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),sandbox,{filename:file});
}

const {SizaCardEffects:effects,SizaCardSchema:schema,SizaCardCatalog:cards,SizaCrystalRules:crystals,SizaManifestRules:manifest,SizaDeckCatalog:decks}=sandbox.window;
const cardById=id=>cards.get(id);

test('el catálogo canónico no conserva cost',()=>{
  for(const card of cards.all())assert.equal(Object.hasOwn(card,'cost'),false,card.id);
  assert.equal(effects.TYPES.includes('cost-reduction'),false);
  assert.equal(effects.TYPES.includes('cost-increase'),false);
});

test('cost legado no crea dificultad ni jugabilidad',()=>{
  const legacy=schema.normalizeCard({id:'legacy',name:'Legado',type:'Instant',cost:99,pips:{U:1}});
  assert.equal(Object.hasOwn(legacy,'cost'),false);
  assert.equal(legacy.difficulty,0);
  assert.equal(schema.validateCard(legacy).valid,false);
  assert.equal(manifest.dcFor(legacy,{mf:2,aff:{U:1}}),Infinity);
  assert.equal(manifest.naturalChance(legacy,{mf:2,aff:{U:1}}),0);
});

test('todos los mazos publicados son legales y tienen 60 cartas',()=>{
  for(const deck of decks.all()){
    const validation=decks.validate(deck,cardById);
    assert.equal(validation.valid,true,`${deck.id}: ${validation.errors.join(', ')}`);
    assert.equal(validation.total,60,deck.id);
    for(const [id,count] of Object.entries(deck.counts)){
      const card=cardById(id);
      if(card.type!=='Land'){
        assert.ok(count<=4,`${deck.id}: ${id}`);
        assert.ok(card.difficulty>0,`${deck.id}: ${id}`);
      }
    }
  }
});

test('los starters tienen pago directo con el perfil U/U/R',()=>{
  const player={crystals:{U:2,R:1}};
  for(const deck of decks.all().filter(deck=>deck.id.startsWith('starter_darkhaven_'))){
    for(const id of Object.keys(deck.counts)){
      const card=cardById(id);
      if(card.type!=='Land')assert.ok(crystals.directPlan(player,card),`${deck.id}: ${id}`);
    }
  }
});

test('Prisma de Servicio se agota al usar su bonificación',()=>{
  const player={artifacts:['dhk_prisma_de_servicio'],artifactExhausted:[]};
  const target=cardById('dhk_familiar_de_practica');
  const first=manifest.bonusSources(player,target,cardById,effects.forEvent);
  assert.equal(first.length,1);
  assert.equal(first[0].effect.exhaustSource,true);
  player.artifactExhausted.push(first[0].index);
  assert.equal(manifest.bonusSources(player,target,cardById,effects.forEvent).length,0);
});

test('Ancla de Retorno no puede elegirse a sí misma',()=>{
  const match={
    player:{battlefield:[],artifacts:['dhk_ancla_de_retorno'],equipment:[]},
    enemy:{battlefield:[],artifacts:[],equipment:[]}
  };
  const targets=effects.otherPermanentTargets(match,'player',null,'artifacts',0);
  assert.equal(targets.some(target=>target.owner==='player'&&target.zone==='artifacts'&&target.index===0),false);
});

test('el pase de prioridad deja la resolución pendiente hasta Continuar',()=>{
  const plan=effects.priorityPassPlan({responder:'enemy'},'enemy');
  assert.equal(plan.pendingResolution,true);
  assert.equal(plan.active,'resolving');
  assert.equal(effects.shouldContinueStackResolution({stack:[{id:'stack'}],pendingChoice:false,over:false},0),true);
});

test('Generator y Arena no consultan card.cost',()=>{
  for(const file of ['../siza-card-generator/app.js','../siza-mobile-test/index.html']){
    const source=fs.readFileSync(path.join(root,file),'utf8');
    assert.equal(/\.cost\b/.test(source),false,file);
  }
});

test('Marea Carmesí no depende de Ofrenda ni de cartas incompatibles',()=>{
  const deck=decks.get('deck_tide_crimson');
  assert.equal(deck.counts.smuggler||0,0);
  assert.equal(deck.counts.leviathan||0,0);
  for(const id of Object.keys(deck.counts)){
    const card=cardById(id);
    if(card.type!=='Land')assert.ok(crystals.directPlan({crystals:{U:2,R:1}},card),id);
  }
});
