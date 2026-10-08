"""
- Daan, Beersma, Borbely 1984, Am J Physiol (PMID 6696142): S sale da sveglio e scende dormendo, soglie modulate
  dall'orologio. Costanti 18,2 h (salita) / 4,2 h (discesa) = valori citati di solito, NON letti nel testo.
- Dijk & Czeisler 1994, Neurosci Lett (PMID 8190360): orologio e pressione contano circa uguale; sono sfasati apposta:
  l'allerta massima dell'orologio cade la sera, quando la pressione e' piu' alta (forced desynchrony, 8 uomini).
- Monterastelli, Adams, Eastman, Crowley 2024 (PMC11801367): zona proibita = 2-3 h prima dell'ora abituale di letto.
- Cohen et al. 2010, Sci Transl Med (PMID 20371466): col debito cronico le prime ore dopo una dormita lunga sembrano
  normali, ma restando svegli la prestazione crolla piu' in fretta, soprattutto nella "notte" dell'orologio.
NON usare (nessuna fonte trovata): "KSS alta + PVT veloce = zona pura".
"""
import math
from statistics import median

TW, TS = 18.2, 4.2      # costanti del processo S (h), vedi sopra
BISOGNO_H = 8.0         # ponytail: bisogno di sonno fisso; da tarare sulle sue notti (durate quando si sveglia da solo)
DEBITO_FORTE_H = 3.0    # debito sulle ultime 3 notti oltre cui si avvisa (scelta nostra, non da letteratura)
DEBITO_GRAVE_H = 6.0    # oltre: l'avviso del debito passa davanti alla riga sulla carica (scelta nostra)


def ore_rel(t):
    """(nota rimossa)"""
    return t.hour + t.minute / 60 - (24 if t.hour >= 12 else 0)


def hhmm(h):
    h %= 24
    return f"{int(h):02d}:{int(round(h % 1 * 60)) % 60:02d}"


def letto_abituale(inizi):
    """Mediana degli inizi del sonno (datetime) in ore relative; None con meno di 3 notti."""
    return median(ore_rel(t) for t in inizi) if len(inizi) >= 3 else None


def debito(durate, n=3):
    """Ore di sonno mancanti sulle ultime n notti (durate in ore, la piu' recente per prima)."""
    return round(sum(max(0.0, BISOGNO_H - d) for d in durate[:n]), 1)


def pressione(ore_sveglio, s0=0.25):
    """Processo S (0-1) dopo ore_sveglio ore di veglia, partendo da s0 al risveglio."""
    return 1 - (1 - s0) * math.exp(-max(0.0, ore_sveglio) / TW)


FASI = ("giorno", "prima", "zona", "verso", "finestra", "oltre")


def fase(ora, letto):
    """
    'zona' = 2-3 h prima del letto abituale, ESATTAMENTE la fonte (Monterastelli 2024) | 'verso' (letto-2..letto-1,
    la carica cala) | 'finestra' (letto +-1 h) | 'oltre'."""
    x = ore_rel(ora)
    for limite, nome in ((letto - 6, "giorno"), (letto - 3, "prima"), (letto - 2, "zona"), (letto - 1, "verso")):
        if x < limite:
            return nome
    return "finestra" if x <= letto + 1 else "oltre"


FONTI = {
    "pochi": "dati: servono >= 3 notti di sonno lungo",
    "giorno": "tue notti (mediana): troppo presto per la seconda carica",
    "prima": "Monterastelli 2024 (zona 2-3 h prima del letto) + tue notti (mediana)",
    "verso": "Monterastelli 2024 (la zona finisce ~2 h prima del letto) + tue notti",
    "zona": "Monterastelli 2024 (PMC11801367) + Dijk & Czeisler 1994 (allerta massima la sera)",
    "finestra": "tue notti: mediana degli inizi del sonno",
    "oltre": "Daan, Beersma, Borbely 1984 (soglie dell'orologio) + tue notti",
    "carica": "tuoi tasti MENTE/SONNO (ultime 3 h) + note caffe'/te' (ultime 4 h)",
    "debito": "Cohen 2010 (PMID 20371466) + tue ultime 3 notti",
}


def riga_carica(f, stimolante=False):
    """
    4 h danno lo stesso effetto (la caffeina abbassa la sensazione di sonno)."""
    r = {"giorno": "Mente alta + sonno alto di giorno: piu' probabile debito di sonno o caffe' che la carica serale.",
         "prima": "Mente alta + sonno alto gia' adesso: forse la carica arriva prima del solito.",
         "zona": "Mente alta + sonno alto: potrebbe essere la seconda carica.",
         "verso": "Mente alta + sonno alto: la carica sta calando.",
         "finestra": "Mente alta + sonno alto: la carica sta finendo.",
         "oltre": "Mente ancora alta oltre il tuo solito: il tuo orologio forse si sta spostando piu' tardi."}[f]
    return r[:-1] + " (o il caffe'/te' delle ultime ore)." if stimolante and f != "oltre" else r


def commento_fonti(ora, inizi, durate, mente=None, sonno=None, stimolante=False):
    """[(riga, chiave fonte)] (max 3): unica fonte di verita'; commento() le unisce. stimolante = caffe'/te' ultime 4 h."""
    letto = letto_abituale(inizi)
    if letto is None:
        return [("Pochi dati sulle tue notti (servono almeno 3): per ora segno e basta.", "pochi")]
    f, dbt, z = fase(ora, letto), debito(durate), f"{hhmm(letto - 3)}-{hhmm(letto - 2)}"
    alta = bool(mente and mente >= 3)
    prima_riga = {
        "giorno": f"Giornata ancora attiva: la tua seconda carica arriva di solito verso le {hhmm(letto - 3)}.",
        "prima": f"Prima della tua seconda carica (di solito {z}).",
        "zona": f"Sei nella seconda carica ({z}): normale sentirsi svegli anche con sonno." if alta
        else f"Sei nella fascia della tua seconda carica ({z}).",
        "verso": f"La seconda carica sta calando: tra poco la tua finestra del sonno (di solito {hhmm(letto)}).",
        "finestra": f"Sei nella tua finestra del sonno (di solito {hhmm(letto)}), ma con la mente a mille potresti fare fatica."
        if mente == 4 else f"Sei nella tua finestra del sonno (di solito {hhmm(letto)}): stendersi ora e' il momento piu' facile.",
        "oltre": f"Oltre il tuo solito ({hhmm(letto)}): l'orologio ora spinge al sonno, restare svegli costa di piu'."}[f]
    out = [(prima_riga, f)]
    car = [(riga_carica(f, stimolante), "carica")] if alta and sonno and sonno >= 3 else []
    deb = [(f"Debito {str(dbt).replace('.', ',')} h nelle ultime 3 notti: la carica lo nasconde, il conto arriva dopo.",
            "debito")] if dbt >= DEBITO_FORTE_H else []
    out += deb + car if dbt >= DEBITO_GRAVE_H else car + deb
    return out[:3]


def commento(ora, inizi, durate, mente=None, sonno=None, stimolante=False):
    """Messaggio corto (max 3 righe) su dove sei nei due ritmi: inizi = datetime degli inizi del sonno recenti,
    durate = ore delle notti recenti (piu' recente prima), mente/sonno = ultimo tasto 1-4 (o None)."""
    return "\n".join(r for r, _ in commento_fonti(ora, inizi, durate, mente, sonno, stimolante))
