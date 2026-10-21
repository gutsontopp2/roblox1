"""Vibrant style v2: blurred bg, gameplay block in the middle, two-colour headlines on top,
yellow game tag at the bottom, SFX + voice, end card with game title."""
import subprocess, os, sys, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make as M  # reuse REG, run, SRC
M.REG["h2"] = dict(x=120, y=40, w=1520, h=660, audio=True, ext="mp4")  # Roll an Anime lobby tour

S = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(S, "tmp2"); OUT = os.path.join(S, "out2")
os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
COL = {"pink": "#FF3EA5", "cyan": "#3EE6FF", "yellow": "#FFE14D", "orange": "#FF8A1E",
       "white": "#FFFFFF", "green": "#6CFF5C", "purple": "#B46BFF"}
BAND_Y, BAND_H = 430, 1060
GAMES = {"KRILLION": ("#3EE6FF", "#FFE14D"), "ANIME FISHING": ("#FFE14D", "#FF3EA5"),
         "ROLL AN ANIME": ("#FF3EA5", "#3EE6FF"), "PET CARD FARM": ("#6CFF5C", "#FFE14D")}

def text_png(lines, path, max_w=1010, size=118, rotate=0.0):
    """lines: [[text, colour], ...] -> transparent PNG 1080 wide, centred lines, stroke + shadow."""
    font_size = size
    while True:
        f = ImageFont.truetype(FONT, font_size)
        widths = [f.getbbox(t)[2] - f.getbbox(t)[0] for t, _ in lines]
        if max(widths) <= max_w or font_size < 50: break
        font_size -= 4
    lh = int(font_size * 1.08); H = lh * len(lines) + 60
    img = Image.new("RGBA", (1080, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (1080, H), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(sh)
    sw = max(6, font_size // 11)
    for i, (t, c) in enumerate(lines):
        w = widths[i]; x = (1080 - w) // 2 - f.getbbox(t)[0]; y = 20 + i * lh
        ds.text((x + 7, y + 10), t, font=f, fill=(0, 0, 0, 170), stroke_width=sw, stroke_fill=(0, 0, 0, 170))
        d.text((x, y), t, font=f, fill=COL.get(c, c), stroke_width=sw, stroke_fill="#0B0B14")
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    out = Image.alpha_composite(sh, img)
    if rotate: out = out.rotate(rotate, resample=Image.BICUBIC, expand=True)
    out.save(path); return out.size

def segment(src, start, end, idx, name, zoom=0.10, speed=1.0):
    r = M.REG[src]; d = end - start
    out = os.path.join(TMP, f"{name}_{idx}.mp4")
    ar = 1080 / BAND_H
    ch = r["h"]; cw = int(ch * ar) // 2 * 2
    if cw > r["w"]: cw = r["w"] // 2 * 2; ch = int(cw / ar) // 2 * 2
    cx = r["x"] + (r["w"] - cw) // 2 + r.get("dx", 0); cy = r["y"] + (r["h"] - ch) // 2
    z = f"(1+0.16*exp(-t*7)+{zoom}*t/{d/speed:.3f})"
    band = (f"crop={cw}:{ch}:{cx}:{cy},scale=w='trunc(1080*{z}/2)*2':h='trunc({BAND_H}*{z}/2)*2':eval=frame:flags=lanczos,"
            f"crop=1080:{BAND_H}:x='(in_w-1080)/2+14*sin(t*55)*exp(-t*7)':y='(in_h-{BAND_H})/2+10*cos(t*47)*exp(-t*7)',"
            f"unsharp=5:5:0.6,eq=saturation=1.35:contrast=1.08")
    bg = (f"crop={r['w']}:{r['h']}:{r['x']}:{r['y']},scale=-2:1920,crop=1080:1920,boxblur=22:2,"
          f"eq=saturation=1.4:brightness=-0.06")
    vf = (f"[0:v]format=yuv420p,setpts=(PTS-STARTPTS)/{speed},fps=30,split[a][b];[a]{bg}[bg];[b]{band}[fg];"
          f"[bg][fg]overlay=0:{BAND_Y},fade=in:st=0:d=0.12:color=white,setsar=1,format=yuv420p[v]")
    ext = r.get("ext", "mov"); f = os.path.join(M.SRC, src + "." + ext)
    cmd = (["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", str(d), "-i", f] if ext == "png"
           else ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-to", str(end), "-i", f])
    if r["audio"]:
        af = f"[0:a]atempo={speed},aresample=44100,volume=0.8[aud]"
        cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[aud]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", vf,
                "-map", "[v]", "-map", "1:a", "-t", str(d / speed)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-ac", "2", out]
    M.run(cmd); return out

def vdur(f, stream="v:0"):
    return float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                                 "stream=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)

def build(v):
    name, game = v["name"], v["game"]
    gcol, gcol2 = GAMES[game]
    parts = [segment(s[0], s[1], s[2], i, name, s[3] if len(s) > 3 else 0.1, s[4] if len(s) > 4 else 1.0)
             for i, s in enumerate(v["segments"])]
    cuts, acc = [], 0.0
    for p in parts[:-1]: acc += vdur(p); cuts.append(acc)
    lst = os.path.join(TMP, name + ".txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    joined = os.path.join(TMP, name + "_joined.mp4")
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    dur = vdur(joined)
    # end card
    last = os.path.join(TMP, name + "_last.png"); end = os.path.join(TMP, name + "_end.mp4")
    M.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", joined, "-frames:v", "1", "-update", "1", last])
    words = game.split(" ")
    title_lines = [[" ".join(words[:-1]), gcol], [words[-1], gcol2]] if len(words) > 1 else [[game, gcol]]
    if v.get("endtitle"): title_lines = v["endtitle"]
    tp = os.path.join(TMP, name + "_endtitle.png"); text_png(title_lines, tp, size=170)
    pp = os.path.join(TMP, name + "_endplay.png"); text_png([[v.get("endsub", "PLAY NOW ON ROBLOX"), "white"]], pp, size=70, rotate=-3)
    M.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", "2", "-i", last,
           "-loop", "1", "-framerate", "30", "-t", "2", "-i", tp, "-loop", "1", "-framerate", "30", "-t", "2", "-i", pp,
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex",
           "[0:v]boxblur=26:2,eq=brightness=-0.25:saturation=1.4[b];"
           "[1:v]format=rgba,scale=w='1080*(1+0.4*max(0,1-t/0.18))':h=-1:eval=frame[t];"
           "[2:v]format=rgba,fade=in:st=0.25:d=0.15:alpha=1[p];"
           "[b][t]overlay=(W-w)/2:620-h/2:shortest=1[bt];[bt][p]overlay=(W-w)/2:1060,fade=in:st=0:d=0.12:color=white,format=yuv420p[v]",
           "-map", "[v]", "-map", "3:a", "-t", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-c:a", "aac", "-ac", "2", end])
    lst2 = os.path.join(TMP, name + "_2.txt"); open(lst2, "w").write(f"file '{joined}'\nfile '{end}'\n")
    full = os.path.join(TMP, name + "_full.mp4")
    M.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst2, "-c", "copy", full])
    # overlays: headlines (top) + tag (bottom) + band edge lines
    ins = ["-i", full]; fc = [f"[0:v]drawbox=x=0:y={BAND_Y-6}:w=1080:h=6:color={gcol}@0.9:t=fill:enable='lt(t,{dur})',"
                              f"drawbox=x=0:y={BAND_Y+BAND_H}:w=1080:h=6:color={gcol2}@0.9:t=fill:enable='lt(t,{dur})'[v0]"]
    k = 0; cur = "v0"; starts = []
    heads = v["headlines"]
    for j, h in enumerate(heads):
        st = h.get("start", 0); en = min(h.get("end", dur), dur)
        hp = os.path.join(TMP, f"{name}_h{j}.png"); w, hh = text_png(h["lines"], hp)
        ins += ["-loop", "1", "-framerate", "30", "-t", str(dur + 2), "-i", hp]; k += 1
        fc.append(f"[{k}:v]format=rgba,scale=w='1080*(1+0.25*max(0,1-(t-{st})/0.12))':h=-1:eval=frame[h{j}]")
        fc.append(f"[{cur}][h{j}]overlay=(W-w)/2:{BAND_Y//2 - 10}-h/2:enable='between(t,{st},{en})'[c{j}]")
        cur = f"c{j}"; starts.append(st)
    tagp = os.path.join(TMP, f"{name}_tag.png"); text_png([[v.get("tag", f"{game} ON ROBLOX"), "yellow"]], tagp, size=96, rotate=-3)
    ins += ["-loop", "1", "-framerate", "30", "-t", str(dur + 2), "-i", tagp]; k += 1
    fc.append(f"[{cur}][{k}:v]overlay=(W-w)/2:{BAND_Y+BAND_H+215}-h/2:enable='lt(t,{dur})',format=yuv420p[vout]")
    # audio: game + sfx + voice
    SFX = os.path.join(S, "sfx")
    events = [("whoosh", max(0, c - 0.16), 0.55) for c in cuts]
    events += [("pop", st, 0.45) for st in starts if st > 0.05]
    events += [("whoosh", max(0, dur - 0.16), 0.6), ("boom", dur, 0.9), ("pop", dur + 0.3, 0.45)]
    base = k + 1; fc.append("[0:a]volume=0.4[g]"); mix = "[g]"
    for e, (snd, at, vol) in enumerate(events):
        ins += ["-i", os.path.join(SFX, snd + ".wav")]; ms = int(at * 1000)
        fc.append(f"[{base+e}:a]volume={vol},adelay={ms}|{ms}[s{e}]"); mix += f"[s{e}]"
    n = len(events) + 1
    vo = os.path.join(S, "vo", name + ".wav")
    if os.path.exists(vo):
        vlen = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vo],
                                    capture_output=True, text=True).stdout)
        tempo = max(1.0, vlen / (dur + 2.0 - 0.35))
        ins += ["-i", vo]
        fc.append(f"[{base+len(events)}:a]aresample=44100,atempo={tempo:.3f},volume=1.7,adelay=150|150,aformat=channel_layouts=stereo[vo]")
        mix += "[vo]"; n += 1
    fc.append(f"{mix}amix=inputs={n}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
    out = os.path.join(OUT, name + ".mp4")
    M.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
           "-t", str(dur + 2), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", out])
    print(name, round(dur + 2, 1), "s ->", out)

if __name__ == "__main__":
    vids = json.load(open(os.path.join(S, "videos2.json")))
    only = sys.argv[1:]
    for v in vids:
        if not only or v["name"] in only: build(v)
