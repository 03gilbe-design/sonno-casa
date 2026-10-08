"""REGOLA DI VERITA' UNICA delle etichette (giudizi.csv = fonte, solo lettura; mai il prefisso del nome file da solo):
  sequenza non vuota -> categorie() di ogni elemento (separatori > + [ ]); altrimenti era non vuota -> categorie(era);
  altrimenti giusto=="1" -> categorie(detto) (ha confermato il modello); altrimenti ESCLUSA (noseq=True, cats=[]).
Uso: rigenera_cats.py giudizi.csv clip.json [clip.json ..]   (aggiorna cats/noseq/seq/era/giusto/detto; scrive la lista delle differenze su stdout)"""
import csv, json, re, sys
from mappa_etichette import categorie


def verita(r):
    """r: dict con sequenza|seq, era, giusto, detto -> (cats, noseq)"""
    toks = [t for t in re.split(r"[>+\[\]]", r.get("sequenza", r.get("seq")) or "") if t.strip()]
    if not toks:
        toks = [r["era"]] if (r.get("era") or "").strip() else [r["detto"]] if r.get("giusto") == "1" else []
    return sorted({k for t in toks for k in categorie(t) if k}), not toks


if __name__ == "__main__":
    G = {r["clip"]: r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))}
    assert verita({"seq": "", "era": "", "giusto": "0", "detto": "russa"}) == ([], True)
    assert verita({"seq": "[respiro+musica]", "era": "respiro", "giusto": "0", "detto": "russa"}) == (["musica", "respiro"], False)
    for p in sys.argv[2:]:
        cl = json.load(open(p))
        for c in cl:
            r = G.get(c["clip"])
            if r is None:
                print("NON IN CSV", p, c["clip"]); continue
            cats, ns = verita(r)
            if cats != sorted(c["cats"]) or ns != c["noseq"]:
                print("DIFF|%s|%s|%s|%s|%s->%s|noseq %s->%s" % (p.split("sonno_audio")[-1], c["clip"], r["sequenza"], r["era"], c["cats"], cats, c["noseq"], ns))
            c.update(cats=cats, noseq=ns, seq=r["sequenza"], era=r["era"], giusto=r["giusto"], detto=r["detto"])
        json.dump(cl, open(p, "w"))
