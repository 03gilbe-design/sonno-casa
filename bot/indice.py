"""
Per ogni .py la prima riga della docstring, per ogni .md il titolo: cosi' nessuno rifa' quello che esiste gia'.
   python indice.py   -> scrive INDICE.md (sonno_bot + sonno_tex); rilanciarlo dopo ogni giro di lavoro
"""
import ast, os

RADICI = [r"C:\sonno_bot", r"C:\sonno_tex"]
SALTA = {".git", "__pycache__", "prova_bot_out", "vecchio", "MAPPA_A21s", "panns", "efficientat", "verifiche_gestore",
         "node_modules", "fonts", "references"}


def riga(p):
    try:
        if p.endswith(".py"):
            d = ast.get_docstring(ast.parse(open(p, encoding="utf-8", errors="replace").read())) or ""
            return d.strip().split("\n")[0][:110]
        if p.endswith(".md"):
            for l in open(p, encoding="utf-8", errors="replace"):
                if l.strip():
                    return l.strip().lstrip("# ")[:110]
    except (SyntaxError, ValueError, OSError):
        return "(non leggibile)"
    return ""


def albero(radice):
    out = [f"## {radice}"]
    for base, cartelle, file in os.walk(radice):
        cartelle[:] = sorted(c for c in cartelle if c not in SALTA and not c.startswith("."))
        liv = base[len(radice):].count(os.sep)
        utili = [f for f in sorted(file) if f.endswith((".py", ".md", ".sh"))]
        if not utili:
            continue
        out.append(f"{'  ' * liv}- **{os.path.relpath(base, radice)}/**")
        for f in utili:
            r = riga(os.path.join(base, f))
            out.append(f"{'  ' * (liv + 1)}- `{f}`" + (f" — {r}" if r else ""))
    return out


if __name__ == "__main__":
    righe = ["# INDICE dei file (generato da indice.py: non modificare a mano)", ""]
    for r in RADICI:
        righe += albero(r) + [""]
    open(os.path.join(RADICI[0], "INDICE.md"), "w", encoding="utf-8").write("\n".join(righe))
    print(len(righe), "righe -> INDICE.md")
