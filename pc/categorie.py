"""
"non ho ancora visto categorizzare i momenti dove russo, respiro, con modelli precisi"; "ma il modello categorizza un
botto di possibili robe"). Righe = 5 fisse (russare, respiro, voce, tosse, musica/rumore) + le ALTRE categorie piu'
forti di quella notte, scelte dai dati. Colore = quanto il modello e' sicuro (chiaro = no, scuro = si').
Usa rec/dataset/<blocco>.npz; se manca lo calcola (solo per i blocchi dell'intervallo).
"""
import glob, os, sys
from datetime import datetime, timedelta
import numpy as np
sys.path.insert(0, os.path.expanduser("~"))
import conferma

FISSE = [("Russare", ["Snoring"], "russa"), ("Respiro", ["Breathing", "Gasp", "Pant"], "respiro"),
         ("Voce", ["Speech", "Whispering"], "voce"), ("Tosse", ["Cough", "Sneeze"], "tosse"),
         ("Musica / rumore", ["Music", "White noise", "Pink noise", "Television"], "musica")]
# classi troppo generiche per dire qualcosa (la stanza, il silenzio, "animale" per qualunque verso)
GENERICHE = {"Silence", "Inside, small room", "Inside, large room or hall", "Animal", "Speech synthesizer",
             "Human voice", "Narration, monologue", "Conversation", "Male speech, man speaking",
             "Female speech, woman speaking", "Child speech, kid speaking", "Snort", "Respiratory sounds", "Wheeze"}
IT = {"Rustle": "Fruscio", "Door": "Porta", "Walk, footsteps": "Passi", "Mechanical fan": "Ventola",
      "Air conditioning": "Condizionatore", "Typing": "Tastiera", "Computer keyboard": "Tastiera", "Clock": "Orologio",
      "Tick": "Tic", "Rain": "Pioggia", "Wind": "Vento", "Vehicle": "Traffico", "Car": "Auto", "Dog": "Cane",
      "Cat": "Gatto", "Laughter": "Risata", "Sigh": "Sospiro", "Yawn": "Sbadiglio", "Sniff": "Naso",
      "Throat clearing": "Raschio", "Hiccup": "Singhiozzo", "Hum": "Ronzio", "Static": "Fruscio elettrico",
      "Beep, bleep": "Bip", "Ringtone": "Suoneria", "Alarm clock": "Sveglia", "Water": "Acqua", "Knock": "Colpo", "Drawer open or close": "Cassetto", "Toilet flush": "Sciacquone", "Mains hum": "Ronzio", "Buzz": "Ronzio", "Fan": "Ventola", "Refrigerator": "Frigo", "Speech noise": "Brusio", "Bird": "Uccelli", "Engine": "Motore"}


def labels():
    return open(os.path.join(conferma.HOME, "efficientat", "labels.txt"), encoding="utf-8").read().split("\n")


def blocchi(da, a):
    out = []
    for p in sorted(glob.glob(os.path.join(conferma.D, "interi", "*.m4a"))):
        t0 = datetime.strptime(os.path.basename(p)[:15], "%Y%m%d_%H%M%S")
        if t0 + timedelta(minutes=31) >= da and t0 <= a:
            out.append((t0, p))
    return out


def classi(t0, p):
    n = os.path.basename(p)[:-4]
    f = os.path.join(conferma.D, "dataset", n + ".npz")
    if not os.path.exists(f):
        csv = os.path.join(conferma.D, "dataset", n + ".csv")
        if os.path.exists(csv):
            os.replace(csv, csv + ".vecchio")  # non si cancella niente: il csv vecchio resta accanto
        conferma.dataset(max_blocchi=0, solo=[p])
    return np.load(f)["p"].astype(np.float32) if os.path.exists(f) else None


def grezzo(da, a):
    """(tempi, matrice N x 527) ogni 5 s nell'intervallo."""
    tt, P = [], []
    for t0, p in blocchi(da, a):
        X = classi(t0, p)
        if X is None:
            continue
        for i, v in enumerate(X):
            t = t0 + timedelta(seconds=5 * i)
            if da <= t <= a:
                tt.append(t); P.append(v)
    return tt, (np.array(P) if P else np.zeros((0, 527)))


STANZA = {"Rustle", "Door", "Walk, footsteps", "Mechanical fan", "Air conditioning", "Hum", "Mains hum", "Buzz", "Rain",
          "Wind", "Vehicle", "Car", "Traffic noise, roadway noise", "Dog", "Cat", "Sigh", "Yawn", "Sniff", "Throat clearing",
          "Hiccup", "Laughter", "Knock", "Water", "Toilet flush", "Typing", "Computer keyboard", "Clock", "Tick",
          "Alarm clock", "Ringtone", "Beep, bleep", "Refrigerator", "Fan"}


def altri(P, tt, lab, usate, soglia=0.3, distanza=timedelta(minutes=5)):
    """
    suono ogni `distanza`. Finiscono tutti in UNA riga 'Altri suoni'."""
    ev = []
    for i, n in enumerate(lab):
        if n not in STANZA or i in usate:
            continue
        for k in np.flatnonzero(P[:, i] >= soglia):
            if not any(e[1] == IT.get(n, n) and abs(e[0] - tt[k]) < distanza for e in ev):
                ev.append((tt[k], IT.get(n, n)))
    return sorted(ev)


def righe(P, lab, extra=4, soglia=0.15):
    """Le 5 fisse + le `extra` altre classi piu' forti della notte (sopra soglia, non generiche): [(nome, indici, tipo)]."""
    out = [(n, [lab.index(c) for c in cc if c in lab], t) for n, cc, t in FISSE]
    usate = {i for _, ii, _ in out for i in ii}
    if len(P):
        out = [r for r in out if (P[:, r[1]].max(1) >= soglia).sum() >= 3]
    if len(P):
        # da 5 s sopra soglia), non il singolo picco
        volte = (P >= soglia).sum(0)
        # riga propria solo per i suoni CONTINUI della stanza (>= 5% dei pezzi, es. ronzio); i rari vanno in altri()
        forti = [i for i in np.argsort(-volte, kind="stable")
                 if i not in usate and lab[i] in STANZA and volte[i] >= max(20, 0.05 * len(P))][:extra]
        gruppi = {}  # stesso nome italiano = una riga sola (Hum + Mains hum = "Ronzio")
        for i in forti:
            gruppi.setdefault(IT.get(lab[i], lab[i]), []).append(i)
        out += [(n, ii, "ora") for n, ii in gruppi.items()]
    return out


def divisione_file(path, passo=2.5, soglia=0.15):
    """Categorie di UNA clip (~20 s) col modello preciso, nel formato di grafici.divisione ('0.0-5.0 s russa+ronzio · ...').
    scheda deve avere una corsia per ognuno. Qui niente regola 'almeno 3 volte' (in 20 s non ha senso): basta una
    finestra sicura. Solo fisse + suoni plausibili della stanza (STANZA)."""
    import subprocess
    import onnxruntime as ort
    SR = conferma.SR
    w = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, dtype="<f4")
    dur = len(w) / SR
    w = np.pad(w, (0, max(0, 5 * SR - len(w))))
    lab = labels()
    chiavi = {i: IT.get(n, n).lower() for i, n in enumerate(lab) if n in STANZA}
    chiavi.update({lab.index(c): t for _, cc, t in FISSE for c in cc if c in lab})
    sess = ort.InferenceSession(os.path.join(conferma.HOME, "efficientat", "mn10_as.onnx"), providers=["CPUExecutionProvider"])
    out = []
    for i in range(0, len(w) - 5 * SR + 1, int(passo * SR)):
        p = sess.run(None, {"waveform": w[i:i + 5 * SR].reshape(1, -1)})[0][0]
        e = sorted({k for j, k in chiavi.items() if p[j] >= soglia})
        if e:
            out.append(f"{i / SR:.1f}-{min(i / SR + 5, dur):.1f} s {'+'.join(e)}")
    return " · ".join(out)


def momenti_da(tt, M, R, per_riga=2, soglia=0.12, distanza=timedelta(minutes=10)):
    """I momenti piu' forti per riga: [(etichetta, tipo_punto, t)], lontani almeno `distanza`, sopra `soglia`."""
    out = []
    for r, (nome, _, tipo) in enumerate(R):
        presi = []
        for k in np.argsort(-M[r]):
            if M[r][k] < soglia or len(presi) >= per_riga:
                break
            if all(abs(tt[k] - q) >= distanza for q in presi):
                presi.append(tt[k])
        out += [(nome.split(" ")[0], tipo, t) for t in sorted(presi)]
    return out


RAMI_IT = {"Human sounds": "Suoni umani", "Animal": "Animali", "Music": "Musica", "Natural sounds": "Suoni naturali",
           "Sounds of things": "Oggetti e casa", "Source-ambiguous sounds": "Suoni generici",
           "Channel, environment and background": "Ambiente e fondo", "Respiratory sounds": "Suoni del respiro",
           "Human voice": "Voce", "Domestic sounds, home sounds": "Casa", "Vehicle": "Veicoli", "Speech": "Parlato",
           "Breathing": "Respiro", "Snoring": "Russare", "Cough": "Tosse", "Sneeze": "Starnuto",
           "Noise": "Rumore", "Background noise": "Rumore di fondo", "Sound reproduction": "Audio riprodotto",
           "Television": "Televisione", "Musical instrument": "Strumenti", "Music genre": "Generi musicali",
           "Speech synthesizer": "Voce sintetica", "Mechanisms": "Meccanismi", "Liquid": "Liquidi",
           "Alarm": "Allarmi", "Tools": "Attrezzi", "Wood": "Legno", "Glass": "Vetro", "Specific impact sounds": "Colpi"}
QUESTO = "(questo suono)"


def _ontologia():
    """AudioSet ontology.json (github.com/audioset/ontology, accanto a questo file): id, nomi, primo genitore."""
    import json
    o = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audioset_ontology.json"), encoding="utf-8"))
    padre = {}
    for x in o:
        for c in x["child_ids"]:
            padre.setdefault(c, x["id"])
    return {x["id"]: x["name"] for x in o}, padre, {x["name"]: x["id"] for x in o}


def albero(tt, P, lab, soglia=0.15, orari=6, distanza=timedelta(minutes=5), ont=None):
    """
    GENERICHE) nei rami dell'ontologia AudioSet: {ramo: {sottoramo: {classe: [orari]}}}. Un suono che e' anche ramo
    (Respiro contiene Russare) tiene i suoi orari in QUESTO."""
    nome_id, padre, per_nome = ont or _ontologia()
    out = {}
    for i, n in enumerate(lab):
        if n in GENERICHE or n not in per_nome or not len(P):
            continue
        ks = np.flatnonzero(P[:, i] >= soglia)
        if not len(ks):
            continue
        tempi = []
        for k in ks[np.argsort(-P[ks, i], kind="stable")]:
            if all(abs(tt[k] - q) >= distanza for q in tempi):
                tempi.append(tt[k])
            if len(tempi) >= orari:
                break
        via, c = [], per_nome[n]
        while c in padre:
            c = padre[c]
            via.append(nome_id[c])
        nodo = out
        for r in reversed(via):
            r = RAMI_IT.get(r, IT.get(r, r))
            if isinstance(nodo.get(r), list):  # era una foglia: diventa ramo che tiene i suoi orari
                nodo[r] = {QUESTO: nodo[r]}
            nodo = nodo.setdefault(r, {})
        k = RAMI_IT.get(n, IT.get(n, n))
        if isinstance(nodo.get(k), dict):
            nodo[k][QUESTO] = sorted(tempi)
        else:
            nodo[k] = sorted(tempi)
    return out


def conta(a):
    return sum(1 if isinstance(v, list) else conta(v) for v in a.values())


def albero_md(a):
    """<details> annidati e chiusi per il rich message (Bot API 10.1+): ramo (quanti suoni) -> suono: orari."""
    righe = []
    for k, v in sorted(a.items(), key=lambda z: (isinstance(z[1], dict), z[0] != QUESTO, z[0])):
        while isinstance(v, dict) and len(v) == 1 and isinstance(next(iter(v.values())), dict):
            k, v = next(iter(v.items()))  # un solo ramo dentro: niente tendina in piu', resta il nome piu' preciso
        if isinstance(v, list):
            righe.append(f"- **{k}**: " + ", ".join(f"{t:%H:%M}" for t in v))
        else:
            righe.append(f"<details><summary>{k} ({conta(v)})</summary>\n\n{albero_md(v)}\n</details>")
    return "\n".join(righe)


def pause_vere(tt, M, R, pz, attorno=30, soglia=0.15):
    """
    musica) il ritmo sembrava regolare e uscivano pause finte."""
    righe = [r for r, (_, _, t) in enumerate(R) if t in ("russa", "respiro")]
    if not righe or not tt:
        return []
    ok = M[righe].max(0) >= soglia
    return [(t, d) for t, d in pz
            if any(ok[k] for k in range(len(tt)) if abs((tt[k] - t).total_seconds()) <= attorno)]


def calcola(da, a):
    tt, P = grezzo(da, a)
    lab = labels()
    R = righe(P, lab)
    M = np.array([P[:, ii].max(1) if len(P) else [] for _, ii, _ in R])
    A = altri(P, tt, lab, {i for _, ii, _ in R for i in ii}) if len(P) else []
    if len(tt):
        rade = [r for r, (_, _, t) in enumerate(R) if t not in ("russa", "respiro")
                and (M[r] >= 0.15).sum() < max(3, 0.01 * len(tt))]
        for r in rade:
            for k in np.flatnonzero(M[r] >= 0.15):
                if not any(e[1] == R[r][0] and abs(e[0] - tt[k]) < timedelta(minutes=5) for e in A):
                    A.append((tt[k], R[r][0]))
        tieni = [r for r in range(len(R)) if r not in rade]
        R, M, A = [R[r] for r in tieni], M[tieni], sorted(A)
        try:
            import respiro
            A = sorted(A + [(t, "Pausa") for t, _ in pause_vere(tt, M, R, respiro.pause_tra(da, a))])
        except Exception as e:
            print(f"respiro: {e}", file=sys.stderr)
    return tt, M, R, A


def momenti(da, a, **kw):
    tt, M, R, A = calcola(da, a)
    return momenti_da(tt, M, R, **kw) + [(n, "ora", t) for t, n in A[:4]]


def tratti(da, a, soglia=0.12, minimo=timedelta(minutes=3), buco=timedelta(minutes=2)):
    """
    [(nome, inizio, fine)] dove la categoria resta sopra soglia (buchi < `buco` uniti), lunghi almeno `minimo`."""
    tt, M, R, _ = calcola(da, a)
    out = []
    for r, (nome, _, _) in enumerate(R):
        t_on = [tt[k] for k in np.flatnonzero(M[r] >= soglia)]
        seg = []
        for t in t_on:
            if seg and t - seg[-1][1] <= buco:
                seg[-1][1] = t
            else:
                seg.append([t, t])
        out += [(nome.split(" ")[0], x, y + timedelta(seconds=5)) for x, y in seg if y - x >= minimo]
    return sorted(out, key=lambda z: z[2] - z[1], reverse=True)


def scrematura(da, a, r, forte=0.3, minimo=30):
    """
    -> (indici delle finestre da 5 s dove c'e' la riga r, [(inizio, fine)] dei pezzi di fila). Prima solo le finestre
    FORTI; se fanno meno di `minimo` secondi anche le deboli (0.15)."""
    tt, M, R, _ = calcola(da, a)
    tieni = []
    for s in (forte, 0.15):
        tieni = [int(k) for k in np.flatnonzero(M[r] >= s)]
        if len(tieni) * 5 >= minimo:
            break
    return scrematura_da(tt, tieni)


def scrematura_da(tt, tieni):
    """(tieni, [(inizio, fine)]): le finestre da 5 s scelte, unite in pezzi di fila (audio = immagine, al secondo)."""
    pezzi = []
    for k in tieni:
        if pezzi and tt[k] == pezzi[-1][1]:  # finestra attaccata alla precedente: stesso pezzo
            pezzi[-1][1] = tt[k] + timedelta(seconds=5)
        else:
            pezzi.append([tt[k], tt[k] + timedelta(seconds=5)])
    return tieni, [tuple(p) for p in pezzi]


def _tagli(tt):
    return [i for i in range(len(tt)) if i == 0 or (tt[i] - tt[i - 1]).total_seconds() > 5]


def tacche(tt, massimo=8, scremato=False):
    """
    (salti nel tempo): una tacca a ogni taglio, al massimo `massimo`."""
    if not tt:
        return [], []
    salti = _tagli(tt)
    if scremato:
        pos = salti[::-(-len(salti) // massimo)]
    else:
        durata = (tt[-1] - tt[0]).total_seconds() / 60
        passo = next((p for p in (5, 10, 15, 30, 60, 120) if durata / p <= massimo), 180)
        pos = [i for i, t in enumerate(tt) if (t.hour * 60 + t.minute) % passo == 0 and t.second < 5]
    return pos, [f"{tt[i]:%H:%M}" for i in pos]


def tacche_zoom(tt, zoom, spazio=110, scremato=False):
    """Tacche per l'immagine LARGA (zoom px ogni 5 s): ogni minuto, o a ogni taglio se scremato, mai piu' vicine di
    `spazio` px (le scritte non si toccano)."""
    pos = []
    for i in (_tagli(tt) if scremato else [i for i, t in enumerate(tt) if t.second < 5]):
        if not pos or (i - pos[-1]) * zoom >= spazio:
            pos.append(i)
    return pos, [f"{tt[i]:%H:%M}" for i in pos]


SX, DX, SU, GIU, RIGA = 190, 20, 20, 50, 72  # zoom: margini e altezza di riga in px (la colonna dei nomi resta ferma)


def disegna(da, a, out, con_geo=False, tieni=None, zoom=None):
    """tieni = indici delle finestre da tenere (scrematura): il video salta i pezzi senza quella categoria.
    (sta nella didascalia), nomi delle righe nei primi SX px."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    tt, M, R, A = calcola(da, a)
    if tieni is not None:
        A = [(t, n) for t, n in A if any(abs((t - tt[k]).total_seconds()) < 5 for k in tieni)]
        tt, M = [tt[k] for k in tieni], M[:, tieni]
    nr = len(R) + (1 if A else 0)
    if A:  # riga "Altri suoni": vuota, con un segno e il nome dove compare ciascuno
        M = np.vstack([M, np.zeros((1, len(tt)))]) if len(M) else np.zeros((1, len(tt)))
    if zoom:
        W, H = SX + len(tt) * zoom + DX, SU + RIGA * nr + GIU
        fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
        ax = fig.add_axes([SX / W, GIU / H, len(tt) * zoom / W, RIGA * nr / H])
    else:
        fig, ax = plt.subplots(figsize=(10.8, 1.2 + 0.72 * nr), dpi=100)
    ax.imshow(M, aspect="auto", cmap="Blues", vmin=0, vmax=0.3, interpolation="nearest",
              extent=[0, len(tt), nr - 0.5, -0.5])
    ax.set_yticks(range(nr)); ax.set_yticklabels([n for n, _, _ in R] + (["Altri suoni"] if A else []), fontsize=15)
    COL = ["#c0392b", "#1f3a5f", "#27ae60", "#8e44ad", "#d35400", "#7f8c8d"]  # un colore per suono, nome scritto 1 volta
    nomi = list(dict.fromkeys(n for _, n in A))
    for t, n in A:
        x = min(range(len(tt)), key=lambda k: abs((tt[k] - t).total_seconds()))
        c = COL[nomi.index(n) % len(COL)]
        ax.plot([x, x], [nr - 1.35, nr - 0.65], color=c, lw=4, solid_capstyle="butt")
        if zoom or t == next(q for q, m in A if m == n):  # zoom: si vede un pezzo alla volta -> nome ogni volta
            ax.text(x, nr - 1.4 - 0.3 * (nomi.index(n) % 2), n, ha="center", va="bottom", fontsize=12,
                    color=c, weight="bold")
    nf = sum(1 for _, _, t in R if t != "ora")  # fisse rimaste
    if 0 < nf < len(R):  # separa le fisse dalle "altre di stanotte"
        ax.axhline(nf - 0.5, color="#888888", lw=1.5)
    scr = tieni is not None
    pos, eti = tacche_zoom(tt, zoom, scremato=scr) if zoom else tacche(tt, scremato=scr)
    # zoom: scritta a DESTRA della tacca, cosi' non sborda nella colonna ferma dei nomi
    ax.set_xticks(pos); ax.set_xticklabels(eti, fontsize=14, ha="left" if zoom else "center")
    if tieni is not None:  # i tagli si vedono: riga bianca dove il tempo salta
        tagli = [i for i in range(1, len(tt)) if (tt[i] - tt[i - 1]).total_seconds() > 5] if zoom else pos[1:]
        for i in tagli:
            ax.axvline(i, color="white", lw=3)
    if not zoom:
        ax.set_title(f"{da:%d/%m} dalle {da:%H:%M} alle {a:%H:%M} · " +
                     (f"solo i pezzi scelti: {len(tt) * 5 // 60} min" if tieni is not None else "ogni 5 secondi") +
                     " · scuro = il modello e' sicuro", fontsize=13)
    for s in ax.spines.values(): s.set_visible(False)
    if not zoom:
        fig.tight_layout()
    fig.canvas.draw()
    bb = ax.get_window_extent(); H = fig.bbox.height  # asse del tempo in pixel (per la linea del video)
    geo = dict(x0=bb.x0, x1=bb.x1, ya=H - bb.y1, yb=H - bb.y0,
               dur=5 * len(tt) if tieni is not None else (a - da).total_seconds())
    fig.savefig(out, facecolor="white"); plt.close(fig)
    return (out, geo) if con_geo else (out, len(tt))


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        lab = ["Snoring", "Breathing", "Speech", "Cough", "Music", "Rustle", "Silence", "Door"]
        P = np.zeros((10, 8)); P[2:6, 5] = 0.4; P[4, 6] = 0.9; P[1:9, 7] = 0.2; P[3, 0] = 0.2
        P = np.zeros((40, 8)); P[:, 5] = 0.4; P[4, 6] = 0.9; P[7, 7] = 0.5; P[3, 0] = 0.2
        R = righe(P, lab, extra=4)
        assert [n for n, _, _ in R] == ["Fruscio"], R  # continuo -> riga; Silence generica; fisse assenti tolte
        tt = [datetime(2026, 9, 29, 22) + timedelta(seconds=5 * k) for k in range(40)]
        assert altri(P, tt, lab, {5}) == [(tt[7], "Porta")], altri(P, tt, lab, {5})  # raro -> "Altri suoni"  # Silence generica esclusa; ordine = quante volte
        q = [datetime(2026, 9, 29, 22, 52) + timedelta(seconds=5 * k) for k in range(480)]  # 40 minuti
        assert tacche(q)[1] == ["22:55", "23:00", "23:05", "23:10", "23:15", "23:20", "23:25", "23:30"], tacche(q)
        assert tacche(q[:3] + q[100:102], scremato=True)[1] == ["22:52", "23:00"]  # scremato: 1 per taglio
        ont = ({"r": "Human sounds", "b": "Breathing", "s": "Snoring", "x": "Silence"}, {"b": "r", "s": "b"},
               {"Human sounds": "r", "Breathing": "b", "Snoring": "s", "Silence": "x"})
        P3 = np.zeros((4, 3)); P3[1, 1] = 0.5; P3[2, 0] = 0.3; P3[3, 2] = 0.9  # russare, respiro, silenzio (generico)
        a = albero(q[:4], P3, ["Breathing", "Snoring", "Silence"], ont=ont)
        assert a == {"Suoni umani": {"Respiro": {QUESTO: [q[2]], "Russare": [q[1]]}}}, a
        assert "<summary>Respiro (2)</summary>" in albero_md(a) and "**Russare**: 22:52" in albero_md(a), albero_md(a)
        b = q[:60] + [t + timedelta(seconds=3) for t in q[60:]]  # buco di 8 s tra due blocchi: NON e' un taglio
        assert len(tacche_zoom(b, 10)[1]) == 40 and tacche_zoom(b, 10)[1][5] == "22:57", tacche_zoom(b, 10)  # 1/minuto
        print("ok")
    else:
        print(disegna(datetime.fromisoformat(sys.argv[1]), datetime.fromisoformat(sys.argv[2]), sys.argv[3]))
