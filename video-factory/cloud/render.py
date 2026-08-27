import json, math, os, shutil, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from kokoro import KPipeline
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'queue' / 'latest.json'
OUT_DIR = ROOT / 'renders'
WORK = ROOT / '.cloud-build'
FRAMES = WORK / 'frames'
AUDIO = WORK / 'audio'
ASSETS = WORK / 'assets'
FPS = 24
W, H = 720, 1280
SR = 24000

for p in (OUT_DIR, FRAMES, AUDIO, ASSETS):
    p.mkdir(parents=True, exist_ok=True)

job = json.loads(QUEUE.read_text(encoding='utf-8'))
project = job['project']
scenes = project.get('scenes', [])
accent_hex = project.get('accent', '#ff354b').lstrip('#')
ACCENT = tuple(int(accent_hex[i:i+2], 16) for i in (0,2,4))
VOICE = project.get('voice', 'am_michael')
SPEED = float(project.get('voiceSpeed', 1.05))

font_candidates = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
]
reg_candidates = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
]
BOLD = next(p for p in font_candidates if Path(p).exists())
REG = next(p for p in reg_candidates if Path(p).exists())

def font(sz, bold=True):
    return ImageFont.truetype(BOLD if bold else REG, sz)

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ease(x):
    x = clamp(x)
    return 1 - (1-x)**3

def pop(x):
    x = clamp(x)
    return ease(x/.72)*1.06 if x < .72 else 1.06 - ((x-.72)/.28)*.06

def trim_silence(a):
    a = np.asarray(a, dtype=np.float32)
    if len(a) == 0:
        return a
    peak = float(np.max(np.abs(a)))
    if peak < 1e-7:
        return a
    frame = max(1, int(SR*0.01))
    rms = np.array([float(np.sqrt(np.mean(a[i:i+frame]**2))) for i in range(0, len(a), frame)])
    active = np.where(rms > max(0.0015, peak*0.012))[0]
    if not len(active):
        return a
    pad = int(SR*0.04)
    s = max(0, int(active[0]*frame)-pad)
    e = min(len(a), int((active[-1]+1)*frame)+pad)
    return a[s:e]

# 1) Generate speech first; audio owns the timeline.
pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
master = []
timeline = []
cursor = 0.0
gap = np.zeros(int(SR*0.075), dtype=np.float32)

for i, scene in enumerate(scenes):
    text = (scene.get('voice') or '').strip()
    parts = []
    if text:
        for _, _, a in pipe(text, voice=VOICE, speed=SPEED, split_pattern=r'\n+'):
            parts.append(trim_silence(a))
    audio = trim_silence(np.concatenate(parts)) if parts else np.zeros(int(SR*1.0), dtype=np.float32)
    if len(audio)/SR < 1.0:
        audio = np.concatenate([audio, np.zeros(int(SR*(1.0-len(audio)/SR)), dtype=np.float32)])
    start = cursor
    speech_end = start + len(audio)/SR
    end = speech_end + (len(gap)/SR if i < len(scenes)-1 else 0)
    timeline.append({'start':start, 'speechEnd':speech_end, 'end':end, 'duration':end-start})
    master.append(audio)
    cursor = speech_end
    if i < len(scenes)-1:
        master.append(gap)
        cursor += len(gap)/SR

master_audio = np.concatenate(master).astype(np.float32)
master_path = AUDIO / 'master.wav'
sf.write(master_path, master_audio, SR)
duration = len(master_audio)/SR

# 2) Capture live evidence once per evidence scene.
evidence = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for i, scene in enumerate(scenes):
        if scene.get('type') != 'evidence' or not scene.get('sourceUrl'):
            continue
        page = browser.new_page(viewport={'width':1365,'height':900})
        try:
            page.goto(scene['sourceUrl'], wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(1200)
            full = ASSETS / f'evidence_{i:02d}_full.png'
            page.screenshot(path=str(full), full_page=False)
            focus = None
            if scene.get('focus'):
                loc = page.get_by_text(scene['focus'], exact=False).first
                if loc.count():
                    loc.scroll_into_view_if_needed()
                    page.wait_for_timeout(250)
                    box = loc.bounding_box()
                    if box:
                        pad = 35
                        clip = {
                            'x':max(0, box['x']-pad), 'y':max(0, box['y']-pad),
                            'width':min(1365-max(0,box['x']-pad), box['width']+pad*2),
                            'height':min(900-max(0,box['y']-pad), box['height']+pad*2)
                        }
                        fp = ASSETS / f'evidence_{i:02d}_focus.png'
                        page.screenshot(path=str(fp), clip=clip)
                        focus = fp
            evidence[i] = {'full':full, 'focus':focus}
        except Exception as e:
            print('Evidence capture failed:', scene.get('sourceUrl'), e)
        finally:
            page.close()
    browser.close()

# Helpers.
def wrap(draw, text, fnt, maxw):
    words = str(text or '').split()
    lines, cur = [], ''
    for w in words:
        test = (cur+' '+w).strip()
        if draw.textbbox((0,0), test, font=fnt)[2] <= maxw:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def text_center(draw, text, y, fnt, fill='white'):
    bb = draw.textbbox((0,0), text, font=fnt)
    draw.text(((W-(bb[2]-bb[0]))/2, y), text, font=fnt, fill=fill)

def draw_caption(draw, scene):
    cap = scene.get('caption') or scene.get('title') or scene.get('voice','')
    words = cap.split()
    if len(words) > 9: cap = ' '.join(words[:9]) + '…'
    f = font(39)
    lines = wrap(draw, cap.upper(), f, 640)
    y = 1080 - (len(lines)-1)*45
    for line in lines:
        text_center(draw, line, y, f)
        y += 45
    draw.text((32,1230), project.get('brand','LOOKS LEGIT'), font=font(17), fill='white')

def base_frame(t):
    img = Image.new('RGB',(W,H),(5,8,13))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y/H
        d.line((0,y,W,y), fill=(8+int(7*(1-k)), 12+int(10*(1-k)), 19+int(15*(1-k))))
    # moving atmosphere
    dx = int(math.sin(t*.7)*18); dy = int(math.cos(t*.5)*12)
    d.ellipse((-170+dx,-110+dy,440+dx,470+dy), fill=(18,42,72))
    d.ellipse((390-dx,760-dy,930-dx,1330-dy), fill=(62,14,27))
    return img

def paste_fit(dst, src, box, zoom=1.0, oy=0.0):
    x1,y1,x2,y2 = box
    bw,bh = x2-x1,y2-y1
    sw,sh = src.size
    scale = max(bw/sw, bh/sh)*zoom
    nw,nh = int(sw*scale), int(sh*scale)
    rs = src.resize((nw,nh), Image.LANCZOS)
    left=(nw-bw)//2; top=max(0,(nh-bh)//2 + int(oy))
    crop=rs.crop((left,top,left+bw,top+bh))
    dst.paste(crop,(x1,y1))

def rounded(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

# 3) Render frames with internal direction per scene.
total = math.ceil(duration*FPS)
scene_idx = 0
for frame in range(total):
    t = frame/FPS
    while scene_idx < len(timeline)-1 and t >= timeline[scene_idx]['end']:
        scene_idx += 1
    scene = scenes[scene_idx]
    seg = timeline[scene_idx]
    p = clamp((t-seg['start'])/max(.001,seg['duration']))
    img = base_frame(t)
    d = ImageDraw.Draw(img)
    typ = scene.get('type','headline')

    if typ == 'headline':
        title = scene.get('title','')
        body = scene.get('body','')
        scale = .84 + .16*pop(p/.18)
        fs = int(68*scale)
        f = font(fs)
        lines = wrap(d, title, f, 620)
        y = 430 - len(lines)*38
        for line in lines:
            text_center(d,line,y,f); y += fs+5
        if p > .20 and body:
            fb = font(28,False); lines = wrap(d,body,fb,580); y += 22
            for line in lines:
                text_center(d,line,y,fb,fill=(200,210,220)); y += 36

    elif typ == 'split':
        lp = ease(p/.18); rp = ease((p-.08)/.18)
        lx = int(35-(1-lp)*120); rx = int(370+(1-rp)*120)
        rounded(d,(lx,260,lx+315,900),28,(17,25,36),(55,70,90),2)
        rounded(d,(rx,260,rx+315,900),28,(17,25,36),(55,70,90),2)
        d.text((lx+26,300),scene.get('leftLabel','LEFT'),font=font(17),fill=(150,168,188))
        d.text((rx+26,300),scene.get('rightLabel','RIGHT'),font=font(17),fill=(150,168,188))
        fl = font(36)
        for x,text in ((lx,scene.get('left','')),(rx,scene.get('right',''))):
            lines=wrap(d,text,fl,260); yy=430
            for line in lines:
                d.text((x+26,yy),line,font=fl,fill='white'); yy+=46

    elif typ == 'stat':
        num = scene.get('number','')
        lab = scene.get('label','')
        sc = .72 + .28*pop(p/.2)
        f = font(int(145*sc)); text_center(d,num,420,f,fill=ACCENT)
        fl=font(39); lines=wrap(d,lab,fl,600); y=620
        for line in lines:
            text_center(d,line,y,fl); y+=48

    elif typ == 'evidence':
        ev = evidence.get(scene_idx,{})
        fullp = ev.get('full'); focusp = ev.get('focus')
        if p < .48 and fullp and Path(fullp).exists():
            src=Image.open(fullp).convert('RGB')
            zoom=1.0 + .08*ease(p/.48)
            paste_fit(img,src,(45,105,675,940),zoom=zoom,oy=-30*p)
            d.rounded_rectangle((45,105,675,940),radius=26,outline=(80,85,95),width=2)
        elif focusp and Path(focusp).exists() and p < .78:
            src=Image.open(focusp).convert('RGB')
            paste_fit(img,src,(70,250,650,760),zoom=.98 + .04*pop((p-.40)/.18))
            d.rounded_rectangle((70,250,650,760),radius=22,outline=(90,95,105),width=2)
        else:
            rounded(d,(55,260,665,860),30,(246,247,249))
            d.text((85,305),'SOURCE',font=font(18),fill=(95,108,123))
            f=font(37)
            lines=wrap(d,scene.get('focus',''),f,520); y=390
            for line in lines:
                d.text((95,y),line,font=f,fill=(18,22,28)); y+=48
            d.rectangle((72,375,82,min(840,y+10)),fill=ACCENT)
        d.text((52,965),scene.get('sourceLabel','SOURCE'),font=font(18),fill=(170,185,200))

    elif typ == 'chat':
        phone_y = int(80 + (1-pop(p/.12))*65)
        rounded(d,(62,phone_y,658,1120),55,(14,20,29),(45,55,68),2)
        rounded(d,(250,phone_y+14,470,phone_y+43),18,(2,3,5))
        d.text((90,phone_y+55),'9:41',font=font(18,False)); d.text((560,phone_y+55),'5G',font=font(18))
        d.rectangle((62,phone_y+88,658,phone_y+190),fill=(18,26,38))
        d.ellipse((90,phone_y+110,148,phone_y+168),fill=(33,74,120))
        d.text((101,phone_y+127),(scene.get('sender','APP')[:3]).upper(),font=font(15))
        d.text((168,phone_y+110),scene.get('sender','Unknown'),font=font(26))
        d.text((168,phone_y+148),scene.get('sub',''),font=font(15,False),fill=(155,170,187))
        if p>.08:
            rounded(d,(90,phone_y+235,530,phone_y+365),22,(27,39,53))
            fm=font(24); lines=wrap(d,scene.get('message',''),fm,390); y=phone_y+255
            for line in lines:
                d.text((112,y),line,font=fm); y+=32
        if p>.30 and scene.get('amount'):
            rounded(d,(90,phone_y+425,630,phone_y+610),25,(19,29,41),(48,60,74),2)
            d.text((115,phone_y+448),'AMOUNT',font=font(16),fill=(145,165,184))
            d.text((115,phone_y+490),scene['amount'],font=font(60))
        if p>.56 and scene.get('fee'):
            rounded(d,(110,phone_y+675,610,phone_y+815),24,(54,18,25),ACCENT,3)
            d.text((135,phone_y+698),'REQUIRED PAYMENT',font=font(16),fill=(255,179,188))
            d.text((135,phone_y+735),scene['fee'],font=font(36))
        if p>.78:
            rounded(d,(85,480,635,700),18,(35,7,12),ACCENT,7)
            text_center(d,scene.get('stamp','SCAM #2'),545,font(75),fill=ACCENT)

    elif typ == 'quote':
        fq=font(47); lines=wrap(d,'“'+scene.get('body','')+'”',fq,600); y=400
        for line in lines:
            text_center(d,line,y,fq); y+=58
        text_center(d,scene.get('title',''),y+30,font(24,False),fill=(155,170,188))

    draw_caption(d, scene)
    img.save(FRAMES / f'frame_{frame+1:06d}.jpg', quality=92)

# 4) Master audio and encode.
out = OUT_DIR / 'latest.mp4'
subprocess.run([
    'ffmpeg','-y','-hide_banner','-loglevel','error',
    '-framerate',str(FPS),'-i',str(FRAMES/'frame_%06d.jpg'),
    '-i',str(master_path),
    '-filter_complex','[1:a]loudnorm=I=-16:TP=-1.5:LRA=9[a]',
    '-map','0:v','-map','[a]',
    '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',
    '-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(out)
], check=True)

meta = {
    'jobId': job.get('id'),
    'project': project.get('name'),
    'duration': round(duration,3),
    'output': 'video-factory/renders/latest.mp4'
}
(OUT_DIR/'latest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))

shutil.rmtree(WORK, ignore_errors=True)
