"""Confronta le parole candidate del copione con i dataset: frequenza nel parlato (OpenSubtitles), uso nelle
recensioni italiane di app del sonno, frasi naturali (Tatoeba). Stampa i risultati usati in copione.md."""
import bz2, collections, json, re, sys
sys.stdout.reconfigure(encoding="utf-8")

RANK = {}
for i, l in enumerate(open("it_50k.txt", encoding="utf-8"), 1):
    w, n = l.split()
    RANK[w] = (i, int(n))
REC = json.load(open("recensioni_it.json", encoding="utf-8"))
SONNO = [r["testo"].lower() for r in REC if r["app"] in ("Sleep Cycle", "SnoreLab", "Sleep as Android", "Pokémon Sleep")]
TUTTE = [r["testo"].lower() for r in REC]
TAT = [l.split("\t", 2)[2].strip() for l in bz2.open("ita_sentences.tsv.bz2", "rt", encoding="utf-8")]


def rango(w):
    return RANK.get(w, (None, 0))[0]


def gruppo(titolo, parole):
    print(f"\n## {titolo}")
    for w in sorted(parole, key=lambda w: rango(w) or 10**6):
        rec = sum(len(re.findall(rf"\b{re.escape(w)}\b", t)) for t in TUTTE)
        print(f"  {w:14s} rango {str(rango(w) or '>50k'):>6s}  recensioni {rec}")


# 1. sinonimi a confronto (vince il più frequente nel parlato, se il senso è giusto)
gruppo("cancellare", ["cancellato", "buttato", "eliminato", "scartato", "tolto", "rimosso", "via"])
gruppo("salvare / annotare", ["segnato", "annotato", "salvato", "preso", "registrato", "fatto"])
gruppo("ripartire", ["riparto", "riprendo", "ricomincio", "riprendi", "riavvio", "ripartita", "ripartito"])
gruppo("fermare", ["fermato", "fermo", "stop", "pausa", "basta", "chiuso", "finito"])
gruppo("guasto", ["inceppato", "bloccato", "rotto", "errore", "problema", "guasto"])
gruppo("imparare", ["imparo", "imparare", "tarare", "allenare", "capire", "indovino"])
gruppo("suono / clip", ["suono", "suoni", "rumore", "rumori", "clip", "audio", "registrazione", "pezzo", "verso"])
gruppo("sonno", ["notte", "nottata", "sonno", "dormito", "dormire", "sveglio", "risvegli", "russato", "russare",
                 "russo", "russa", "sbuffi", "sbuffo", "crollato", "crolli", "addormentato"])
gruppo("risposte brevi", ["vai", "preso", "ripeti", "cosa", "eh", "ok", "grazie", "chiuso", "fatto", "pronto",
                          "ascolto", "buonanotte", "attenzione"])
gruppo("tempo", ["finché", "fino", "domani", "stasera", "stanotte", "ieri", "adesso", "ora", "subito"])

# 2. come descrivono la notte gli utenti veri (bigrammi con parole del sonno, recensioni app sonno)
print("\n## bigrammi nelle recensioni (app del sonno)")
c = collections.Counter()
for t in SONNO:
    w = re.findall(r"[a-zàèéìòù']+", t)
    c.update(" ".join(p) for p in zip(w, w[1:]) if any(re.match(r"(dorm|russ|sonn|nott|svegl|rumor|sogn)", x) for x in p))
for b, n in c.most_common(45):
    print(f"  {n:4d}  {b}")
print("\n## parole che si lamentano (recensioni 1-2 stelle, tutte le app)")
neg = collections.Counter(w for r in REC if r["stelle"] <= 2 for w in re.findall(r"[a-zàèéìòù]{5,}", r["testo"].lower()))
pos = collections.Counter(w for r in REC if r["stelle"] >= 4 for w in re.findall(r"[a-zàèéìòù]{5,}", r["testo"].lower()))
print("  neg:", ", ".join(w for w, _ in neg.most_common(60) if pos[w] < neg[w])[:600])

# 3. frasi naturali (Tatoeba): quante frasi contengono ciascuna formula
print("\n## formule in Tatoeba (frasi che le contengono)")
for f in ["Ti ascolto", "Preso nota", "Com'è andata", "A domani", "Buonanotte", "Tutto a posto", "È andata così",
          "Una non fa", "Ci riprovo", "Ripeti", "Non ho capito", "Riparto", "Fatto!", "Chiuso", "Ho dormito bene",
          "Ho dormito male", "Non ho dormito", "Ho russato", "Russi", "notte in bianco", "dormito come un sasso",
          "come un ghiro", "a pezzi", "Sono a pezzi", "stanco morto", "Buttalo", "Lascia stare", "Quanto hai dormito"]:
    n = [s for s in TAT if f.lower() in s.lower()]
    print(f"  {len(n):4d}  {f:24s} {n[0][:70] if n else ''}")
