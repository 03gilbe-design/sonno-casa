"""
pipe in testo su Windows). Uso: python C:/sonno_bot/tecnica/controlla_file.py file1 [file2 ...]  -> exit 1 se sporchi.
"""
import sys

AMMESSI = {9, 10}  # TAB e a-capo sono normali nel testo; il resto sotto 32 no (compreso \r solitario)


def sporchi(path):
    dati = open(path, "rb").read()
    out = []
    for n, riga in enumerate(dati.split(b"\n"), 1):
        riga = riga[:-1] if riga.endswith(b"\r") and dati.count(b"\r\n") == dati.count(b"\n") else riga  # file CRLF coerente
        brutti = sorted({c for c in riga if c < 32 and c not in AMMESSI})
        if brutti:
            out.append((n, [hex(c) for c in brutti], riga[:80].decode("utf-8", "replace")))
    return out


if __name__ == "__main__":
    male = False
    for p in sys.argv[1:]:
        for n, codici, testo in sporchi(p):
            male = True
            print(f"{p}:{n}: {codici}  {testo!r}")
    print("SPORCO" if male else "pulito")
    sys.exit(1 if male else 0)
