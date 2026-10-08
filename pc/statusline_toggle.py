# senza console apre una finestra conhost a ogni aggiornamento, ~ogni 10 s). Copia di sicurezza prima di cambiare.
import json, os, shutil, sys
p = os.path.expanduser("~/.claude/settings.json"); bak = p + ".statusline_salvata.json"
d = json.load(open(p, encoding="utf-8"))
if sys.argv[1:] == ["off"]:
    if "statusLine" in d:
        json.dump(d["statusLine"], open(bak, "w", encoding="utf-8"), indent=2)
        del d["statusLine"]
    print("Riga di stato SPENTA. Riapri le sessioni di Claude Code.")
else:
    if os.path.exists(bak):
        d["statusLine"] = json.load(open(bak, encoding="utf-8"))
    print("Riga di stato RIACCESA:", d.get("statusLine"))
shutil.copy(p, p + ".bak_toggle")
json.dump(d, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
