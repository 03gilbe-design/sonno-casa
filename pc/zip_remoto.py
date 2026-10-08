"""
solo i file che servono, non tutto lo zip. Uso: z = apri(url); z.namelist(); estrai(z, nome, dest)."""
import io, os, shutil, urllib.request, zipfile


class Remoto(io.RawIOBase):
    def __init__(s, u):
        r = urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=60)
        s.n, s.u, s.p = int(r.headers["Content-Length"]), r.url, 0

    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.p

    def seek(s, o, w=0):
        s.p = o if w == 0 else s.p + o if w == 1 else s.n + o
        return s.p

    def readinto(s, b):
        if s.p >= s.n or not len(b):
            return 0
        fine = min(s.p + len(b), s.n) - 1
        d = urllib.request.urlopen(urllib.request.Request(s.u, headers={"Range": f"bytes={s.p}-{fine}"}), timeout=120).read()
        b[:len(d)] = d
        s.p += len(d)
        return len(d)


def apri(url):
    return zipfile.ZipFile(io.BufferedReader(Remoto(url), buffer_size=8 << 20))


def estrai(z, nome, dest):
    out = os.path.join(dest, nome)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with z.open(nome) as a, open(out + ".part", "wb") as b:
        shutil.copyfileobj(a, b, 8 << 20)
    os.replace(out + ".part", out)  # un file c'e' solo se completo
    return out
