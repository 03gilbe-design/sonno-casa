"""Recensioni italiane (solo testo + stelle, niente nomi/ID) e descrizioni ufficiali IT di app del sonno/tono dal Play Store."""
import json
from google_play_scraper import app, reviews, Sort

APP = {"Sleep Cycle": "com northcube sleepcycle", "SnoreLab": "com snorelab app",
       "Sleep as Android": "com urbandroid sleep", "Pokémon Sleep": "jp pokemon pokemonsleep",
       "Finch": "com finch finch", "Duolingo": "com duolingo", "Headspace": "com getsomeheadspace android",
       "BetterSleep": "ipnossoft rain"}
rec, desc = [], {}
for nome, pkg in APP.items():
    pkg = pkg.replace(" ", ".")
    try:
        d = app(pkg, lang="it", country="it")
        desc[nome] = {"pkg": pkg, "titolo": d.get("title"), "breve": d.get("summary"), "descrizione": d.get("description")}
        rs, _ = reviews(pkg, lang="it", country="it", sort=Sort.MOST_RELEVANT, count=400)
        rec += [{"app": nome, "stelle": r["score"], "testo": r["content"]} for r in rs if r.get("content")]
        print(nome, len(rs))
    except Exception as e:
        print(nome, "ERRORE", e)
json.dump(rec, open("recensioni_it.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump(desc, open("descrizioni_it.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("recensioni:", len(rec))
