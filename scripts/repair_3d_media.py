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
pattern = re.compile(r'src="data:image/([a-zA-Z0-9.+-]+);base64,([^\"]+)"', re.S)
semantic = ['hero', 'ser-drashton', 'orange-coat']

def decode_b64(text: str) -> bytes:
    clean = re.sub(r'\s+', '', text)
    clean += '=' * ((4 - len(clean) % 4) % 4)
    return base64.b64decode(clean, validate=False)

def clean_image(raw: bytes, out: Path):
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        if im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
        im.save(out, 'PNG', optimize=False)

# The current page contains damaged embedded image strings. Recover the known-good
# portfolio images from the original 3D-page commit, validate them, and store them
# as normal browser files instead of data URIs.
original_html = subprocess.check_output(
    ['git', 'show', 'b935a9770826508541885c1cb49c2f47dea76a73:3d/index.html'],
    text=True,
    encoding='utf-8'
)
original_matches = list(pattern.finditer(original_html))
if len(original_matches) < 3:
    raise RuntimeError(f'Original 3D page only contains {len(original_matches)} embedded images')

for i, name in enumerate(semantic):
    clean_image(decode_b64(original_matches[i].group(2)), MEDIA / f'{name}.png')

# Replace every current embedded image occurrence by position. The first three are
# the hero, Ser Drashton, and Orange Coat images. Any unexpected extra embedded
# image is removed rather than leaving a broken data URI in the live page.
idx = 0
def replace_current(match):
    global idx
    if idx < len(semantic):
        path = f'/media/3d/{semantic[idx]}.png?v=0830-mediafix2'
    else:
        path = '/media/3d/hero.png?v=0830-mediafix2'
    idx += 1
    return f'src="{path}"'

html, replaced = pattern.subn(replace_current, html)
if replaced < 3:
    raise RuntimeError(f'Current page has only {replaced} embedded image references')

# Recover and validate the AI still from the existing original media chunks.
image_parts = sorted(TMP.glob('image.part*'))
if image_parts:
    raw = decode_b64(''.join(p.read_text(encoding='utf-8').strip() for p in image_parts))
    clean_image(raw, MEDIA / 'ai-workflow.png')
else:
    historical = subprocess.check_output(
        ['git', 'show', '67a74fabd779e5a7fc568602e01dbe50355bc208:media/3d/ai-workflow.webp']
    )
    clean_image(historical, MEDIA / 'ai-workflow.png')

html = re.sub(
    r'/media/3d/ai-workflow\.(?:webp|png)(?:\?v=[^\"\']*)?',
    '/media/3d/ai-workflow.png?v=0830-mediafix2',
    html
)

# Restore the last known video source and force a browser-safe H.264/yuv420p MP4.
# This also moves the MOOV atom to the front so playback can begin before the full
# file has downloaded.
try:
    raw_video = subprocess.check_output(
        ['git', 'show', '67a74fabd779e5a7fc568602e01dbe50355bc208:media/3d/ai-animation.mp4']
    )
except subprocess.CalledProcessError:
    raw_video = (MEDIA / 'ai-animation.mp4').read_bytes()

with tempfile.TemporaryDirectory() as td:
    source = Path(td) / 'source.mp4'
    output = Path(td) / 'output.mp4'
    source.write_bytes(raw_video)
    subprocess.run([
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(source),
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(output)
    ], check=True)
    probe = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,pix_fmt,width,height,duration',
        '-of', 'default=noprint_wrappers=1', str(output)
    ], text=True)
    if 'codec_name=h264' not in probe or 'pix_fmt=yuv420p' not in probe:
        raise RuntimeError('Video transcode did not produce browser-safe H.264/yuv420p')
    shutil.copy2(output, MEDIA / 'ai-animation.mp4')

html = re.sub(
    r'/media/3d/ai-animation\.mp4(?:\?v=[^\"\']*)?',
    '/media/3d/ai-animation.mp4?v=0830-mediafix2',
    html
)
# Always give the video a visible poster instead of a black empty rectangle.
html = re.sub(
    r'<video controls playsinline preload="metadata"(?: poster="[^"]*")? aria-label="Animated final output">',
    '<video controls playsinline preload="metadata" poster="/media/3d/ai-workflow.png?v=0830-mediafix2" aria-label="Animated final output">',
    html
)

PAGE.write_text(html, encoding='utf-8')
print(f'Replaced {replaced} damaged embedded image reference(s).')
print('Recovered three clean project images from git history.')
print('Validated AI still and H.264/yuv420p video.')
