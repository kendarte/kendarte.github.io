from pathlib import Path
import base64

root = Path('.')
parts = sorted((root / '.tmp_illustration').glob('page.part*'))
if not parts:
    raise RuntimeError('No illustration page chunks found')

page = ''.join(p.read_text(encoding='utf-8') for p in parts)
illustration_dir = root / 'illustration'
illustration_dir.mkdir(parents=True, exist_ok=True)
(illustration_dir / 'index.html').write_text(page, encoding='utf-8')

hero_b64 = (root / '.tmp_illustration' / 'hero.b64').read_text(encoding='utf-8')
media_dir = root / 'media' / 'illustration'
media_dir.mkdir(parents=True, exist_ok=True)
(media_dir / 'hero.webp').write_bytes(base64.b64decode(hero_b64))

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
          <a class="project-visual" href="/illustration/"><img src="/media/illustration/hero.webp" alt="Faro Ahogado illustration and visual development"><span class="project-index">05</span><span class="project-status">Illustration portfolio</span></a>
          <div class="project-content"><div class="project-meta"><span>Character illustration</span><span>Visual development</span></div><h3><a href="/illustration/">Visual Development — Character Illustration</a></h3><p>A dedicated illustration page with line-art, color and final-lighting process stages plus the full selected illustration gallery.</p><ul class="tag-list"><li>Line Art</li><li>Color Design</li><li>Character</li><li>Environment</li><li>Technical Design</li></ul><a class="text-link" href="/illustration/">Open illustration portfolio <span>↗</span></a></div>
        </article>
      </div>
    </section>

'''

html = html[:start] + replacement + html[end:]
home.write_text(html, encoding='utf-8')
