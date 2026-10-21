import subprocess, os, sys, json
S = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(S, "src"); OUT = os.path.join(S, "out"); TMP = os.path.join(S, "tmp")
os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"

# crop region (gameplay area) per source: x,y,w,h ; whether to keep audio
REG = {
    "c": dict(x=300, y=104, w=1320, h=856, audio=True),   # screen recording, letterboxed
    "a": dict(x=0, y=470, w=1080, h=1050, audio=False),   # phone filming monitor, skip burned text
    "d": dict(x=238, y=0, w=900, h=768, audio=True, ext="mp4"),   # Anime Fishing PC recording
    "e": dict(x=110, y=590, w=778, h=430, audio=True),    # Ryu/Yuta cutscene, below burned caption
    "f": dict(x=110, y=590, w=778, h=430, audio=True),    # Lelouch cutscene
    "g": dict(x=0, y=560, w=1080, h=1200, audio=False),   # phone filming monitor, below caption
    "img1": dict(x=420, y=300, w=1150, h=624, audio=False, ext="png", dx=-95),
}

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print(r.stderr[-3000:]); sys.exit(1)

def segment(src, start, end, idx, name, zoom=0.10, speed=1.0):
    r = REG[src]; d = (end - start)
    out = os.path.join(TMP, f"{name}_{idx}.mp4")
    ch = r['h']; cw = int(ch * 9 / 16) // 2 * 2
    if cw > r['w']: cw = r['w'] // 2 * 2; ch = int(cw * 16 / 9) // 2 * 2
    cx = r['x'] + (r['w'] - cw) // 2 + r.get('dx', 0); cy = r['y'] + (r['h'] - ch) // 2
    z = f"(1+0.18*exp(-t*7)+{zoom}*t/{d/speed:.3f})"
    vf = (f"[0:v]format=yuv420p,setpts=(PTS-STARTPTS)/{speed},fps=30,crop={cw}:{ch}:{cx}:{cy},"
          f"scale=w='trunc(1080*{z}/2)*2':h='trunc(1920*{z}/2)*2':eval=frame:flags=lanczos,"
          f"crop=1080:1920:x='(in_w-1080)/2+16*sin(t*55)*exp(-t*7)':y='(in_h-1920)/2+12*cos(t*47)*exp(-t*7)',"
          f"unsharp=5:5:0.6,eq=saturation=1.18:contrast=1.06,fade=in:st=0:d=0.12:color=white,setsar=1,format=yuv420p[v]")
    ext = r.get("ext", "mov"); f = os.path.join(SRC, src + "." + ext)
    if ext == "png":
        cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", str(d), "-i", f]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-to", str(end), "-i", f]
    if r["audio"]:
        af = f"[0:a]atempo={speed},aresample=44100,volume=0.8[aud]" if speed != 1 else "[0:a]aresample=44100,volume=0.8[aud]"
        cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[aud]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", vf,
                "-map", "[v]", "-map", "1:a", "-t", str(d / speed)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-ac", "2", out]
    run(cmd); return out

def esc(path): return path.replace(":", r"\:")

def build(v):
    name = v["name"]
    parts = [segment(s[0], s[1], s[2], i, name, s[3] if len(s) > 3 else 0.10, s[4] if len(s) > 4 else 1.0)
             for i, s in enumerate(v["segments"])]
    def vdur(f): return float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    cuts, acc = [], 0.0
    for p_ in parts[:-1]: acc += vdur(p_); cuts.append(acc)
    lst = os.path.join(TMP, name + ".txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    joined = os.path.join(TMP, name + "_joined.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", joined],
                               capture_output=True, text=True).stdout)
    filters = []
    for j, t in enumerate(v["texts"]):
        tf = os.path.join(TMP, f"{name}_t{j}.txt"); open(tf, "w").write(t["text"])
        st, en = t.get("start", 0), min(t.get("end", dur), dur - 0.04)
        size = t.get("size", 72); col = t.get("color", "white"); y = t.get("y", 300)
        fade = f"if(lt(t-{st},0.15),(t-{st})/0.15,1)"
        style = "box=1:boxcolor=black@0.55:boxborderw=20:borderw=3:bordercolor=black:"
        fs = f"'{size}*(1+0.3*max(0,1-(t-{st})/0.12))'"
        filters.append(
            f"drawtext=fontfile={FONT}:textfile={esc(tf)}:fontsize={fs}:fontcolor={col}:{style}"
            f"expansion=none:line_spacing=8:text_align=C:x=(w-text_w)/2:y={y}-text_h/2:alpha='{fade}':"
            f"enable='between(t,{st},{en})'")
    # end card with the game title
    game = v.get("game") or ("KRILLION" if name[:2] in ("01","02","03","04","05") else "ANIME FISHING")
    last = os.path.join(TMP, name + "_last.png"); end = os.path.join(TMP, name + "_end.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", joined, "-frames:v", "1", "-update", "1", last])
    gt = os.path.join(TMP, name + "_game.txt"); open(gt, "w").write(game.replace(" ", "\n"))
    sub = os.path.join(TMP, name + "_sub.txt"); open(sub, "w").write("PLAY NOW ON ROBLOX")
    srch = os.path.join(TMP, name + "_srch.txt"); open(srch, "w").write("search: " + game.title())
    ecol = "0x3CE0FF" if game == "KRILLION" else "0xFFD43B"
    evf = (f"scale=1080:1920,boxblur=28:2,eq=brightness=-0.32,fade=in:st=0:d=0.12:color=white,"
           f"drawtext=fontfile={FONT}:textfile={esc(gt)}:fontcolor={ecol}:borderw=10:bordercolor=black:"
           f"expansion=none:text_align=C:line_spacing=-20:fontsize='165*(1+0.5*max(0,1-t/0.18))':x=(w-text_w)/2:y=1000-text_h-30,"
           f"drawtext=fontfile={FONT}:textfile={esc(sub)}:fontcolor=white:box=1:boxcolor=0xE6262A:boxborderw=24:"
           f"expansion=none:fontsize=64:x=(w-text_w)/2:y=1040:enable='gte(t,0.25)',"
           f"drawtext=fontfile={FONT}:textfile={esc(srch)}:fontcolor=white:borderw=6:bordercolor=black:"
           f"expansion=none:fontsize=50:x=(w-text_w)/2:y=1190:enable='gte(t,0.45)',format=yuv420p")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", "2.0", "-i", last,
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-vf", evf, "-t", "2.0",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-ac", "2", end])
    lst2 = os.path.join(TMP, name + "_2.txt"); open(lst2, "w").write(f"file '{joined}'\nfile '{end}'\n")
    full = os.path.join(TMP, name + "_full.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst2, "-c", "copy", full])
    out = os.path.join(OUT, name + ".mp4")
    SFX = os.path.join(S, "sfx")
    events = [("whoosh", max(0, c - 0.16), 0.55) for c in cuts]
    starts = sorted({round(t.get("start", 0), 2) for t in v["texts"]})
    events += [("pop", st, 0.45) for st in starts if st > 0.05]
    events += [("whoosh", max(0, dur - 0.16), 0.6), ("boom", dur, 0.9), ("pop", dur + 0.25, 0.45), ("pop", dur + 0.45, 0.35)]
    ins = ["-i", full]; fc = []
    for k, (snd, at, vol) in enumerate(events):
        ins += ["-i", os.path.join(SFX, snd + ".wav")]
        ms = int(at * 1000)
        fc.append(f"[{k+1}:a]volume={vol},adelay={ms}|{ms}[s{k}]")
    vo = os.path.join(S, "vo", name + ".wav"); n_in = len(events) + 1
    mix = "[g]" + "".join(f"[s{k}]" for k in range(len(events)))
    fc.append("[0:a]volume=0.4[g]")
    if os.path.exists(vo):
        vlen = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vo],
                                    capture_output=True, text=True).stdout)
        total = dur + 2.0; tempo = max(1.0, vlen / (total - 0.35))
        ins += ["-i", vo]
        fc.append(f"[{n_in}:a]aresample=44100,atempo={tempo:.3f},volume=1.7,adelay=150|150,aformat=channel_layouts=stereo[vo]")
        mix += "[vo]"; n_in += 1
    fc.append(f"{mix}amix=inputs={n_in}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
    fc.append("[0:v]" + ",".join(filters) + "[vout]")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", out])
    print(name, round(dur, 1), "s ->", out)

if __name__ == "__main__":
    vids = json.load(open(os.path.join(S, "videos.json")))
    only = sys.argv[1:]
    for v in vids:
        if not only or v["name"] in only: build(v)
