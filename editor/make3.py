"""'Roblox games to play with friends' list style (like the reference edit):
full-frame gameplay, hook + counter intro, one stat card per game, handle outro, beat + sfx."""
import os, sys, json, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make as M

S = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(S, "tmp3"); OUT = os.path.join(S, "out3")
os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
COL = {"red": "#FF2B3A", "green": "#4DFF3A", "cyan": "#2EF2FF", "pink": "#FF3EA5", "yellow": "#FFE14D",
       "orange": "#FF9A1E", "white": "#FFFFFF", "purple": "#B46BFF"}
M.REG["sr"] = dict(x=0, y=0, w=1920, h=888, audio=True, ext="mp4")

def render(lines, path, size=100, max_w=1020, rotate=0, spacing=1.06, letter=0):
    """lines: [[(text, colour), ...], ...] -> PNG (1080 wide)."""
    fs = size
    def width(f, segs): return sum(f.getlength(t) + letter * len(t) for t, _ in segs)
    while True:
        f = ImageFont.truetype(FONT, fs)
        if max(width(f, l) for l in lines) <= max_w or fs < 40: break
        fs -= 3
    lh = int(fs * spacing); H = lh * len(lines) + 50
    img = Image.new("RGBA", (1080, H), (0, 0, 0, 0)); sh = img.copy()
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(sh); sw = max(5, fs // 12)
    for i, segs in enumerate(lines):
        x = (1080 - width(f, segs)) / 2; y = 15 + i * lh
        for t, c in segs:
            for ch in (t if letter else [t]):
                ds.text((x + 6, y + 8), ch, font=f, fill=(0, 0, 0, 200), stroke_width=sw, stroke_fill=(0, 0, 0, 200))
                d.text((x, y), ch, font=f, fill=COL.get(c, c), stroke_width=sw, stroke_fill="#000000")
                x += f.getlength(ch) + letter
    out = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(3)), img)
    if rotate: out = out.rotate(rotate, resample=Image.BICUBIC, expand=True)
    bb = out.getbbox()
    if bb: out = out.crop((max(0, bb[0]-8), max(0, bb[1]-8), min(out.width, bb[2]+8), min(out.height, bb[3]+8)))
    out.save(path); return out.size

def beat(path, dur, bpm=140):
    """Free self-made trap-ish beat: kick, clap, hats."""
    b = 60 / bpm
    expr = (f"0.9*sin(2*PI*(55*mod(t,{b})-60*mod(t,{b})^2))*exp(-mod(t,{b})*9)"
            f"+0.35*(random(0)*2-1)*exp(-mod(t+{b},{2*b})*28)*lt(mod(t+{b},{2*b}),0.25)"
            f"+0.12*(random(1)*2-1)*exp(-mod(t,{b/2})*60)")
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur}",
           "-af", "highpass=f=30,acompressor,volume=0.55", "-ac", "2", path])

def build(cfg):
    name = cfg["name"]; clips = []; cuts = []; t = 0.0; overlays = []; pops = []; booms = []
    # intro
    for i, s in enumerate(cfg["intro"]):
        clips.append(M.segment(*s[:3], f"i{i}", name, *s[3:]));
    for i, card in enumerate(cfg["cards"]):
        for k, s in enumerate(card["clips"]):
            clips.append(M.segment(*s[:3], f"c{i}_{k}", name, *s[3:]))
    durs = [float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
             "-of", "csv=p=0", c], capture_output=True, text=True).stdout) for c in clips]
    lst = os.path.join(TMP, name + ".txt"); open(lst, "w").write("".join(f"file '{c}'\n" for c in clips))
    joined = os.path.join(TMP, name + "_j.mp4")
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    # outro card (black, handle)
    outro = os.path.join(TMP, name + "_outro.mp4"); od = 2.5
    hp = os.path.join(TMP, name + "_follow.png"); render([[("FOLLOW FOR", "white")], [("MORE GAMES", "cyan")]], hp, size=120)
    hh = os.path.join(TMP, name + "_handle.png"); render([[(cfg["handle"], "white")]], hh, size=70)
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r=30:d={od}",
           "-loop", "1", "-framerate", "30", "-t", str(od), "-i", hp, "-loop", "1", "-framerate", "30", "-t", str(od), "-i", hh,
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex",
           "[1:v]format=rgba,scale=w='1080*(1+0.4*max(0,1-t/0.18))':h=-1:eval=frame[a];[2:v]format=rgba,fade=in:st=0.3:d=0.2:alpha=1[b];"
           "[0:v][a]overlay=(W-w)/2:780-h/2[x];[x][b]overlay=(W-w)/2:980,format=yuv420p[v]",
           "-map", "[v]", "-map", "3:a", "-t", str(od), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-c:a", "aac", "-ac", "2", outro])
    lst2 = os.path.join(TMP, name + "_2.txt"); open(lst2, "w").write(f"file '{joined}'\nfile '{outro}'\n")
    full = os.path.join(TMP, name + "_full.mp4")
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst2, "-c", "copy", full])
    body = sum(durs); total = body + od
    # timeline
    n_intro = len(cfg["intro"]); intro_end = sum(durs[:n_intro])
    acc = 0
    for d_ in durs: acc += d_; cuts.append(acc)
    hook = os.path.join(TMP, name + "_hook.png")
    render([[("ROBLOX GAMES", "red")], [("TO PLAY WITH", "green")], [("F R I E N D S !", "white")]], hook, size=88, max_w=700, spacing=0.98)
    overlays.append((hook, 0.0, intro_end, "40", "1470-h/2", False))
    n = len(cfg["cards"])
    for j in range(n):
        cp = os.path.join(TMP, f"{name}_cnt{j}.png"); render([[(f"+{j+1}", "cyan")]], cp, size=170, rotate=12)
        st = 0.5 + j * (intro_end - 0.6) / n
        en = 0.5 + (j + 1) * (intro_end - 0.6) / n if j < n - 1 else intro_end
        overlays.append((cp, st, en, "700", "1450-h/2", True)); pops.append(st)
    start = intro_end; ci = n_intro
    for i, card in enumerate(cfg["cards"]):
        cd = sum(durs[ci:ci + len(card["clips"])]); ci += len(card["clips"])
        tp = os.path.join(TMP, f"{name}_t{i}.png"); render([[(card["title"], card["color"])]], tp, size=118)
        overlays.append((tp, start, start + cd, "(W-w)/2", "250", True)); booms.append(start)
        for k, (lab, val, col) in enumerate(card["stats"]):
            sp = os.path.join(TMP, f"{name}_s{i}_{k}.png"); render([[(lab + ": ", "white"), (val, col)]], sp, size=62)
            st = start + 0.25 + 0.22 * k
            overlays.append((sp, st, start + cd, "(W-w)/2", str(395 + 78 * k), True)); pops.append(st)
        start += cd
    wm = os.path.join(TMP, name + "_wm.png"); render([[(cfg["handle"], "white")]], wm, size=36)
    overlays.append((wm, 0, body, "W-w-20", "640", False))
    ins = ["-i", full, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1080x1920", "-r", "30", "-i", "-"]
    fc = ["[0:v][1:v]overlay=0:0,format=yuv420p[vout]"]
    imgs = {p: Image.open(p).convert("RGBA") for p, *_ in overlays}
    def pos(expr, W, w):
        return int(eval(expr.replace("W", str(W)).replace("w", str(w)).replace("h", "0")))
    def frames():
        nfr = int(total * 30)
        for fi in range(nfr):
            t = fi / 30; canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            for p, st, en, x, y, pop in overlays:
                if not (st <= t <= en): continue
                im = imgs[p]
                if pop:
                    k = 1 + 0.35 * max(0, 1 - (t - st) / 0.12)
                    if k > 1.001: im = im.resize((int(im.width * k), int(im.height * k)), Image.BILINEAR)
                X = pos(x, 1080, im.width)
                Y = int(eval(y.replace("h", str(im.height))))
                canvas.alpha_composite(im, (max(0, X), max(0, Y))) if X >= 0 and Y >= 0 else canvas.paste(im, (X, Y), im)
            yield canvas.tobytes()
    # audio: beat + game (quiet) + sfx
    bp = os.path.join(TMP, name + "_beat.wav"); beat(bp, total)
    base = 2; ins += ["-i", bp]
    fc.append(f"[0:a]volume=0.25[g];[{base}:a]afade=out:st={total-0.8}:d=0.8[bt]"); mix = "[g][bt]"; nin = 2
    SFX = os.path.join(S, "sfx"); ev = [("whoosh", max(0, c - 0.16), 0.6) for c in cuts[:-1]]
    ev += [("pop", p, 0.5) for p in pops] + [("boom", b, 0.7) for b in booms] + [("whoosh", body - 0.16, 0.6), ("boom", body, 0.8)]
    for e, (snd, at, vol) in enumerate(ev):
        ins += ["-i", os.path.join(SFX, snd + ".wav")]; ms = int(at * 1000)
        fc.append(f"[{base+1+e}:a]volume={vol},adelay={ms}|{ms}[e{e}]"); mix += f"[e{e}]"; nin += 1
    fc.append(f"{mix}amix=inputs={nin}:normalize=0:duration=longest,alimiter=limit=0.95[aout]")
    out = os.path.join(OUT, name + ".mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
           "-t", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames(): pr.stdin.write(fr)
    pr.stdin.close(); pr.wait()
    if pr.returncode: sys.exit("final render failed")
    print(name, round(total, 1), "s ->", out)

if __name__ == "__main__":
    for cfg in json.load(open(os.path.join(S, "videos3.json"))):
        if len(sys.argv) < 2 or cfg["name"] in sys.argv[1:]: build(cfg)
