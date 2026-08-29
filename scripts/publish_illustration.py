from pathlib import Path
import base64

root = Path('.')
tmp = root / '.tmp_illustration'


def decode_parts(prefix: str, destination: Path):
    parts = sorted(tmp.glob(f'{prefix}.part*'))
    if not parts:
        raise RuntimeError(f'No {prefix} chunks found')
    payload = ''.join(p.read_text(encoding='utf-8') for p in parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(base64.b64decode(payload))


media_dir = root / 'media' / 'illustration'
decode_parts('proc', media_dir / 'process-atlas.webp')
decode_parts('gal', media_dir / 'gallery-atlas.webp')

illustration_dir = root / 'illustration'
illustration_dir.mkdir(parents=True, exist_ok=True)
page = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kendall Angulo — Illustration & Visual Development</title>
  <meta name="description" content="Character illustration, visual development, environment studies and technical design work by Kendall Angulo.">
  <link rel="canonical" href="https://kendarte.github.io/illustration/">
  <link rel="icon" href="/favicon.svg">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .ill-hero{padding-block:clamp(70px,9vw,140px);display:grid;grid-template-columns:.8fr 1.2fr;gap:clamp(36px,7vw,95px);align-items:center}
    .ill-hero h1{margin:0;font-size:clamp(52px,7vw,106px);line-height:.91;letter-spacing:-.065em;font-weight:560}
    .ill-hero h1 em{font-style:normal;color:var(--acid)}
    .ill-hero p:not(.eyebrow){max-width:650px;color:var(--muted);font-size:18px;line-height:1.7}
    .hero-panel,.art-panel{margin:0;border:1px solid var(--line);background:#090b0c;overflow:hidden;cursor:zoom-in}
    .hero-panel img,.art-panel img{display:block;width:100%;height:auto}
    .ill-section{padding-block:clamp(82px,10vw,150px);border-top:1px solid var(--line)}
    .stage-labels{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);border-top:0}
    .stage-labels span{padding:13px 15px;border-right:1px solid var(--line);font-family:var(--font-geist-mono),monospace;font-size:10px;letter-spacing:.09em;text-transform:uppercase}
    .stage-labels span:last-child{border-right:0}
    .gallery-note{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
    .gallery-note span{padding:8px 10px;border:1px solid var(--line);font-size:10px;color:#c3cbc7}
    .gallery-additions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:22px}
    .gallery-card{margin:0;border:1px solid var(--line);background:var(--panel);overflow:hidden;cursor:zoom-in}
    .gallery-card img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover}
    .gallery-card figcaption{display:flex;justify-content:space-between;gap:18px;padding:14px 16px}
    .gallery-card figcaption span{color:var(--muted);font-size:11px}
    .owner-tools{position:fixed;right:18px;bottom:18px;z-index:80;display:none;padding:11px 14px;border:1px solid var(--acid);background:#0b0d0e;color:var(--acid);font:700 11px var(--font-geist-mono),monospace;letter-spacing:.08em;text-transform:uppercase}
    .owner-tools.on{display:block}
    .lightbox{position:fixed;inset:0;z-index:100;display:none;place-items:center;background:rgba(0,0,0,.95);padding:28px}
    .lightbox.open{display:grid}
    .lightbox img{max-width:96vw;max-height:88vh;width:auto;height:auto;object-fit:contain}
    .lightbox button{position:absolute;right:18px;top:18px;border:1px solid rgba(255,255,255,.4);background:#111;color:white;padding:10px 13px;cursor:pointer}
    @media(max-width:900px){.ill-hero{grid-template-columns:1fr}.gallery-additions{grid-template-columns:1fr}.stage-labels span{font-size:8px;padding:10px 6px}}
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="site-header">
    <a class="brand" href="/illustration/" aria-label="Kendall Angulo illustration portfolio"><span class="brand-mark">KA</span><span class="brand-copy"><strong>Kendall Angulo</strong><small>Illustration &amp; visual development</small></span></a>
    <nav aria-label="Illustration navigation"><a href="#process">Process</a><a href="#gallery">Gallery</a><a href="/3d/">3D</a><a href="/">Main Portfolio</a><a href="/Kendall_Angulo_Jhonson_CV_2026.pdf">CV</a></nav>
    <a class="header-cta" href="mailto:Kendarte@gmail.com">Contact</a>
  </header>

  <main id="main-content">
    <section class="ill-hero section-shell">
      <div><p class="eyebrow"><span></span> Illustration · visual development</p><h1>Visual Development — <em>Character Illustration.</em></h1><p>This is the dedicated illustration page: process documentation first, followed by the rest of the selected illustration work.</p></div>
      <figure class="hero-panel zoomable"><img src="/media/illustration/gallery-atlas.webp" alt="Selected illustration and visual development gallery"></figure>
    </section>

    <section class="ill-section section-shell" id="process">
      <div class="section-heading"><div><p class="eyebrow"><span></span> Process documentation</p><h2>From line work to final presentation.</h2></div><p>The three stages are shown at full width instead of being squeezed into the homepage card.</p></div>
      <figure class="art-panel zoomable"><img src="/media/illustration/process-atlas.webp" alt="Line art, color pass and final lighting stages"></figure>
      <div class="stage-labels"><span>01 · Line Art</span><span>02 · Color Pass</span><span>03 · Final Lighting</span></div>
    </section>

    <section class="ill-section section-shell" id="gallery">
      <div class="section-heading"><div><p class="eyebrow"><span></span> Selected illustration gallery</p><h2>The rest of the visual-development work.</h2></div><p>Dársena Fish, Faro Ahogado, FF-01 Faro de Caza, character studies and Servidor Ahogado pieces are all shown here.</p></div>
      <figure class="art-panel zoomable"><img src="/media/illustration/gallery-atlas.webp" alt="Seven selected illustration and visual development pieces"></figure>
      <div class="gallery-note"><span>Dársena Fish</span><span>Faro Ahogado</span><span>FF-01 Faro de Caza</span><span>Port Characters</span><span>Servidor Ahogado</span><span>Nereida Voss</span><span>Character Studies</span></div>
      <div class="gallery-additions" id="owner-additions"><!-- OWNER: paste additional generated gallery-card blocks here. --></div>
    </section>
  </main>

  <footer><span>© 2026 Kendall Angulo Jhonson</span><span>Illustration · visual development</span><a href="#main-content">Back to top ↑</a></footer>
  <a class="owner-tools" id="ownerTools" href="/admin/">Owner Admin</a>
  <div class="lightbox" id="lightbox" aria-hidden="true"><button id="closeLightbox" type="button">Close ×</button><img id="lightboxImg" alt=""></div>
  <script>
    if(localStorage.getItem('kaPortfolioOwner')==='1') document.getElementById('ownerTools').classList.add('on');
    const lb=document.getElementById('lightbox'), li=document.getElementById('lightboxImg');
    document.querySelectorAll('.zoomable').forEach(el=>el.addEventListener('click',()=>{const im=el.querySelector('img');li.src=im.src;li.alt=im.alt;lb.classList.add('open');lb.setAttribute('aria-hidden','false')}));
    function closeLB(){lb.classList.remove('open');lb.setAttribute('aria-hidden','true');li.src=''}
    document.getElementById('closeLightbox').addEventListener('click',closeLB);lb.addEventListener('click',e=>{if(e.target===lb)closeLB()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLB()});
  </script>
</body>
</html>
'''
(illustration_dir / 'index.html').write_text(page, encoding='utf-8')

home = root / 'index.html'
html = home.read_text(encoding='utf-8')
start_marker = '    <section class="work-section section-shell" id="visual-work">'
end_marker = '    <section class="capabilities-section section-shell" id="siza">'
start = html.find(start_marker)
end = html.find(end_marker)
if start == -1 or end == -1 or end <= start:
    raise RuntimeError('Visual work section markers not found')

replacement = '''    <section class="work-section section-shell" id="visual-work">
      <div class="section-heading"><div><p class="eyebrow"><span></span> Visual work</p><h2>3D &amp; visual development.</h2></div><p>Dedicated visual portfolios, separated from the gameplay case studies.</p></div>
      <div class="project-list">
        <article class="project-card">
          <a class="project-visual" href="/3d/"><img src="/media/3d/ai-workflow.webp" alt="3D character rendering and AI animation workflow"><span class="project-index">04</span><span class="project-status">3D portfolio</span></a>
          <div class="project-content"><div class="project-meta"><span>3D character work</span><span>Rendering · animation</span></div><h3><a href="/3d/">3D Portfolio</a></h3><p>Stylized character work, costume and armor variation, props, rendering and a 3D-to-AI animation workflow.</p><a class="text-link" href="/3d/">Open 3D portfolio <span>↗</span></a></div>
        </article>
        <article class="project-card">
          <a class="project-visual" href="/illustration/"><img src="/media/illustration/gallery-atlas.webp" alt="Illustration and visual development gallery"><span class="project-index">05</span><span class="project-status">Illustration portfolio</span></a>
          <div class="project-content"><div class="project-meta"><span>Character illustration</span><span>Visual development</span></div><h3><a href="/illustration/">Visual Development — Character Illustration</a></h3><p>Dedicated illustration page with the line-art → color → final-lighting process and the selected illustration gallery.</p><ul class="tag-list"><li>Line Art</li><li>Color Design</li><li>Character</li><li>Environment</li><li>Technical Design</li></ul><a class="text-link" href="/illustration/">Open illustration portfolio <span>↗</span></a></div>
        </article>
      </div>
    </section>

'''
html = html[:start] + replacement + html[end:]
home.write_text(html, encoding='utf-8')
