# Manda su @IlTuoBot le immagini gia' pronte del "mondo di Toppa" da valutare (una per messaggio, lettera + riga)
import os, sys
sys.path.insert(0, r"C:\sonno_bot")
from manda_valutazione import testo, file  # stesse funzioni (token da ~/.env)

E = r"C:\sonno_bot\concept\mondo\esempi"
testo("🧵 <b>Il mondo di Toppa</b> (dati finti). Rispondi a ognuna: ok / no / cosa cambiare.")
for lettera, f, d in [
    ("M1", "cartolina.png", "la settimana: coperta = ore, bottone = ti addormenti, rivetto = ti svegli"),
    ("M2", "espressioni_mondo.png", "le facce di Toppa nel suo mondo"),
    ("M3", "mattino_ottima.png", "notte ottima"),
    ("M4", "mattino_storta.png", "notte storta: fili sciolti = risvegli, onde = russato"),
    ("M5", "mattino_corta.png", "notte corta"),
    ("M6", "mattino_serie.png", "serie di notti buone"),
    ("M7", "mattino_esame.png", "notte da esame"),
    ("M8", "mattino_viaggio.png", "notte fuori casa"),
    ("M9", "mattino_pisolino.png", "pisolino"),
    ("M10", "mattino_prima.png", "prima notte in assoluto"),
    ("M11", "stato_pausa.png", "registrazione in pausa"),
    ("M12", "stato_vuoto.png", "notte senza dati"),
]:
    p = os.path.join(E, f)
    if os.path.exists(p):
        file("sendPhoto", "photo", p, f"{lettera} · {d}")
        print("ok", f)
