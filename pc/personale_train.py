"""Modello PERSONALE: dataset (taratura + clip giudicate) -> embedding YAMNet (cache) -> leave-one-night-out
-> confronto con il sistema attuale (regole YAMNet, PANNs, EfficientAT) -> installa sul telefono SOLO se migliore.
   python personale_train.py [--no-installa]      scrive C:\\sonno_audio\\modello_personale_report.txt

Scelte (motivate):
- clip giudicate: etichetta = verita() di rigenera_cats.py (sequenza > era > detto se giusto=1 > esclusa), multi-categoria
  ridotta alla principale (PRIORITA'). Escluse: presenza.csv (non_dataset/dispositivo_suona; fuori_stanza solo russa/respiro)
  ed etichette_dubbie.csv; contate nel report.
- giudizi.csv non si riscrive: la mappa (mappa_etichette.json) si applica qui in lettura.
"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import csv, json, os, re, subprocess, sys, time
from datetime import datetime, timedelta
import numpy as np
sys.path.insert(0, r"C:\sonno_tex")
from mappa_etichette import mappa, principale
from rigenera_cats import verita

R = r"C:\sonno_audio"
P = R + r"\personale"
CAL, CLIP, CACHE = R + r"\cal", P + r"\clip", P + r"\cache"
OUT = r"C:\sonno_tex\modello_personale.npz"
REPORT = R + r"\modello_personale_report.txt"
STATO = P + r"\stato_allenamento.json"
import a21
SSH = ["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", a21.ip()]
SR, HOP, MIN_ESEMPI = 16000, 0.48, 5
RUSSA, RESPIRO, VOCE, TOSSE = 38, 36, 0, 42
SILENZI = ("silenzio",)


PRIORITA = ("russa", "respiro", "movimento")
ANALISI = r"C:\sonno_bot\analisi"


def _presenza():
    """[(inizio, fine, stato)] da presenza.csv; solo stati che escludono. fine vuota = inizio+20 min (ponytail: stima)."""
    out = []
    for r in csv.DictReader(open(ANALISI + r"\presenza.csv", encoding="utf-8-sig")):
        if r["stato"] not in ("non_dataset", "dispositivo_suona", "fuori_stanza"):
            continue
        try:
            i = datetime.strptime(r["inizio"], "%Y-%m-%dT%H:%M")
            f = datetime.strptime(r["fine"], "%Y-%m-%dT%H:%M") if r["fine"] else i + timedelta(minutes=20)
        except ValueError:
            continue
        out.append((i, f, r["stato"]))
    return out


def _dubbie():
    # ponytail: dubbie = escluse (peso basso non supportato dal fit); upgrade: sample_weight in fit
    return {r["clip_ora"] for r in csv.DictReader(open(ANALISI + r"\etichette_dubbie.csv", encoding="utf-8-sig"))}


def _filtra(cats, dt, pres):
    """toglie le categorie escluse dalla presenza al momento dt (fuori_stanza: solo russa/respiro)."""
    for i, f, st in pres:
        if dt and i <= dt <= f:
            cats = [c for c in cats if st == "fuori_stanza" and c not in ("russa", "respiro")]
    return cats


def notte(dt):  # la notte e' la data in cui e' iniziata: prima di mezzogiorno appartiene a ieri
    return (dt - timedelta(hours=12)).strftime("%Y%m%d")


def dt_da_nome(n):
    m = re.search(r"(\d{8})_(\d{4})", n)
    return datetime.strptime(m[1] + m[2], "%Y%m%d%H%M") if m else None


def pull_giudizi():
    r = subprocess.run(SSH + ["cat ~/sonno_bot/giudizi.csv"], capture_output=True, timeout=60)
    if r.returncode == 0 and r.stdout:
        open(P + r"\giudizi.csv", "wb").write(r.stdout)


def costruisci():
    """-> (esempi, esclusi). esempio = dict(path, nome, label, main, dev, notte, src)."""
    es, escl = [], {}
    for f in sorted(os.listdir(CAL)):
        if not f.endswith((".m4a", ".wav")):
            continue
        suono, mic, ora = f.rsplit(".", 1)[0].split("__")[:3]
        dt = dt_da_nome(ora)
        label = mappa(suono)
        if label.startswith("silenzio") and not dt:  # ambiente calibra_*: gruppo = microfono/posizione
            n = "cal_" + mic
        else:
            n = notte(dt) if dt else "cal_" + mic
        # taratura: .mp3 e .wav dello stesso audio -> tengo il .wav
        if f.endswith(".mp3"):
            continue
        es.append(dict(path=f"{CAL}\\{f}", nome=f, label=label, main=label.split("/")[0], dev=mic, notte=n, src="taratura"))
    # ponytail: regola unica verita() (rigenera_cats.py); ultima riga per clip, come rigenera_cats. Classificatore a
    # ETICHETTA SINGOLA (softmax su `main`): clip multi-categoria -> categoria principale per PRIORITA' (PRIORITA').
    # Upgrade: one-vs-rest per russa/respiro/movimento se serve usare tutte le categorie insieme.
    G = {r["clip"]: r for r in csv.DictReader(open(P + r"\giudizi.csv", encoding="utf-8-sig"))}
    pres, dubbie = _presenza(), _dubbie()
    for clip, r in G.items():
        path = f"{CLIP}\\{clip}"
        if not os.path.exists(path):
            escl[clip] = "file assente"; continue
        cats, noseq = verita(r)
        dt = dt_da_nome(clip)
        if not cats:
            escl[clip] = "senza verita"; continue
        if dt and dt.strftime("%Y-%m-%dT%H:%M") in dubbie:
            escl[clip] = "etichetta dubbia"; continue
        cats = _filtra(cats, dt, pres)
        if not cats:
            escl[clip] = "presenza (non_dataset/dispositivo/fuori_stanza)"; continue
        main = next((c for c in PRIORITA if c in cats), cats[0])
        es.append(dict(path=path, nome=clip, label=main, main=main, dev=(r.get("dispositivo") or "A21s"),
                       notte=notte(dt), src="giudizio", cats=cats))
    return es, escl


def carica(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(pcm, np.float32)


_sess = None


def feat(e):
    """embedding (n,1024), score YAMNet (n,521) e dB per frame, in cache."""
    global _sess
    os.makedirs(CACHE, exist_ok=True)
    cp = f"{CACHE}\\{e['nome']}.{os.path.getsize(e['path'])}.npz"
    if os.path.exists(cp):
        z = np.load(cp); return z["emb"], z["sc"], z["db"]
    import onnxruntime as ort
    _sess = _sess or ort.InferenceSession(r"C:\sonno_tex\yamnet\yamnet.onnx", providers=["CPUExecutionProvider"])
    w = carica(e["path"])
    if len(w) < SR:
        return None
    outs = [_sess.run(None, {"waveform": w[i:i + SR * 60]}) for i in range(0, len(w) - SR, SR * 60)]
    sc, emb = np.concatenate([o[0] for o in outs]), np.concatenate([o[1] for o in outs])
    n = int(HOP * SR)
    db = np.array([20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(sc))])
    np.savez(cp, emb=emb, sc=sc.astype(np.float16), db=db)
    return emb, sc, db


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else 0.0
    return p, r, f


def curva(X, y, nt, fid, nfile, fit, seeds=3):
    """
    intere), media su `seeds` sorteggi. +10 esempi = retta F1 ~ a + b*ln(n) sui 4 punti: estrapolazione INCERTA."""
    rng = np.random.default_rng(0)
    out = {}
    for c in nfile:
        if nfile[c] < MIN_ESEMPI:
            continue
        files = np.unique(fid[y == c]); n = len(files); v = y == c; pts = []
        for fr in (0.25, 0.5, 0.75, 1.0):
            f1s = []
            for _ in range(seeds if fr < 1 else 1):
                keep = rng.choice(files, max(1, round(fr * n)), replace=False) if fr < 1 else files
                mask = ~v | np.isin(fid, keep)
                pred = np.full(len(y), "incerto", dtype=object)
                for night in set(nt):
                    te = nt == night; tr = ~te & mask
                    if te.all() or len(set(y[tr])) < 2:
                        continue
                    mu, sd, clf = fit(X[tr], y[tr])
                    pr = clf.predict_proba((X[te] - mu) / sd)
                    pred[te] = np.where(pr.max(1) > 0.6, clf.classes_[pr.argmax(1)], "incerto")
                f1s.append(prf(((pred == c) & v).sum(), ((pred == c) & ~v).sum(), ((pred != c) & v).sum())[2])
            pts.append((max(1, round(fr * n)), float(np.mean(f1s))))
        ns, fs = np.array([p[0] for p in pts], float), np.array([p[1] for p in pts])
        b = np.polyfit(np.log(ns), fs, 1)[0]
        out[c] = dict(punti=pts, pendenza=float(b), guadagno10=float(min(b * (np.log(n + 10) - np.log(n)), 1 - fs[-1])), n=n)
    return out


def prova():
    """Prova a secco (--prova): etichette per categoria prima (logica vecchia) e dopo; nessun feature/training."""
    from collections import Counter
    pull = [r for r in csv.DictReader(open(P + r"\giudizi.csv", encoding="utf-8-sig"))]
    righe = {}
    for r in pull:
        righe.setdefault(r["clip"], []).append(r)
    vec = Counter()
    for clip, rr in righe.items():
        if not os.path.exists(f"{CLIP}\\{clip}") or any(re.search(r"[>\[\]+]", r.get("sequenza", "") or "") for r in rr):
            continue
        labs = {mappa(mappa(r["era"].strip() or r["detto"]) if r["giusto"] == "0" else mappa(r["detto"])) for r in rr}
        if len({l.split("/")[0] for l in labs}) == 1:
            vec[sorted(labs)[0].split("/")[0]] += 1
    es, escl = costruisci()
    nuo = Counter(e["main"] for e in es if e["src"] == "giudizio")
    print("clip giudicate per categoria (principale)  PRIMA:", dict(sorted(vec.items())), "| totale", sum(vec.values()))
    print("                                           DOPO :", dict(sorted(nuo.items())), "| totale", sum(nuo.values()))
    print("multi-categoria dopo:", sum(len(e["cats"]) > 1 for e in es if e["src"] == "giudizio"), "| tutte le cats DOPO:",
          dict(sorted(Counter(c for e in es if e["src"] == "giudizio" for c in e["cats"]).items())))
    print("escluse:", dict(Counter(escl.values())))


def main():
    if "--prova" in sys.argv:
        return prova()
    t_start = time.time()
    from sklearn.linear_model import LogisticRegression
    if "--no-pull" not in sys.argv:
        pull_giudizi()
    es, escl = costruisci()
    D = []
    for e in es:
        f = feat(e)
        if f:
            e["emb"], e["sc"], e["db"] = f[0], f[1].astype(np.float32), f[2]; D.append(e)
    amb = [e["db"] for e in D if e["label"] == "silenzio/ambiente"]
    soglia = float(np.median(np.concatenate(amb)) + 4) if amb else -200.0
    X, y, nt, fid, SC, DB, BASE = [], [], [], [], [], [], []
    for k, e in enumerate(D):
        keep = np.ones(len(e["db"]), bool) if e["main"] in SILENZI else e["db"] > soglia
        base = np.percentile(e["db"], 20)
        for i in np.where(keep)[0]:
            X.append(e["emb"][i]); y.append(e["main"]); nt.append(e["notte"]); fid.append(k)
            SC.append(e["sc"][i]); DB.append(e["db"][i]); BASE.append(base)
    X, y, nt, fid, SC, DB, BASE = map(np.array, (X, y, nt, fid, SC, DB, BASE))
    nfile = {c: sum(e["main"] == c for e in D) for c in sorted(set(y))}
    nnotti = {c: len({e["notte"] for e in D if e["main"] == c}) for c in nfile}

    def fit(Xa, ya):
        mu, sd = Xa.mean(0), Xa.std(0) + 1e-6
        return mu, sd, LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced").fit((Xa - mu) / sd, ya)

    # --- leave-one-night-out, stessa regola del telefono (prob>0.6 altrimenti 'incerto')
    pred = np.full(len(y), "incerto", dtype=object)
    for n in sorted(set(nt)):
        te = nt == n
        if te.all() or len(set(y[~te])) < 2:
            continue
        mu, sd, clf = fit(X[~te], y[~te])
        pr = clf.predict_proba((X[te] - mu) / sd)
        pred[te] = np.where(pr.max(1) > 0.6, clf.classes_[pr.argmax(1)], "incerto")
    # --- sistema attuale (fallback del telefono, senza il filtro 'esterno': approssimato)
    base_flag = {"russa": SC[:, RUSSA] > 0.2, "voce": SC[:, VOCE] > 0.5, "tosse": SC[:, TOSSE] > 0.3,
                 "respiro": SC[:, RESPIRO] > 0.3, "movimento": DB > BASE + 12}
    R_ = {}
    for c in nfile:
        v = y == c
        R_[c] = dict(pers=prf(((pred == c) & v).sum(), ((pred == c) & ~v).sum(), ((pred != c) & v).sum()),
                     base=prf((base_flag[c] & v).sum(), (base_flag[c] & ~v).sum(), (~base_flag[c] & v).sum()) if c in base_flag else None)
    # falsi allarmi russa su frame NON russa (la cosa che conta di notte)
    nr = y != "russa"
    fa_p, fa_b = (pred[nr] == "russa").mean(), base_flag["russa"][nr].mean()
    # --- clip-level russa, anche PANNs / EfficientAT (hanno solo le clip del telefono)
    pe = {}
    for r in csv.reader(open(P + r"\pe\tutti.csv")):
        pe[r[0]] = float(r[1])
    cl = {"yamnet": [], "personale": [], "panns": [], "eff": [], "vero": []}
    for k, e in enumerate(D):
        if e["src"] != "giudizio":
            continue
        m = fid == k
        stem = e["nome"][:-4]
        if m.sum() == 0 or f"{stem}.panns" not in pe:
            continue
        cl["vero"].append(e["main"] == "russa")
        cl["yamnet"].append(base_flag["russa"][m].sum() >= 1)
        cl["personale"].append((pred[m] == "russa").sum() >= 3)
        cl["panns"].append(pe[f"{stem}.panns"] > 0.2)
        cl["eff"].append(pe.get(f"{stem}.eff", 0) > 0.2)
    v = np.array(cl["vero"])
    t_lono = time.time() - t_start
    CV = {}
    if "--no-curva" not in sys.argv:
        t0 = time.time(); CV = curva(X, y, nt, fid, nfile, fit); t_curva = time.time() - t0
        json.dump(CV, open(R + r"\curva_apprendimento.json", "w"))
    # --- decisione
    quest = {c: R_[c] for c in R_ if nfile[c] >= MIN_ESEMPI}
    motivi = []
    if "silenzio" not in quest:
        motivi.append("manca la classe silenzio (>=5 esempi)")
    if "russa" not in quest:
        motivi.append("russa: <5 esempi")
    else:
        if not quest["russa"]["pers"][2] > quest["russa"]["base"][2]:
            motivi.append(f"russa F1 {quest['russa']['pers'][2]:.2f} non batte YAMNet {quest['russa']['base'][2]:.2f}")
        if fa_p > fa_b:
            motivi.append(f"falsi allarmi russa {fa_p:.0%} > YAMNet {fa_b:.0%}")
    for c, q in quest.items():
        if c != "russa" and q["base"] and q["pers"][2] < q["base"][2] - 0.02:
            motivi.append(f"{c} F1 {q['pers'][2]:.2f} < YAMNet {q['base'][2]:.2f}")
    ok = not motivi
    # --- modello finale su tutto
    mu, sd, clf = fit(X, y)
    np.savez(OUT, mu=mu, sd=sd, W=clf.coef_, b=clf.intercept_, classi=clf.classes_.astype(str), soglia_db=soglia)
    inst = "NO"
    if ok and "--no-installa" not in sys.argv:
        r = subprocess.run(["scp", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", OUT, a21.ip() + ":modello_personale.npz"], capture_output=True)
        inst = "SI (copiato sul telefono)" if r.returncode == 0 else f"scp fallito: {r.stderr[:80]}"
    # --- report
    L = [f"Modello personale {datetime.now():%Y-%m-%d %H:%M} - esempi (file/notti): " +
         ", ".join(f"{c} {nfile[c]}/{nnotti[c]}" + (" POCHI DATI" if nfile[c] < MIN_ESEMPI else "") for c in nfile),
         f"Esclusi dall'allenamento: {len(escl)} clip ("
         f"{sum('presenza' in s for s in escl.values())} presenza, {sum('dubbia' in s for s in escl.values())} dubbie, "
         f"{sum('verita' in s for s in escl.values())} senza verita); frame usati {len(y)}, {len(set(nt))} notti/sessioni, soglia {soglia:.1f} dB"]
    L.append("Per classe, frame, leave-one-night-out (prec/rich/F1) personale | YAMNet-regole:")
    for c, q in R_.items():
        f = lambda t: "n/d" if t is None else f"{t[0]:.2f}/{t[1]:.2f}/{t[2]:.2f}"
        L.append(f"  {c:10s} {f(q['pers'])} | {f(q['base'])}" + ("  (pochi dati: non giudicata)" if nfile[c] < MIN_ESEMPI else ""))
    L.append(f"Falsi allarmi russa sui frame non-russa: personale {fa_p:.0%}, YAMNet {fa_b:.0%}")
    if v.sum():
        def tf(k):
            p = np.array(cl[k]); return f"{k} {(p & v).sum()}/{v.sum()} trovate, {(p & ~v).sum()} falsi su {(~v).sum()}"
        L.append("Clip russa (giudicate, n=%d): " % len(v) + "; ".join(tf(k) for k in ("yamnet", "personale", "panns", "eff")))
    if CV:
        L.append("Curva di apprendimento (F1 leave-one-night-out, % dei file della classe; +10 = estrapolazione INCERTA):")
        for c, q in sorted(CV.items(), key=lambda kv: -kv[1]["guadagno10"]):
            L.append(f"  {c:10s} " + "  ".join(f"{n}f={f:.2f}" for n, f in q["punti"]) + f"  | +10 esempi: {q['guadagno10']:+.2f} F1")
        L.append(f"Tempo: dataset+LONO+modello {t_lono:.0f} s; curva {t_curva:.0f} s")
    L.append(f"Installato: {inst}" + ("" if ok else " - " + "; ".join(motivi)))
    open(REPORT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump({"data": datetime.now().strftime("%Y-%m-%d"), "n_giudizi": sum(1 for _ in open(P + r"\giudizi.csv", encoding="utf-8-sig")) - 1,
               "installato": ok}, open(STATO, "w"))
    print("\n".join(L))


if __name__ == "__main__":
    main()
