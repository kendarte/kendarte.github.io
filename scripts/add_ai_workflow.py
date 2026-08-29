from pathlib import Path
import base64

root = Path('.')
index_path = root / '3d' / 'index.html'
html = index_path.read_text(encoding='utf-8')

media_dir = root / 'media' / '3d'
media_dir.mkdir(parents=True, exist_ok=True)

img_b64 = (root / '.tmp_portfolio' / 'ai-workflow.b64').read_text().strip()
video_b64 = ''.join((root / '.tmp_portfolio' / f'video.part{i:02d}').read_text().strip() for i in range(4))
(media_dir / 'ai-workflow.webp').write_bytes(base64.b64decode(img_b64))
(media_dir / 'ai-animation.mp4').write_bytes(base64.b64decode(video_b64))

if 'id="ai-workflow"' not in html:
    html = html.replace(
        '<a href="#work">Selected Work</a><a href="#focus">Focus</a>',
        '<a href="#work">Selected Work</a><a href="#ai-workflow">AI Workflow</a><a href="#focus">Focus</a>'
    )

    css = '''\n    .ai-workflow { padding-block:clamp(90px,11vw,150px); border-top:1px solid var(--line); }\n    .ai-case { overflow:hidden; border:1px solid var(--line); background:var(--panel); }\n    .ai-case-grid { display:grid; grid-template-columns:1.05fr .95fr; }\n    .ai-stills { min-height:560px; background:#080a0c; }\n    .ai-stills img { width:100%; height:100%; object-fit:cover; }\n    .ai-copy { display:flex; flex-direction:column; justify-content:center; padding:clamp(34px,5vw,70px); }\n    .ai-copy h2 { margin:0; font-size:clamp(38px,4vw,62px); font-weight:560; letter-spacing:-.05em; line-height:1; }\n    .ai-copy > p:not(.project-kicker) { margin:25px 0 0; color:var(--muted); font-size:15px; line-height:1.78; }\n    .pipeline { display:flex; flex-wrap:wrap; gap:8px; margin-top:28px; }\n    .pipeline span { padding:8px 10px; border:1px solid var(--line); color:#d6d0ff; font-family:var(--font-geist-mono),monospace; font-size:9px; letter-spacing:.08em; text-transform:uppercase; }\n    .pipeline b { align-self:center; color:var(--art-violet); font-weight:500; }\n    .ai-video { padding:18px; border-top:1px solid var(--line); background:#080a0c; }\n    .ai-video video { display:block; width:min(720px,100%); margin:auto; aspect-ratio:1/1; object-fit:cover; background:#000; }\n    .ai-video-label { width:min(720px,100%); margin:12px auto 0; color:var(--muted); font-family:var(--font-geist-mono),monospace; font-size:9px; letter-spacing:.1em; text-transform:uppercase; }\n'''
    html = html.replace('    @media (max-width:900px) {', css + '    @media (max-width:900px) {')
    html = html.replace(
        '      .art-hero,.art-project,.art-project:nth-of-type(even){grid-template-columns:1fr;}',
        '      .art-hero,.art-project,.art-project:nth-of-type(even),.ai-case-grid{grid-template-columns:1fr;}'
    )
    html = html.replace(
        '      .art-project-media{min-height:auto; aspect-ratio:1/1;}',
        '      .art-project-media{min-height:auto; aspect-ratio:1/1;}\n      .ai-stills{min-height:auto; aspect-ratio:14/9;}'
    )

    section = '''\n    <section class="ai-workflow section-shell" id="ai-workflow">\n      <div class="section-heading">\n        <div><p class="eyebrow"><span></span> Process documentation</p><h2>3D Rendering to AI Animation.</h2></div>\n        <p>Character staging, rendering and AI-assisted animation workflow.</p>\n      </div>\n      <article class="ai-case">\n        <div class="ai-case-grid">\n          <div class="ai-stills"><img src="/media/3d/ai-workflow.webp" alt="3D scene setup, render development and final character render"></div>\n          <div class="ai-copy">\n            <p class="project-kicker">Project 03 · AI-assisted workflow</p>\n            <h2>From 3D scene to animated output.</h2>\n            <p>A compact production pipeline moving from character staging and render preparation into an AI animation pass and final output.</p>\n            <div class="pipeline"><span>3D Character</span><b>→</b><span>Staging</span><b>→</b><span>Render</span><b>→</b><span>AI Animation</span><b>→</b><span>Final Output</span></div>\n            <div class="art-meta"><div><span>Focus</span><strong>3D Rendering · Character Presentation</strong></div><div><span>Workflow</span><strong>AI-Assisted Animation</strong></div></div>\n          </div>\n        </div>\n        <div class="ai-video">\n          <video controls playsinline preload="metadata" aria-label="Final AI-assisted animated character output">\n            <source src="/media/3d/ai-animation.mp4" type="video/mp4">\n          </video>\n          <div class="ai-video-label">Final output · AI-assisted animation</div>\n        </div>\n      </article>\n    </section>\n\n'''
    anchor = '    <section class="art-focus section-shell" id="focus">'
    if anchor not in html:
        raise RuntimeError('Focus section anchor not found')
    html = html.replace(anchor, section + anchor, 1)

    html = html.replace(
        '<article><span class="capability-number">04</span><h3>Props &amp; weapons</h3><p>Large integrated props designed to contribute to the character silhouette instead of reading as separate inventory pieces.</p></article>',
        '<article><span class="capability-number">04</span><h3>3D + AI workflow</h3><p>Rendered character presentation carried into an AI-assisted animation pipeline with documented visual stages.</p></article>'
    )
    html = html.replace(
        '<span>3D characters · costumes · armor · props</span>',
        '<span>3D characters · costumes · armor · rendering · AI animation</span>'
    )

index_path.write_text(html, encoding='utf-8')
