"""Analisi di una notte dai riassunti per minuto (minuti_AAAAMMGG.csv fatti da sonno_tel.py).
Unica versione: la usano il bot sul telefono (bot.py) e il PC (C:\\sonno_tex\\sonno_audio.py).
Solo stdlib + numpy.
"""
import csv, glob, os
from datetime import datetime, timedelta
import numpy as np


MEDIA = next((p for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_a56.csv"),
                          r"C:\sonno_audio\media_a56.csv") if os.path.exists(p)), "media_a56.csv")


def cambio_ora(a, b):
    """Ore da aggiungere a una durata calcolata con orari da orologio (naive, ora italiana) tra a e b: +1 se attraversa
    """
    def ultima_domenica(anno, mese, ora):
        d = datetime(anno, mese, 31, ora)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    h = 0
    for anno in {a.year, b.year}:
        if a < ultima_domenica(anno, 10, 3) <= b:
            h += 1
        if a < ultima_domenica(anno, 3, 2) <= b:
            h -= 1
    return h


def suona(start, end, path=MEDIA):
    """Minuti in cui un telefono (A56/A21s) suonava dall'altoparlante (media_a56.csv: t,dispositivo,si|no,app).
    """
    out = set()
    try:
        for r in csv.reader(open(path, encoding="utf-8")):
            if len(r) > 2 and r[2] == "si":
                k = datetime.fromisoformat(r[0]).replace(second=0, microsecond=0)
                for j in (-1, 0, 1):  # un campione ogni 2': copre anche i minuti vicini
                    if start <= k + timedelta(minutes=j) < end:
                        out.add(k + timedelta(minutes=j))
    except (OSError, ValueError):
        pass
    return out


def minuti(cartella, start, end, pc=frozenset(), media=None):
    """Tabella per minuto. I rumori ESTERNI sono gia' tolti da picchi e voce (sul telefono).
    pc = minuti in cui il PC era usato (solo sul PC): se usi il PC non dormi."""
    M = {}
    for fn in sorted(glob.glob(os.path.join(cartella, "minuti_*.csv"))):
        for r in csv.DictReader(open(fn)):
            k = datetime.fromisoformat(r["t"])
            if r.get("esterno_top") == "scartato_sveglio":
                continue
            if start <= k < end:
                M[k] = dict(picchi=int(r["picchi_miei"]), voce=int(r["voce"]), colpi=int(r["colpi_russa"]),
                            esterni=int(r["esterni"]), esterno_top=r["esterno_top"],
                            sbuffi=int(r.get("sbuffi") or 0), respiro=int(r.get("respiro") or 0))
    media = suona(start, end) if media is None else media
    for k, d in M.items():
        d["russa"] = d["colpi"] >= 3  # russamento = a colpi: >=3 nel minuto
        d["pc"] = k in pc
        d["telefono"] = k in media
        # ponytail: soglie a occhio, da tarare col voto del mattino (diario.csv)
        # picchi non contano come agitazione; PC e voce si'.
        d["sveglio"] = d["pc"] or (d["picchi"] >= 4 and not d["russa"]) or (d["voce"] >= 10 and not d["telefono"])
    return M


def blocco_sonno(M):
    """Periodo piu' lungo 'calmo' (<=3 minuti agitati su 15), unendo interruzioni fino a 20'."""
    ks = sorted(M)
    calmo = [sum(M.get(k + timedelta(minutes=j), {"sveglio": False})["sveglio"] for j in range(-7, 8)) <= 3
             and not M[k]["pc"] for k in ks]
    runs, s, prev = [], None, None
    for k, c in zip(ks + [None], calmo + [False]):
        # Oltre 20 minuti senza audio il blocco si spezza.
        if s is not None and k is not None and k - prev > timedelta(minutes=21):
            runs.append([s, prev]); s = None
        if c and s is None: s = k
        if not c and s is not None: runs.append([s, prev]); s = None
        prev = k
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] <= timedelta(minutes=20): merged[-1][1] = b
        else: merged.append([a, b])
    best = max(merged, key=lambda r: r[1] - r[0], default=None)
    return best if best and best[1] - best[0] >= timedelta(hours=1) else None


def veglia(a, z, uso, M, breve=5, tetto=45):
    """Fine vera della notte = primo segno di veglia SOSTENUTA dopo `a` (uso PC/A56 >= 5' o uso breve seguito da
    agitazione), non l'ultimo minuto analizzato. Usi brevi (< 5') con respiro/silenzio che riprende = risveglio breve,
    ponytail: segni = solo uso.csv (PC + schermo A56); Sleep as Android 'awake' non conta (poca fiducia)."""
    ss = []
    for k in sorted(k for k in uso if k > a):
        if ss and k - ss[-1][1] <= timedelta(minutes=2): ss[-1][1] = k
        else: ss.append([k, k])
    brevi = []
    for s, e in ss:
        if s > z + timedelta(minutes=tetto):  # troppo dopo l'ultimo audio calmo: non si allunga la notte
            break
        dopo = [M[e + timedelta(minutes=j)] for j in range(1, 6) if e + timedelta(minutes=j) in M]
        if (e - s).total_seconds() / 60 + 1 >= breve or sum(d["sveglio"] and not d["pc"] for d in dopo) >= 3:
            return s, brevi, True
        brevi.append((s, e))
    return z, brevi, False


def analizza(cartella, day, pc_fn=None, storico=()):
    """Notte che finisce il giorno `day` (AAAAMMGG): finestra 18:00 -> 16:00."""
    end = datetime.strptime(day, "%Y%m%d").replace(hour=16)
    start = end - timedelta(hours=22)  # ponytail: finestra fissa, il ritmo caotico ci sta dentro
    pc = pc_fn(start, end) if pc_fn else frozenset()
    M = minuti(cartella, start, end, pc)
    if not M:
        return None
    b = blocco_sonno(M)
    if b and end - b[1] <= timedelta(minutes=15):
        # se no la notte veniva tagliata alle 16 e il report partiva mentre dormiva ancora
        end = end + timedelta(hours=8)
        pc = pc_fn(start, end) if pc_fn else frozenset()
        M = minuti(cartella, start, end, pc)
        b = blocco_sonno(M)
    if not b:
        return dict(day=day, M=M, blocco=None)
    a, z = b
    dentro = [k for k in sorted(M) if a <= k <= z]
    fine, brevi, confermata = veglia(a, z, pc, M)
    durata = ((fine - a) - sum((e - s + timedelta(minutes=1) for s, e in brevi), timedelta())).total_seconds() / 3600
    durata += cambio_ora(a, fine)
    elaborato = max(k for k in M if k <= max(fine, z)) + timedelta(minutes=1)  # audio analizzato fino a qui
    # risvegli = almeno 3 minuti agitati di fila (o PC usato) dentro il blocco
    risv, run, waso = [], 0, 0
    for k in dentro + [None]:
        sv = k is not None and M[k]["sveglio"]
        if sv: run += 1; waso += 1
        else:
            if run >= 3: risv.append(k - timedelta(minutes=run))
            run = 0
    eff = 1 - waso / max(len(dentro), 1)
    russ = sum(M[k]["russa"] for k in dentro)
    # c'era davvero qualcuno? stanza vuota = "calma" ma senza respiro/russa/movimenti (bug UX: notte finta di 22h
    # quando dorme fuori). ponytail: soglia 3% dei minuti con segni di una persona, da tarare con le notti vere
    segni = sum(1 for k in dentro if M[k]["russa"] or M[k]["respiro"] > 0 or M[k]["picchi"] > 0)
    vuota = segni < 0.03 * len(dentro)
    # regolarita': distanza (circolare) dall'ora mediana di addormentamento delle notti precedenti
    prec = [datetime.fromisoformat(r["inizio"]) for r in storico if r["day"] != day][-14:]
    diff = None
    if prec:
        hh = np.array([p.hour + p.minute / 60 for p in prec]) * 2 * np.pi / 24
        med = (np.angle(np.mean(np.exp(1j * hh))) * 24 / (2 * np.pi)) % 24
        diff = ((a.hour + a.minute / 60 - med + 12) % 24) - 12
    # punteggio indicativo 0-100 (durata 30, efficienza 30, risvegli 20, russamento 10, regolarita' 10)
    p_dur = 30 * min(1, max(0, 1 - max(7 - durata, durata - 9.5, 0) / 3))
    p_eff = 30 * min(1, max(0, (eff - 0.70) / 0.25))
    p_ris = max(0, 20 - 4 * len(risv))
    p_rus = 10 * max(0, 1 - (russ / max(len(dentro), 1)) / 0.2)
    p_reg = 10 * max(0, 1 - abs(diff) / 4) if diff is not None else 5
    return dict(day=day, M=M, blocco=b, inizio=a, fine=fine, durata=durata, brevi=[s for s, _ in brevi], pausa=sum((e - s).total_seconds() / 60 + 1 for s, e in brevi),
                confermata=confermata, elaborato=elaborato, ore_audio=len(dentro) / 60, eff=eff,
                risvegli=risv, waso=waso, russa=russ, sbuffi=sum(M[k]["sbuffi"] for k in dentro), diff=diff, vuota=vuota,
                punteggio=round(p_dur + p_eff + p_ris + p_rus + p_reg),
                voci=dict(durata=p_dur, efficienza=p_eff, risvegli=p_ris, russamento=p_rus, regolarita=p_reg))


def risvegli_uniti(audio, uso, fonte=lambda k: "telefono", stesso=10):
    """
    in ordine, entro `stesso` minuti = stesso risveglio (fonti unite). -> [(ora, 'audio'|'telefono'|'audio+telefono')]"""
    out = []
    for k, f in sorted([(k, "audio") for k in audio] + [(k, fonte(k)) for k in uso]):
        if out and k - out[-1][0] <= timedelta(minutes=stesso):
            if f not in out[-1][1].split("+"):
                out[-1] = (out[-1][0], out[-1][1] + "+" + f)
            continue
        out.append((k, f))
    return out


def previsione_letto(inizi, quota=0.70, peso=0.85):
    """Ora in cui si addormenta stasera dalle notti recenti. inizi = [(giorni_fa, datetime inizio)], peso peso**giorni_fa.
    Orari dopo le 12 = sera prima (22:30 -> -1.5). Range = quantili pesati che tengono ~`quota` del peso, arrotondati a 15'.
    -> (da 'HH:MM', a 'HH:MM', percentuale del peso dentro) o None con meno di 3 notti o range > 4 h.
    ponytail: niente modello del giorno della settimana; prob = peso delle notti passate dentro il range, max 90%."""
    if len(inizi) < 3:
        return None
    xs = sorted((k.hour + k.minute / 60 - (24 if k.hour >= 12 else 0), peso ** g) for g, k in inizi)
    tot = sum(w for _, w in xs)
    def q(p):
        c = 0
        for h, w in xs:
            c += w
            if c >= p * tot - 1e-9:
                return h
    lo, hi = np.floor(q((1 - quota) / 2) * 4) / 4, np.ceil(q((1 + quota) / 2) * 4) / 4
    if hi - lo > 4:
        return None
    p = sum(w for h, w in xs if lo <= h <= hi) / tot
    hhmm = lambda h: f"{int(h % 24):02d}:{int(round(h % 1 * 60)):02d}"
    return hhmm(lo), hhmm(hi), min(90, int(round(p * 20)) * 5)


def testo(r, html=False):
    B = (lambda s: f"<b>{s}</b>") if html else (lambda s: s)
    if not r:
        return "nessun audio per questa notte"
    if not r["blocco"]:
        return "audio presente ma nessun periodo di sonno >=1h riconosciuto"
    g ="lun mar mer gio ven sab dom".split()[r["inizio"].weekday()]
    L = [B(f"Notte {g} {r['inizio']:%d/%m}: {r['punteggio']}/100") + " (indicativo)",
         f"Addormentato {r['inizio']:%H:%M} → sveglio {r['fine']:%H:%M} = {r['durata']:.1f}h"
         + (f" (audio {r['ore_audio']:.1f}h)" if r["ore_audio"] < r["durata"] - 0.3 else ""),
         f"Efficienza {r['eff']*100:.0f}% · agitato {r['waso']}' · risvegli {len(r['risvegli'])}"
         + (" (" + ", ".join(f"{k:%H:%M}" for k in r["risvegli"][:6]) + ")" if r["risvegli"] else ""),
         f"Russamento {r['russa']}' ({r['russa'] / max(r['durata'] * 60, 1) * 100:.0f}% della notte)"]
    if r.get("sbuffi"):
        L.append(f"Sbuffi (respiro ripreso di colpo): {r['sbuffi']} — indizio, non diagnosi")
    est = {}
    for k in r["M"]:
        if r["inizio"] <= k <= r["fine"] and r["M"][k]["esterno_top"]:
            est[r["M"][k]["esterno_top"]] = est.get(r["M"][k]["esterno_top"], 0) + 1
    if est:
        L.append("Rumori esterni (esclusi dai risvegli): "
                 + ", ".join(f"{g.replace('_', '/')} {m}'" for g, m in sorted(est.items(), key=lambda x: -x[1])))
    if r["diff"] is not None:
        L.append(f"Regolarità: {abs(r['diff']):.1f}h {'dopo' if r['diff'] > 0 else 'prima'} del tuo solito")
    peggio = min(r["voci"], key=lambda k: r["voci"][k] / {"durata": 30, "efficienza": 30, "risvegli": 20,
                                                           "russamento": 10, "regolarita": 10}[k])
    L.append(f"Punto debole: {peggio}")
    if r.get("vuota"):  # dorme fuori quasi mai: la notte si tiene, solo un dubbio (mai buttare una notte vera)
        L.append("pochi segni di te nell'audio: eri qui?")
    ore = {}
    for k in r["M"]:
        if r["inizio"] <= k <= r["fine"] and r["M"][k]["russa"]:
            ore[k.hour] = ore.get(k.hour, 0) + 1
    if ore:
        L.append("Russa per ora: " + " ".join(f"{h:02d}h {m}'" for h, m in ore.items()))
    return "\n".join(L)


if __name__ == '__main__':
    a = datetime(2026, 9, 29, 1)
    z = a + timedelta(minutes=120)
    M = {a + timedelta(minutes=i): dict(sveglio=False, pc=False) for i in range(121)}
    assert blocco_sonno({a: M[a], z: M[z]}) is None
    assert blocco_sonno(M) == [a, z]
    for buco in (5, 20, 21):
        bucata = {k: v for k, v in M.items() if not a + timedelta(minutes=50) <= k < a + timedelta(minutes=50 + buco)}
        assert blocco_sonno(bucata) == ([a, z] if buco <= 20 else None)
    print('OK: campioni isolati, 121 minuti continui, buchi di 5, 20 e 21 minuti')
