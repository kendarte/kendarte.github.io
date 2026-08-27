(()=>{
  function norm(s){return String(s||'').replace(/\s+/g,' ').trim().toLocaleLowerCase('es');}
  function addStyle(){
    if(document.getElementById('rivarica-character-art-style')) return;
    const s=document.createElement('style');
    s.id='rivarica-character-art-style';
    s.textContent=`.rivarica-character-art{margin:1rem 0 1.4rem;max-width:520px;border:1px solid rgba(212,177,108,.3);background:rgba(0,0,0,.18);padding:8px;border-radius:10px}.rivarica-character-art img{display:block;width:100%;height:auto;border-radius:6px}.rivarica-character-art figcaption{padding:8px 4px 2px;color:#aaa79f;font:12px/1.45 system-ui,sans-serif}`;
    document.head.appendChild(s);
  }
  function attach(){
    const root=document.getElementById('archive')||document;
    const h=[...root.querySelectorAll('h4')].find(e=>norm(e.textContent).includes('gwen / basiliza'));
    if(!h || h.nextElementSibling?.classList?.contains('rivarica-character-art')) return;
    addStyle();
    const fig=document.createElement('figure');
    fig.className='rivarica-character-art';
    const img=document.createElement('img');
    img.src='art/basiliza-xafrith.webp';
    img.alt='Basiliza Xafrith — ilustración histórica de Summoner Crusade';
    img.loading='lazy';
    const cap=document.createElement('figcaption');
    cap.textContent='Basiliza Xafrith — ilustración existente del Libro de Personajes / Summoner Crusade. Se conserva como antecedente visual; no se presenta como reemplazo automático del diseño canónico actual.';
    fig.append(img,cap);
    h.insertAdjacentElement('afterend',fig);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(attach,250),{once:true});
  else setTimeout(attach,250);
  const mo=new MutationObserver(attach); mo.observe(document.documentElement,{childList:true,subtree:true}); setTimeout(()=>mo.disconnect(),10000);
})();
