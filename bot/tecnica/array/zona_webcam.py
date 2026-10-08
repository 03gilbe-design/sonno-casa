"""
TDOA: d(webcam,A21s) - d(webcam,A56) = DIFF; distanza A56-A21s = BASE -> lontano dai due la webcam sta in un
cono di semiapertura acos(DIFF/BASE) attorno al prolungamento A21s->A56, oltre l'A56.
ponytail: foto in prospettiva, pixel dei telefoni a mano; il punto 3D vero dopo l'analisi con le 2 casse del PC.
   python zona_webcam.py [manda]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw

D = "C:/sonno_audio/array/disposizioni/3d_webcam"
DIFF, BASE = 0.467, 0.549
A21S, A56 = np.array([180, 525]), np.array([1000, 422])  # pixel nella foto (bordo USB circa)


def main(manda=False):
    im = Image.open(f"{D}/foto.jpg").convert("RGB")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); g = ImageDraw.Draw(ov)
    u = (A56 - A21S) / np.linalg.norm(A56 - A21S)
    mezzo = np.arccos(DIFF / BASE)
    rot = lambda v, a: np.array([v[0] * np.cos(a) - v[1] * np.sin(a), v[0] * np.sin(a) + v[1] * np.cos(a)])
    L = 900
    g.polygon([tuple(A56), tuple(A56 + L * rot(u, mezzo)), tuple(A56 + L * rot(u, -mezzo))], fill=(230, 57, 70, 70))
    g.line([tuple(A21S), tuple(A56 + L * u)], fill=(230, 57, 70, 255), width=3)
    for p, t in ((A21S, "A21s"), (A56, "A56")):
        g.ellipse([p[0] - 9, p[1] - 9, p[0] + 9, p[1] + 9], fill=(230, 57, 70, 255))
        g.text((p[0] + 12, p[1] - 28), t, fill=(255, 255, 255, 255), font_size=26)
    g.text((20, 20), f"webcam: nel cono rosso (±{np.degrees(mezzo):.0f}°) oltre l'A56\n"
                     f"arriva 47 cm prima all'A56 che all'A21s", fill=(255, 255, 255, 255), font_size=28)
    out = f"{D}/zona_webcam.jpg"
    Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB").save(out, quality=90)
    print("salvato", out, f"semiapertura {np.degrees(mezzo):.1f} gradi")
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendPhoto", "photo", out, "📍 Dove penso sia la webcam: nel cono rosso oltre l'A56 (zona, non punto; "
               "il punto 3D dopo l'analisi con le due casse del PC)")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
