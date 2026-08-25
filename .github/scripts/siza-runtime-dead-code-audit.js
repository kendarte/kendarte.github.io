const acorn=require('acorn');
const fs=require('fs');
const html=fs.readFileSync('siza-mobile-test/index.html','utf8');
const so=html.lastIndexOf('<script>'),sc=html.indexOf('</script>',so);if(so<0||sc<0)throw new Error('main script not found');const code=html.slice(so+8,sc),ast=acorn.parse(code,{ecmaVersion:'latest'}),decl=[];
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='FunctionDeclaration'&&n.id)decl.push(n);for(const[k,v]of Object.entries(n)){if(k==='start'||k==='end')continue;if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object'&&v.type)walk(v)}}walk(ast);
function identifierCount(name){let count=0;function visit(n){if(!n||typeof n!=='object')return;if(n.type==='Identifier'&&n.name===name)count++;for(const[k,v]of Object.entries(n)){if(k==='start'||k==='end')continue;if(Array.isArray(v))v.forEach(visit);else if(v&&typeof v==='object'&&v.type)visit(v)}}visit(ast);return count}
function textCount(name){const esc=name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');return [...html.matchAll(new RegExp(`\\b${esc}\\b`,'g'))].length}
const rows=decl.map(n=>({name:n.id.name,identifiers:identifierCount(n.id.name),text:textCount(n.id.name),start:n.start})).sort((a,b)=>a.name.localeCompare(b.name));
const candidates=rows.filter(x=>x.identifiers===1&&x.text===1);
console.log(`Named function declarations: ${decl.length}`);
console.log(`Conservative zero-reference candidates: ${candidates.length}`);
for(const c of candidates)console.log(`DEAD? ${c.name} | AST=${c.identifiers} | TEXT=${c.text}`);
console.log('--- Functions with exactly one AST identifier but extra text references ---');
for(const c of rows.filter(x=>x.identifiers===1&&x.text>1))console.log(`STRING/HTML? ${c.name} | AST=${c.identifiers} | TEXT=${c.text}`);
