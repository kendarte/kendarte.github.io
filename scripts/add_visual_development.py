from pathlib import Path

path = Path('index.html')
html = path.read_text(encoding='utf-8')

if 'id="visual-work"' not in html:
    html = html.replace(
        '<a href="#work">Work</a><a href="/projects/">Project Log</a>',
        '<a href="#work">Work</a><a href="#visual-work">Visual</a><a href="/projects/">Project Log</a>',
        1
    )

    section = '''
    <section class="work-section section-shell" id="visual-work">
      <div class="section-heading"><div><p class="eyebrow"><span></span> Visual work</p><h2>3D &amp; visual development.</h2></div><p>Character-focused work presented separately from the gameplay case studies.</p></div>
      <div class="project-list">
        <article class="project-card">
          <a class="project-visual" href="/3d/"><img src="/media/3d/ai-workflow.webp" alt="3D character rendering and AI animation workflow"><span class="project-index">04</span><span class="project-status">3D portfolio</span></a>
          <div class="project-content"><div class="project-meta"><span>3D character work</span><span>Rendering · animation</span></div><h3>3D Portfolio</h3><p>Stylized character work, costume and armor variation, props, rendering and a 3D-to-AI animation workflow.</p><a class="text-link" href="/3d/">Open 3D portfolio <span>↗</span></a></div>
        </article>
        <article class="project-card">
          <div class="project-visual"><img src="/media/visual-development/final-lighting.webp" alt="Final illustrated monster character with dramatic fire lighting"><span class="project-index">05</span><span class="project-status">Visual development</span></div>
          <div class="project-content"><div class="project-meta"><span>Character illustration</span><span>Process documentation</span></div><h3>Visual Development — Character Illustration</h3><p>From line work to final presentation.</p>
            <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:24px;">
              <figure style="margin:0;"><img src="/media/visual-development/line-art.webp" alt="Character line art stage" style="display:block;width:100%;height:auto;"><figcaption style="margin-top:8px;color:var(--muted);font-size:12px;">Line Art</figcaption></figure>
              <figure style="margin:0;"><img src="/media/visual-development/color-pass.webp" alt="Character color design stage" style="display:block;width:100%;height:auto;"><figcaption style="margin-top:8px;color:var(--muted);font-size:12px;">Color Pass</figcaption></figure>
              <figure style="margin:0;"><img src="/media/visual-development/final-lighting.webp" alt="Character final lighting stage" style="display:block;width:100%;height:auto;"><figcaption style="margin-top:8px;color:var(--muted);font-size:12px;">Final Lighting</figcaption></figure>
            </div>
            <ul class="tag-list"><li>Line Art</li><li>Color Design</li><li>Final Lighting</li><li>Visual Development</li></ul>
          </div>
        </article>
      </div>
    </section>

'''
    anchor = '    <section class="capabilities-section section-shell" id="siza">'
    if anchor not in html:
        raise RuntimeError('Siza section anchor not found')
    html = html.replace(anchor, section + anchor, 1)

path.write_text(html, encoding='utf-8')
