from pathlib import Path
import base64
import io
import re
import shutil
import subprocess
import tempfile
from PIL import Image

ROOT = Path('.')
PAGE = ROOT / '3d' / 'index.html'
MEDIA = ROOT / 'media' / '3d'
TMP = ROOT / '.tmp_portfolio'
MEDIA.mkdir(parents=True, exist_ok=True)

html = PAGE.read_text(encoding='utf-8')

# Move embedded browser data URIs into real files. Long embedded src attributes
# were the source of the visibly broken portfolio images.
pattern = re.compile(r'src="data:image/([a-zA-Z0-9.+-]+);base64,([^\"]+)"', re.S)
semantic = ['hero', 'ser-drashton', 'orange-coat']
counter = 0

def decode_b64(text: str) -> bytes:
    clean = re.sub(r'\s+', '', text)
    clean += '=' * ((4 - len(clean) % 4) % 4)
    return base64.b64decode(clean, validate=False)

def data_uri_to_file(match):
    global counter
    raw = decode_b64(match.group(2))
    name = semantic[counter] if counter < len(semantic) else f'embedded-{counter+1}'
    out = MEDIA / f'{name}.png'
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
            im.save(out, 'PNG', optimize=False)
    except Exception as exc:
        raise RuntimeError(f'Could not decode embedded 3D image {counter+1}: {exc}')
    counter += 1
    return f'src="/media/3d/{out.name}?v=0830-mediafix"'

html, replaced = pattern.subn(data_uri_to_file, html)
if replaced < 3:
    raise RuntimeError(f'Expected at least 3 embedded 3D images, found {replaced}')

# Rebuild the AI workflow still from the original chunks and normalize it to PNG.
image_parts = sorted(TMP.glob('image.part*'))
if image_parts:
    raw = decode_b64(''.join(p.read_text(encoding='utf-8').strip() for p in image_parts))
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.mode not in ('RGB', 'RGBA'):
                im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
            im.save(MEDIA / 'ai-workflow.png', 'PNG', optimize=False)
    except Exception as exc:
        raise RuntimeError(f'AI workflow image is invalid: {exc}')
else:
    src = MEDIA / 'ai-workflow.webp'
    if not src.exists():
        raise RuntimeError('AI workflow image source is missing')
    with Image.open(src) as im:
        im.load()
        im.save(MEDIA / 'ai-workflow.png', 'PNG', optimize=False)

html = html.replace('/media/3d/ai-workflow.webp', '/media/3d/ai-workflow.png?v=0830-mediafix')
html = re.sub(r'/media/3d/ai-workflow\.png(?:\?v=[^\"\']*)?', '/media/3d/ai-workflow.png?v=0830-mediafix', html)

# Rebuild the animation from its original chunks and transcode to browser-safe H.264 MP4.
video_parts = sorted(TMP.glob('video.part*'))
if video_parts:
    raw_video = decode_b64(''.join(p.read_text(encoding='utf-8').strip() for p in video_parts))
else:
    existing = MEDIA / 'ai-animation.mp4'
    if not existing.exists():
        raise RuntimeError('AI animation source is missing')
    raw_video = existing.read_bytes()

with tempfile.TemporaryDirectory() as td:
    source = Path(td) / 'source-video'
    output = Path(td) / 'output.mp4'
    source.write_bytes(raw_video)
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(source),
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(output)
    ]
    subprocess.run(cmd, check=True)
    if output.stat().st_size < 1000:
        raise RuntimeError('Transcoded AI video is unexpectedly small')
    shutil.copy2(output, MEDIA / 'ai-animation.mp4')

html = re.sub(r'/media/3d/ai-animation\.mp4(?:\?v=[^\"\']*)?', '/media/3d/ai-animation.mp4?v=0830-mediafix', html)
# A poster prevents the video block from looking like a dead black rectangle before playback.
html = html.replace('<video controls playsinline preload="metadata" aria-label="Animated final output">', '<video controls playsinline preload="metadata" poster="/media/3d/ai-workflow.png?v=0830-mediafix" aria-label="Animated final output">')

PAGE.write_text(html, encoding='utf-8')
print(f'Repaired {replaced} embedded image(s).')
print('Wrote browser-safe hero/project PNGs, AI workflow PNG, and H.264 MP4.')
