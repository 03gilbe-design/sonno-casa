"""Applica mappa_etichette.json: mappa('silenziownoise') -> 'silenzio/rumore_bianco'; principale(x) -> parte prima di '/'."""
import json, os
_M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mappa_etichette.json"), encoding="utf-8"))


def mappa(e):
    e = (e or "").strip().lower()
    if e in _M["esatte"]:
        return _M["esatte"][e]
    return next((t for p, t in _M["prefissi"] if e.startswith(p)), e)


def principale(e):
    return mappa(e).split("/")[0]


def categorie(e):
    """Tutte le categorie vere di un'etichetta: principale + 'anche' (es. movimento+respiro)."""
    e = (e or "").strip().lower()
    extra = next((v for k, v in _M.get("anche", {}).items() if e == k or e.startswith(k)), [])
    return [x for x in [principale(e)] + extra if x]


if __name__ == "__main__":
    for x in ("silenziownoise", "muoversi_nel_letto__resp", "tiktokaudiotelefono", "tiro_sul_con_il_naso", "russa", ""):
        print(repr(x), "->", mappa(x))
    assert categorie("muoversi_nel_letto__resp") == ["movimento", "respiro"] and categorie("russa") == ["russa"]
    assert principale("io_che_mi_muovo_nel_lett") == "movimento" and principale("tiktok") == "tiktok"
