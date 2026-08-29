from pathlib import Path
import base64

root = Path('.')
index_path = root / '3d' / 'index.html'
html = index_path.read_text(encoding='utf-8')

chunks = root / '.tmp_portfolio'
img_b64 = ''.join(p.read_text().strip() for p in sorted(chunks.glob('image.part*')))
video_b64 = ''.join(p.read_text().strip() for p in sorted(chunks.glob('video.part*')))
if not img_b64 or not video_b64:
    raise RuntimeError('Portfolio media chunks are missing')

media_dir = root / 'media' / '3d'
media_dir.mkdir(parents=True, exist_ok=True)
(media_dir / 'ai-workflow.webp').write_bytes(base64.b64decode(img_b64))
(media_dir / 'ai-animation.mp4').write_bytes(base64.b64decode(video_b64))

if 'id="ai-workflow"' not in html:
    html = html.replace(
        '<a href="#work">Selected Work</a><a href="#focus">Focus</a>',
        '<a href="#work">Selected Work</a><a href="#ai-workflow">AI Workflow</a><a href="#focus">Focus</a>'
    )

    css = '''
    .ai-workflow { padding-block:clamp(90px,11vw,150px); border-top:1px solid var(--line); }
    .ai-case { overflow:hidden; border:1px solid var(--line); background:var(--panel); }
    .ai-case-grid { display:grid; grid-template-columns:1.05fr .95fr; }
    .ai-stills { min-height:560px; background:#080a0c; }
    .ai-stills img { width:100%; height:100%; object-fit:cover; }
    .ai-copy { display:flex; flex-direction:column; justify-content:center; padding:clamp(34px,5vw,70px); }
    .ai-copy h2 { margin:0; font-size:clamp(38px,4vw,62px); font-weight:560; letter-spacing:-.05em; line-height:1; }
    .ai-copy > p:not(.project-kicker) { margin:25px 0 0; color:var(--muted); font-size:15px; line-height:1.78; }
    .pipeline { display:flex; flex-wrap:wrap; gap:8px; margin-top:28px; }
    .pipeline span { padding:8px 10px; border:1px solid var(--line); color:#d6d0ff; font-family:var(--font-geist-mono),monospace; font-size:9px; letter-spacing:.08em; text-transform:uppercase; }
    .pipeline b { align-self:center; color:var(--art-violet); font-weight:500; }
    .ai-video { padding:18px; border-top:1px solid var(--line); background:#080a0c; }
    .ai-video video { display:block; width:min(720px,100%); margin:auto; aspect-ratio:1/1; object-fit:cover; background:#000; }
    .ai-video-label { width:min(720px,100%); margin:12px auto 0; color:var(--muted); font-family:var(--font-geist-mono),monospace; font-size:9px; letter-spacing:.1em; text-transform:uppercase; }
'''
    html = html.replace('    @media (max-width:900px) {', css + '    @media (max-width:900px) {')
    html = html.replace(
        '      .art-hero,.art-project,.art-project:nth-of-type(even){grid-template-columns:1fr;}',
        '      .art-hero,.art-project,.art-project:nth-of-type(even),.ai-case-grid{grid-template-columns:1fr;}'
    )
    html = html.replace(
        '      .art-project-media{min-height:auto; aspect-ratio:1/1;}',
        '      .art-project-media{min-height:auto; aspect-ratio:1/1;}\n      .ai-stills{min-height:auto; aspect-ratio:14/9;}'
    )

    section = '''
    <section class="ai-workflow section-shell" id="ai-workflow">
      <div class="section-heading">
        <div><p class="eyebrow"><span></span> 3D workflow</p><h2>3D Rendering → AI Animation.</h2></div>
        <p>From the 3D render to the animated result.</p>
      </div>
      <article class="ai-case">
        <div class="ai-case-grid">
          <div class="ai-stills"><img src="/media/3d/ai-workflow.webp" alt="3D render workflow and character presentation"></div>
          <div class="ai-copy">
            <p class="project-kicker">3D Rendering · Animation</p>
            <h2>Render to motion.</h2>
            <p>Character rendering carried into an AI animation pass for the final moving shot.</p>
            <div class="pipeline"><span>3D Scene</span><b>→</b><span>Render</span><b>→</b><span>AI Animation</span><b>→</b><span>Final Output</span></div>
          </div>
        </div>
        <div class="ai-video">
          <video controls playsinline preload="metadata" aria-label="Animated final output">
            <source src="/media/3d/ai-animation.mp4" type="video/mp4">
          </video>
          <div class="ai-video-label">Animated final output</div>
        </div>
      </article>
    </section>

'''
    anchor = '    <section class="art-focus section-shell" id="focus">'
    if anchor not in html:
        raise RuntimeError('Focus section anchor not found')
    html = html.replace(anchor, section + anchor, 1)

index_path.write_text(html, encoding='utf-8')
