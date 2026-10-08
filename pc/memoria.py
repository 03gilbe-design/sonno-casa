"""Inventario A21s, sola lettura + proposta. Nessuna cancellazione/compressione.
python memoria.py                 # SSH A21s, ~/rec; tabella e MB
python memoria.py --json          # inventario dettagliato JSON
python memoria.py --radice DIR --bot DIR --manifest FILE --json  # campione locale
python memoria.py prova           # fixture locale e verifiche avversariali
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime

LIMITE = 20000
SOGLIA = 10**9  # 1 GB decimale, come nella tabella MB


def righe(path):
    try:
        if path.stat().st_size > 5_000_000:
            raise ValueError("metadati troppo grandi: " + str(path))
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def punteggio(path):
    try:
        x = float(path.read_text().split(",")[0])
        return x if 0 <= x <= 1 else None
    except (OSError, ValueError):
        return None


def hash_file(path):
    """Campioni limitati: nessun hash massivo implicito sul telefono."""
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("campione oltre 64 MiB: verifica separata richiesta")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blocco in iter(lambda: f.read(65536), b""):
            h.update(blocco)
    return h.hexdigest()


def verifica_copia(originale, record):
    """Rilegge copia locale recuperata; un ID remoto da solo non prova recuperabilita."""
    try:
        copia = Path(record["copia_locale"])
        if copia.resolve() == originale.resolve():
            return False
        return hash_file(originale) == hash_file(copia) == record["sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def inventario(radice, bot=None, manifest=None):
    radice = Path(radice).resolve()
    if not radice.is_dir():
        raise ValueError("cartella rec assente")
    files = []
    ignorati = []
    for base, dirs, nomi in os.walk(radice, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not Path(base, d).is_symlink())
        for n in sorted(nomi):
            p = Path(base, n)
            if p.is_symlink():
                ignorati.append(str(p.relative_to(radice)))
                continue
            files.append(p)
            if len(files) > LIMITE:
                raise ValueError("oltre 20000 file: inventario interrotto, restringere cartella")
    riferimenti = set()
    for root in (radice, Path(bot) if bot else radice):
        for n in ("giudizi.csv", "verifiche.csv", "etichette_drive.csv"):
            for r in righe(root / n):
                for valore in r.values():
                    if valore:
                        riferimenti.update(re.findall(r"[\w.-]+\.(?:m4a|wav|flac|mp3)", str(valore)))
    protetti = {Path(n).stem for n in riferimenti}
    disaccordi = set()
    for p in files:
        if p.suffix == ".panns":
            a, b = punteggio(p), punteggio(p.with_suffix(".eff"))
            if a is not None and b is not None and (a > .2) != (b > .2):
                disaccordi.add(p.stem)
    # Manifest unico opzionale: al massimo 20 campioni, mai archivio remoto presunto verificato.
    manifest = manifest or []
    if len(manifest) > 20:
        raise ValueError("oltre 20 campioni: restringere manifest")
    archivio = {}
    for r in manifest:
        nome = r["origine"]
        if nome in archivio:
            raise ValueError("origine duplicata nel manifest: " + nome)
        archivio[nome] = r
    dataset = {p.stem: str(p.relative_to(radice)).replace("\\", "/")
               for p in files if "dataset" in p.relative_to(radice).parts and p.suffix == ".csv"}
    # Dipendenze dichiarate: conservazione transitiva, anche originale di clip giudicata.
    dip_protette = set()
    for r in manifest:
        if Path(r["origine"]).stem in protetti | disaccordi:
            dip_protette.update(r.get("dipendenze", []))
    for _ in range(len(manifest)):
        for r in manifest:
            if r["origine"] in dip_protette:
                dip_protette.update(r.get("dipendenze", []))
    out = []
    for p in files:
        rel = str(p.relative_to(radice)).replace("\\", "/")
        cat, motivo = "DI VALORE", "valore ignoto: conservare finche' verificato"
        if rel in dip_protette:
            motivo = "originale collegato a giudizio/disaccordo: conservare"
        elif p.stem in protetti:
            motivo = "clip giudicata/Drive e relativi sidecar"
        elif p.stem in disaccordi:
            motivo = "disaccordo PANNs/EfficientAT e relativi sidecar"
        elif "dataset" in p.relative_to(radice).parts:
            motivo = "dataset: conservare categorie e provenienza"
        elif p.name in ("giudizi.csv", "verifiche.csv", "etichette_drive.csv", "archivio.json") or "etichette" in p.name:
            motivo = "etichette/giudizi: protezione permanente"
        elif "interi" in p.relative_to(radice).parts or p.suffix.lower() in (".m4a", ".wav", ".flac", ".mp3"):
            motivo = "registrazione/notte potenzialmente vera; assenza di giudizi non autorizza scarto"
        elif p.name.startswith(("notte", "minuti_")):
            motivo = "cronologia notti/minuti: conserva anche negativi e stanza vuota"
        elif p.suffix.lower() in (".log", ".txt", ".csv", ".json"):
            cat, motivo = "comprimibile", "testo: gzip reversibile solo dopo copia verificata"
        # Dataset/silenzio/copia non sono autorizzazioni di scarto.
        record = archivio.get(rel, {})
        dipendenze = list(record.get("dipendenze", []))
        if p.stem in dataset and "dataset" not in p.relative_to(radice).parts:
            dipendenze.append(dataset[p.stem])
            motivo += "; gia elaborato: dataset non sostituisce audio"
        if record.get("etichetta") == "silenzio":
            motivo += "; silenzio non autorizza scarto"
        recuperata = verifica_copia(p, record) if record else False
        destinazione = record.get("destinazione") or dict(tipo="da scegliere", id=None)
        if record:
            motivo += "; copia recuperata identica" if recuperata else "; recupero non verificato"
        out.append(dict(file=rel, bytes=p.stat().st_size, categoria=cat, motivo=motivo,
                        byte_recuperabili=0, dipendenze=sorted(set(dipendenze)),
                        destinazione=destinazione, recupero_verificato=recuperata,
                        archivio=dict(etichetta=record.get("etichetta", "ignota"),
                                      data=record.get("data"), origine=rel,
                                      sha256=record.get("sha256"),
                                      telegram=record.get("telegram"), drive=record.get("drive"))))
    # Duplicati solo se hash originale e copia sono stati entrambi verificati.
    gruppi_hash = defaultdict(list)
    for f in out:
        if f["recupero_verificato"]:
            gruppi_hash[f["archivio"]["sha256"]].append(f["file"])
    for f in out:
        duplicati = [n for n in gruppi_hash.get(f["archivio"]["sha256"], []) if n != f["file"]]
        f["duplicati_verificati"] = duplicati
        if duplicati:
            f["motivo"] += "; duplicato byte-identico: mantenuto in simulazione"
    libero = shutil.disk_usage(radice).free
    return dict(versione=1, simulazione=True, t=datetime.now().isoformat(timespec="seconds"),
                byte_recuperabili=0, radice=str(radice), libero_bytes=libero, soglia_bytes=SOGLIA,
                sotto_1GB=libero < SOGLIA, files=out, symlink_ignorati=ignorati,
                proposta_sotto_1GB=[
                    "Avvisare utente/Claude; nessuna azione automatica da questo script.",
                    "Sospendere nuove elaborazioni derivate; preservare registrazione e prove.",
                    "Copiare su archivio scelto e verificare hash prima di proporre spazio recuperabile.",
                    "Comprimere solo testi non attivi dopo approvazione; M4A/FLAC sono gia' compressi.",
                    "Mai scartare per solo silenzio o verdetto modello; buttabile richiede verifica umana."])


def tabella(d):
    gruppi = defaultdict(lambda: [0, 0])
    for f in d["files"]:
        g = gruppi[f["categoria"]]
        g[0] += 1
        g[1] += f["bytes"]
    print("Categoria       File          MB (decimali)")
    for c in ("DI VALORE", "comprimibile", "buttabile"):
        n, b = gruppi[c]
        print(f"{c:15} {n:5d} {b / 1e6:12.2f}")
    print(f"Totale: {sum(f['bytes'] for f in d['files']) / 1e6:.2f} MB; liberi: {d['libero_bytes'] / 1e6:.2f} MB")
    print("Sotto 1 GB: " + ("SI" if d["sotto_1GB"] else "NO"))
    print("Buttabile=0 finche' non esistono scarti verificati. MB logici, non risparmio promesso.")
    for r in d["proposta_sotto_1GB"]:
        print("- " + r)


def prova():
    import tempfile
    from unittest.mock import patch
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as t:
        p = Path(t)
        (p / "dataset").mkdir()
        (p / "dataset/a.csv").write_text("t,russa\n0,0\n")
        (p / "russa_a.m4a").write_bytes(b"prova")
        (p / "russa_a.panns").write_text("0.9,1")
        (p / "russa_a.eff").write_text("0.1,0")
        (p / "giudizi.csv").write_text("clip,giusto\nrussa_a.m4a,0\n")
        (p / "lavoro.tmp").write_text("in corso")
        (p / "analizza.log").write_text("log")
        prima = {str(f): f.read_bytes() for f in p.rglob("*") if f.is_file()}
        d = inventario(p)
        by = {f["file"]: f for f in d["files"]}
        assert by["russa_a.m4a"]["categoria"] == "DI VALORE"  # anche giudizio negativo
        assert by["dataset/a.csv"]["categoria"] == "DI VALORE"
        assert by["lavoro.tmp"]["categoria"] == "DI VALORE"
        assert by["analizza.log"]["categoria"] == "comprimibile"
        assert sum(f["bytes"] for f in d["files"]) == sum(len(v) for v in prima.values())
        assert prima == {str(f): f.read_bytes() for f in p.rglob("*") if f.is_file()}
        (p / "giudizi.csv").write_text("clip,giusto\n")
        d = inventario(p)
        assert "disaccordo" in next(f["motivo"] for f in d["files"] if f["file"] == "russa_a.m4a")
        with patch.object(shutil, "disk_usage", return_value=SimpleNamespace(free=SOGLIA-1)):
            assert inventario(p)["sotto_1GB"]
        with patch.object(shutil, "disk_usage", return_value=SimpleNamespace(free=SOGLIA)):
            assert not inventario(p)["sotto_1GB"]
    print("memoria: self-check PASS (protezione negativi, disaccordi, tmp attivi, byte, sola lettura)")


def main():
    if "prova" in sys.argv:
        prova()
        return
    if "--radice" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser(description="Conservazione: solo simulazione, nessuna cancellazione")
        parser.add_argument("--radice", required=True)
        parser.add_argument("--bot")
        parser.add_argument("--manifest")
        parser.add_argument("--json", action="store_true")
        args = parser.parse_args()
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8")) if args.manifest else None
        if manifest is not None and (manifest.get("versione") != 1 or not isinstance(manifest.get("files"), list)):
            raise ValueError("manifest atteso: versione=1, files=[...]")
        d = inventario(args.radice, args.bot, manifest["files"] if manifest else None)
    elif "--manifest" in sys.argv or "--bot" in sys.argv:
        raise ValueError("manifest e bot richiedono --radice locale esplicita")
    elif "--locale" in sys.argv:
        d = inventario(Path.home() / "rec", Path.home() / "sonno_bot")
    else:
        # Invia codice via stdin: esegue solo letture, nessun file installato sul telefono.
        sys.path.insert(0, r"C:\sonno_tex"); import a21  # solo sul PC: sul telefono questo ramo non gira
        r = subprocess.run(["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes",
                            "-o", "ConnectTimeout=8", a21.ip(), "python - --locale --json"],
                           input=Path(__file__).read_text(encoding="utf-8"), text=True,
                           encoding="utf-8", capture_output=True, timeout=45)
        if r.returncode:
            raise RuntimeError("SSH inventario fallito: " + r.stderr[-500:])
        d = json.loads(r.stdout)
    if "--json" in sys.argv:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        tabella(d)


if __name__ == "__main__":
    main()
