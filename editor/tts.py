import json, re, sys, os
import numpy as np, onnxruntime as ort, wave
S = os.path.dirname(os.path.abspath(__file__))
D = {}
for f in ["us_silver.json", "us_gold.json"]:
    D.update(json.load(open(os.path.join(S, "misaki/misaki/data", f))))
VOCAB = json.load(open(os.path.join(S, "kokoro-onnx/src/kokoro_onnx/config.json")))["vocab"]
MANUAL = {
    "krillion": "kɹˈɪljən", "roblox": "ɹˈOblɑks", "zenichi": "zɛnˈiʧi", "lelouch": "ləlˈuʃ",
    "ryu": "ɹjˈu", "yuta": "jˈutə", "pov": "pˌiOvˈi", "i": "ˈI", "a": "ə", "the": "ðə",
}
VOICED_END = set("bdgvðzʒʤmnŋlɹwjaeiouɑæʌɔəɛɪʊɜɚAIOWYᵊ")

def word(w):
    lw = w.lower()
    if lw in MANUAL: return MANUAL[lw]
    for k in (w, lw):
        v = D.get(k)
        if v: return v if isinstance(v, str) else (v.get("DEFAULT") or next(iter(v.values())))
    for suf, fn in [("'s", None), ("s", None), ("es", None), ("ed", None), ("ing", "ɪŋ"), ("est", "ɪst"), ("er", "əɹ")]:
        if lw.endswith(suf) and len(lw) > len(suf) + 2:
            base = lw[: -len(suf)]
            cands = [base, base + "e"] if suf in ("ed", "ing", "est", "er", "es") else [base]
            for b in cands:
                bp = D.get(b) or MANUAL.get(b)
                if bp:
                    if not isinstance(bp, str): bp = bp.get("DEFAULT") or next(iter(bp.values()))
                    last = bp.rstrip("ˈˌ")[-1]
                    if suf in ("s", "'s", "es"):
                        if last in "szʃʒʧʤ": return bp + "ᵻz"
                        return bp + ("z" if last in VOICED_END else "s")
                    if suf == "ed":
                        if last in "td": return bp + "ᵻd"
                        return bp + ("d" if last in VOICED_END else "t")
                    return bp + fn
    print("UNKNOWN:", w, file=sys.stderr); return lw

def g2p(text):
    out = []
    for tok in re.findall(r"[A-Za-z']+|[.,!?;:…—]", text.replace("...", "…")):
        out.append(word(tok) if tok[0].isalpha() else tok)
    s = ""
    for t in out:
        s += t if t in ".,!?;:…—" else ((" " if s else "") + t)
    return s

sess = None
def synth(text, voice="am_michael", speed=1.1):
    global sess
    if sess is None: sess = ort.InferenceSession(os.path.join(S, "kmodel/kokoro.onnx"))
    ph = g2p(text)
    toks = [VOCAB[c] for c in ph if c in VOCAB][:510]
    style = np.load(os.path.join(S, "kmodel/voices.bin"))[voice][len(toks) - 1]
    names = [i.name for i in sess.get_inputs()]
    feed = {names[0]: np.array([[0, *toks, 0]], dtype=np.int64), "style": style.astype(np.float32),
            "speed": np.array([speed], dtype=np.float32 if sess.get_inputs()[2].type == "tensor(float)" else np.int32)}
    audio = sess.run(None, feed)[0]
    return ph, np.asarray(audio).reshape(-1)

if __name__ == "__main__":
    scripts = json.load(open(os.path.join(S, "vo_scripts.json")))
    os.makedirs(os.path.join(S, "vo"), exist_ok=True)
    for name, text in scripts.items():
        ph, a = synth(text, voice=sys.argv[1] if len(sys.argv) > 1 else "am_michael")
        with wave.open(os.path.join(S, "vo", name + ".wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        print(name, round(len(a) / 24000, 1), "s |", ph)
