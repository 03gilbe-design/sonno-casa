"""Rianalizza le prove salvate in C:/sonno_audio/array/disposizioni/<nome>/ (niente suoni) e stampa una riga per prova.
   python rianalizza.py [nome ...]      (default: tutte le cartelle con rip_a56.m4a)
"""
import contextlib, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ripetuti as r

DISP = "C:/sonno_audio/array/disposizioni"


def una(nome):
    r.RIS.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r.analizza(os.path.join(DISP, nome))
    except Exception as e:
        return f"{nome:26s} ERRORE {e}"
    f = lambda k: (f"{r.RIS[k][0]:7.3f}+-{r.RIS[k][1] * 100:4.1f}" if k in r.RIS else "      -       ")
    return f"{nome:26s} A56-A21s {f('A56-A21s')}  A56-PC {f('A56-PC')}  A21s-PC {f('A21s-PC')}  tdoaIntel {f('tdoa_PCintel')}"


if __name__ == "__main__":
    nomi = sys.argv[1:] or sorted(d for d in os.listdir(DISP) if os.path.exists(os.path.join(DISP, d, "rip_a56.m4a")))
    for n in nomi:
        print(una(n), flush=True)
