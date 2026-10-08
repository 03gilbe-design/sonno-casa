"""
telefono, hai la posizione 3D: e' il tuo momento per imparare come un suono arriva a X").
   python raccolta.py [bocca] [nome]  -> la bocca (A56 default) suona calibra.wav (6,4 min: sweep, suo russare e
       respiro VERI, musica slowed+reverb, mix, ambiente); A56, A21s e PC Intel registrano. Salva tutto in
       C:/sonno_audio/array/raccolta/<nome>/ con scaletta, scena e distanze dell'ultima prova.
   python raccolta.py analizza <nome> -> per ogni pezzo e orecchio: livello per ottava rispetto a chi suona
       (= come arriva X a Y: perdita per frequenza) + correlazione di forma (= quanto e' deformato).
"""
import json, os, shutil, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b  # prima di scipy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova as p
import ripetuti as r
import sweep as sw

CAL = "C:/sonno_audio/calibra"
BASE = "C:/sonno_audio/array/raccolta"
ORECCHI = {"A56": "racc_a56.m4a", "A21s": "racc_a21s.m4a", "PCintel": "racc_pc_intel.wav"}
DIAGONALE = 4.9  # m: stanza ~3 x 3,8 (sua descrizione). Una distanza oltre = sospetta (eco al posto del diretto)


def registra(bocca="A56", nome="raccolta"):
    out = os.path.join(BASE, nome); os.makedirs(out, exist_ok=True)
    dur = len(b.decodifica(os.path.join(CAL, "calibra.wav"))) / b.SR
    dove = {"A56": b.A56, "A21s": "192.0.2.184"}[bocca]
    subprocess.run(["scp", "-q", "-P", "8022", os.path.join(CAL, "calibra.wav"), f"{dove}:calibra.wav"], check=True)
    rec_cmd = p.REC.replace("limit 90000", f"limit {int((dur + 60) * 1000)}")
    c21 = a21s_raggiungibile()
    if not c21:
        print("A21s non raggiungibile: raccolgo con A56 + PC")
    g56 = p.Guscio(p.SSH56)
    g21 = p.Guscio(p.SSH21) if c21 else type("Muto", (), {"manda": lambda s, c: None, "chiudi": lambda s: None})()
    p.voci(); p.parla("silenzio, test")
    g21.manda("echo $(date -d '+12 min' -Iseconds) > ~/sonno_bot/PAUSA; pkill -f '^bash .*home/[r]ec.sh'; "
              f"termux-microphone-record -q; rm -f ~/racc_a21s.m4a; termux-volume music 15; {rec_cmd} $HOME/racc_a21s.m4a")
    g56.manda(f"termux-microphone-record -q; rm -f ~/racc_a56.m4a; termux-volume music {r.VOL56}; {rec_cmd} $HOME/racc_a56.m4a")
    era_muto = b.muto_pc(False)
    pc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={r.nome_dshow(r.MIC_INTEL)}",
                           "-t", str(int(dur + 30)), "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, ORECCHI["PCintel"])],
                          stdin=subprocess.PIPE)
    t0 = time.time()
    try:
        time.sleep(2.5)
        (g56 if bocca == "A56" else g21).manda("play-audio calibra.wav &")
        time.sleep(dur + 1.0)
        p.parla("fine test, analizzo")
    finally:
        try:
            pc.communicate(b"q", timeout=10)
        except Exception:
            pc.kill()
        g56.manda("termux-microphone-record -q"); g21.manda("termux-microphone-record -q"); g56.chiudi(); g21.chiudi()
        b.muto_pc(era_muto)
        if c21:
            p.ripristina_a21s()
    sorgenti = [f"{b.A56}:racc_a56.m4a"] + (["192.0.2.184:racc_a21s.m4a"] if c21 else [])
    for f in ORECCHI.values():  # niente file vecchi
        if os.path.exists(os.path.join(b.OUT, f)) and f != ORECCHI["PCintel"]:
            os.remove(os.path.join(b.OUT, f))
    subprocess.run(["scp", "-q", "-P", "8022"] + sorgenti + [b.OUT], check=True)
    for f in ORECCHI.values():
        if os.path.exists(os.path.join(b.OUT, f)):
            shutil.copy(os.path.join(b.OUT, f), out)
    shutil.copy(os.path.join(CAL, "scaletta.json"), out)
    json.dump({"bocca": bocca, "quando": time.strftime("%Y-%m-%d %H:%M"), "durata_s": round(time.time() - t0),
               "distanze_ultima_prova": r.RIS}, open(os.path.join(out, "info.json"), "w"), indent=1)
    print("salvato in", out)


def a21s_raggiungibile():
    try:
        return "ok" in subprocess.run(p.SSH21 + ["echo ok"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return False


def distanza_a56_pc():
    """
    Tutti e due suonano i loro 3 bip e registrano; d = c/2 * ((tA56[PC]-tA56[A56]) - (tPC[PC]-tPC[A56]))."""
    p.voci()
    for chi in ("A56", "PC"):
        b.scrivi_wav(os.path.join(b.OUT, f"bip_{chi}.wav"), r.treno(r.BOCCHE[chi]), pausa_prima=0.1)
    subprocess.run(["scp", "-q", "-P", "8022", os.path.join(b.OUT, "bip_A56.wav"), f"{b.A56}:"], check=True)
    g56 = p.Guscio(p.SSH56); p.parla("silenzio, test")
    g56.manda(f"termux-microphone-record -q; rm -f ~/d2_a56.m4a; termux-volume music {r.VOL56}; {p.REC} $HOME/d2_a56.m4a")
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={r.nome_dshow(r.MIC_INTEL)}",
                           "-t", "30", "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, "d2_pc.wav")], stdin=subprocess.PIPE)
    import winsound
    try:
        time.sleep(2.5); p.parla("bip insieme")
        g56.manda("play-audio bip_A56.wav &")
        winsound.PlaySound(os.path.join(b.OUT, "bip_PC.wav"), winsound.SND_FILENAME)
        time.sleep(1.0); p.parla("fine test, analizzo")
    finally:
        try:
            pc.communicate(b"q", timeout=10)
        except Exception:
            pc.kill()
        g56.manda("termux-microphone-record -q"); g56.chiudi(); b.muto_pc(era_muto); b.volume_pc(vol_pc)
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:d2_a56.m4a", b.OUT], check=True)
    x56, xpc = b.decodifica(os.path.join(b.OUT, "d2_a56.m4a")), b.decodifica(os.path.join(b.OUT, "d2_pc.wav"))
    t = {(o, e): r.arrivi(x, r.BOCCHE[e])[0] for o, x in (("A56", x56), ("PC", xpc)) for e in ("A56", "PC")}
    d = b.C / 2 * ((t["A56", "PC"] - t["A56", "A56"]) - (t["PC", "PC"] - t["PC", "A56"]))
    print(f"A56 <-> PC: {np.median(d):.3f} m  (per bip {np.round(d, 3)})  dispersione {np.std(d) * 100:.1f} cm")
    if np.median(d) > DIAGONALE:
        vecchio = r.PRIMO; r.PRIMO = 0.3
        t = {(o, e): r.arrivi(x, r.BOCCHE[e])[0] for o, x in (("A56", x56), ("PC", xpc)) for e in ("A56", "PC")}
        r.PRIMO = vecchio
        d = b.C / 2 * ((t["A56", "PC"] - t["A56", "A56"]) - (t["PC", "PC"] - t["PC", "A56"]))
        print(f"  SOSPETTA (> diagonale {DIAGONALE} m): col primo arrivo al 30% -> {np.median(d):.3f} m")
    r.RIS["A56-PC"] = (float(np.median(d)), float(np.std(d)))
    return float(np.median(d))


def allinea(x, ref):
    """Ritardo di x rispetto a ref (s) dal primo sweep della scaletta (correlazione via FFT)."""
    from scipy.signal import correlate
    n = int(20 * b.SR)
    c = np.abs(correlate(x[: n * 2], ref[:n], "valid", method="fft")) if len(x) > n else np.zeros(1)
    return int(np.argmax(c))


def analizza(nome="raccolta"):
    from scipy.signal import correlate
    out = os.path.join(BASE, nome); info = json.load(open(os.path.join(out, "info.json")))
    ref = b.decodifica(os.path.join(CAL, "calibra.wav")); sc = json.load(open(os.path.join(out, "scaletta.json")))
    import wave
    with wave.open(os.path.join(CAL, "calibra.wav")) as w:
        fattore = b.SR / w.getframerate()
    sc = [dict(pz, da=int(pz["da"] * fattore), a=int(pz["a"] * fattore)) for pz in sc]
    rec = {o: b.decodifica(os.path.join(out, f)) for o, f in ORECCHI.items() if os.path.exists(os.path.join(out, f))}
    rit = {o: allinea(x, ref) for o, x in rec.items()}
    righe = []
    print(f"bocca {info['bocca']} | per pezzo: dB per ottava RISPETTO al file originale (125..8k) | forma = correlazione 0-1")
    for pz in sc:
        if pz["lab"] == "ambiente":
            continue
        a, z = pz["da"], pz["a"]; s = ref[a:z]
        for o, x in rec.items():
            m = int(0.2 * b.SR); lo = max(0, rit[o] + a - m); seg = x[lo: rit[o] + z + m]
            if len(seg) < len(s):
                continue
            k = int(np.argmax(np.abs(correlate(seg, s, "valid", method="fft"))))
            y = seg[k: k + len(s)]
            perdita = sw.bande(y) - sw.bande(s)
            forma = float(np.max(np.abs(correlate(y, s, "full", method="fft"))) / (np.linalg.norm(y) * np.linalg.norm(s) + 1e-12))
            righe.append({"pezzo": pz["lab"], "vol": pz["vol"], "orecchio": o, "perdita_dB": np.round(perdita, 1).tolist(),
                          "forma": round(forma, 3)})
            print(f"{pz['lab']:20s} v{pz['vol']:<4} -> {o:8s}" + "".join(f"{v:7.1f}" for v in perdita) + f"   forma {forma:.2f}")
    json.dump(righe, open(os.path.join(out, "come_arriva.json"), "w"), indent=1)
    print("salvato", os.path.join(out, "come_arriva.json"))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["analizza"]:
        analizza(a[1] if len(a) > 1 else "raccolta")
    else:
        registra(a[0] if a else "A56", a[1] if len(a) > 1 else "raccolta")
        analizza(a[1] if len(a) > 1 else "raccolta")
