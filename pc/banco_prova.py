"""
perfette, fare test"; "scarica, analizza e poi elimina"; "mettilo in schedule").
APSAA (zenodo.org/records/14096541, CC BY 4.0): 32 notti, audio + eventi della polisonnografia annotati.
Per ogni soggetto: scarica solo il suo .wav (~200 MB, zip letto a pezzi), misura, CANCELLA il wav, tiene i numeri in
banco/banco_prova.csv (soggetto, misura, valore, versione = commit di sonno_tex). Soggetti gia' fatti con la stessa
versione si saltano: dopo ogni modifica ai modelli si rilancia e si confronta.
   python banco_prova.py [quanti_soggetti]
Misure:
  russare_precisione / russare_richiamo: EfficientAT (Snoring >= 0.15 come categorie.py, finestre 5 s) contro 'Snore'
  pause_trovate: quante apnee/ipopnee annotate hanno una pausa di respiro.py sopra (+-5 s)
  pause_vere:    quante pause di respiro.py cadono su un'apnea/ipopnea (+-5 s)
"""
import csv, os, subprocess, sys
import numpy as np
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import respiro, zip_remoto

URL = "https://zenodo.org/api/records/14096541/files/APSAA.zip/content"
DATI = r"C:\sonno_dataset\apsaa"
OUT = os.path.join(QUI, "banco", "banco_prova.csv")
MODELLO = os.path.join(QUI, "efficientat", "mn10_as.onnx")
APNEE = {"Obstructive Apnea", "Central Apnea", "Mixed Apnea", "Hypopnea"}
PEZZO = 1800  # s di audio in memoria alla volta (una notte intera a 32 kHz = 3 GB)


def versione():
    """(nota rimossa)"""
    import hashlib
    h = hashlib.sha1()
    for f in ("respiro.py", "banco_prova.py"):
        h.update(open(os.path.join(QUI, f), "rb").read())
    return h.hexdigest()[:7]


def durata(wav):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                capture_output=True, text=True).stdout)


def pezzo(wav, sr, da, lung):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-ss", str(da), "-t", str(lung), "-i", wav, "-ac", "1",
                                         "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout, "<f4")


def eventi(ann):
    """{nome: [(inizio_s, fine_s)]} da Annotations.csv (Start_Time hh:mm:ss dall'inizio dell'audio)."""
    out = {}
    for r in csv.DictReader(open(ann, encoding="utf-8-sig")):
        h, m, s = (float(x) for x in r["Start_Time"].split(":"))
        a = h * 3600 + m * 60 + s
        out.setdefault(r["Event_Name"], []).append((a, a + float(r["Duration"])))
    return out


def russare(wav, dur, sess):
    """Probabilita' Snoring (classe 43) ogni 5 s, a pezzi."""
    p = []
    for da in range(0, int(dur), PEZZO):
        w = pezzo(wav, 32000, da, PEZZO)
        p += [float(sess.run(None, {"waveform": w[i:i + 160000].reshape(1, -1)})[0][0, 43])
              for i in range(0, len(w) - 160000 + 1, 160000)]
    return np.array(p)


def pause(wav, dur):
    env = np.concatenate([respiro.inviluppo(pezzo(wav, respiro.SR, da, PEZZO)) for da in range(0, int(dur), PEZZO)])
    return respiro.pause(respiro.picchi(env))


def misura(wav, ev):
    import onnxruntime as ort
    dur = durata(wav)
    p = russare(wav, dur, ort.InferenceSession(MODELLO, providers=["CPUExecutionProvider"]))
    vero = np.array([any(a < 5 * (k + 1) and b > 5 * k for a, b in ev.get("Snore", [])) for k in range(len(p))])
    detto = p >= 0.15
    ps = pause(wav, dur)
    ap = [e for n in APNEE for e in ev.get(n, [])]
    sopra = lambda x, y, a, b: x < b + 5 and x + y > a - 5
    return {"ore_audio": dur / 3600,
            "russare_precisione": (detto & vero).sum() / max(detto.sum(), 1),
            "russare_richiamo": (detto & vero).sum() / max(vero.sum(), 1),
            "russare_finestre_vere": int(vero.sum()),
            "apnee_annotate": len(ap), "pause_bot": len(ps),
            "pause_trovate": sum(any(sopra(x, y, a, b) for x, y in ps) for a, b in ap) / max(len(ap), 1),
            "pause_vere": sum(any(sopra(x, y, a, b) for a, b in ap) for x, y in ps) / max(len(ps), 1)}


def main(quanti=2):
    v = versione()
    fatti = {r["soggetto"] for r in csv.DictReader(open(OUT, encoding="utf-8"))} if os.path.exists(OUT) else set()
    fatti = {s for s in fatti if s.endswith("@" + v)}
    z = zip_remoto.apri(URL)
    soggetti = sorted({n.split("/")[0] for n in z.namelist() if n.endswith(".wav")})
    nuovi = [s for s in soggetti if f"{s}@{v}" not in fatti][:quanti]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for s in nuovi:
        ann = zip_remoto.estrai(z, f"{s}/{s}_Annotations.csv", DATI)
        wav = zip_remoto.estrai(z, f"{s}/{s}.wav", DATI)
        try:
            m = misura(wav, eventi(ann))
        finally:
            os.remove(wav)  # scarica, analizza, ELIMINA: resta solo il csv delle annotazioni (pochi KB)
        nuovo = not os.path.exists(OUT)
        with open(OUT, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if nuovo:
                w.writerow(["soggetto", "misura", "valore"])
            w.writerows([[f"{s}@{v}", k, f"{x:.3f}" if isinstance(x, float) else x] for k, x in m.items()])
        print(s, {k: round(x, 2) if isinstance(x, float) else x for k, x in m.items()}, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
