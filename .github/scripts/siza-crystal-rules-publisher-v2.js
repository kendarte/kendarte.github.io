const repo=process.env.GH_REPOSITORY,token=process.env.GH_TOKEN;
const headers={'Accept':'application/vnd.github+json','Authorization':`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};

(async()=>{
  const path='.github/scripts/siza-crystal-rules-extraction.js';
  const r=await fetch(`https://api.github.com/repos/${repo}/contents/${path}?ref=main`,{headers});
  if(!r.ok)throw new Error(`GET ${path}: ${r.status} ${await r.text()}`);
  const f=await r.json();
  let source=Buffer.from(f.content.replace(/\n/g,''),'base64').toString('utf8');
  const start=source.indexOf('async function atomicCommit(changes,message){');
  const end=source.indexOf('\n\n(async()=>{',start);
  if(start<0||end<0)throw new Error('atomicCommit block not found');
  const replacement=`async function atomicCommit(changes,message){
  const ordered=Object.keys(changes).filter(path=>path!=='siza-mobile-test/index.html').concat('siza-mobile-test/index.html');
  let lastSha=null;
  for(const path of ordered){
    const current=await getFile(path);
    if(current.text===changes[path]){console.log('UNCHANGED '+path);continue}
    const result=await request(\`${'${api}'}/contents/${'${path}'}\`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:\`${'${message}'}: ${'${path}'}\`,content:Buffer.from(changes[path],'utf8').toString('base64'),sha:current.sha,branch:'main'})});
    lastSha=result.commit.sha;
    console.log('WROTE '+path+' '+lastSha);
  }
  return lastSha;
}`;
  source=source.slice(0,start)+replacement+source.slice(end);
  console.log('Publishing validated crystal extraction through Contents API; runtime index is ordered last.');
  eval(source);
})().catch(e=>{console.error(e.stack||e.message);process.exit(1)});
