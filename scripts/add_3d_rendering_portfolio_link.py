from pathlib import Path

path = Path('3d/index.html')
text = path.read_text(encoding='utf-8')
url = 'https://kendarte.pb.online/kendallangulosportfolio'

nav_old = '<a href="#work">Selected Work</a><a href="#ai-workflow">AI Workflow</a><a href="#focus">Focus</a>'
nav_new = '<a href="#work">Selected Work</a><a href="#ai-workflow">AI Workflow</a><a href="' + url + '" target="_blank" rel="noopener">Rendering Portfolio</a><a href="#focus">Focus</a>'
if url not in text and nav_old in text:
    text = text.replace(nav_old, nav_new, 1)

hero_old = '''          <a class="button button-primary" href="#work">View selected work <span>↘</span></a>\n          <a class="button button-secondary" href="/">Gameplay portfolio <span>↗</span></a>'''
hero_new = '''          <a class="button button-primary" href="#work">View selected work <span>↘</span></a>\n          <a class="button button-secondary" href="https://kendarte.pb.online/kendallangulosportfolio" target="_blank" rel="noopener">Full 3D Rendering Portfolio <span>↗</span></a>\n          <a class="button button-secondary" href="/">Gameplay portfolio <span>↗</span></a>'''
if 'Full 3D Rendering Portfolio' not in text and hero_old in text:
    text = text.replace(hero_old, hero_new, 1)

# If the URL was added to nav first, still ensure the hero button exists.
if 'Full 3D Rendering Portfolio' not in text:
    marker = '          <a class="button button-primary" href="#work">View selected work <span>↘</span></a>\n'
    if marker in text:
        text = text.replace(marker, marker + '          <a class="button button-secondary" href="https://kendarte.pb.online/kendallangulosportfolio" target="_blank" rel="noopener">Full 3D Rendering Portfolio <span>↗</span></a>\n', 1)

path.write_text(text, encoding='utf-8')
