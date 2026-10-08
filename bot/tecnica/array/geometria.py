"""
Coordinate LOCALI in cm, origine = centro del dispositivo appoggiato sul tavolo:
  x = verso destra, y = verso il lato "alto" del dispositivo (PC: verso la cerniera), z = in su dal tavolo.
Ogni punto ha la fonte: 'HMM' manuale Lenovo, 'PSREF' scheda Lenovo, 'UBR' ultrabookreview, 'stima' = da misurare.
   python geometria.py              -> tabella dei punti
   python geometria.py 3d           -> figura 3D (C:\\sonno_audio\\array\\geometria.png)
"""
import sys
import numpy as np

PC_W, PC_D, PC_H = 32.15, 21.75, 1.79          # PSREF 321,5 x 217,5 x 17,9 mm
# coperchio profondo quanto la base (chiuso la copre): ~21,7 cm; pannello NV140FHM-N4U 14" FHD area attiva ~309x174 mm;
SCHERMO_H = PC_D - 0.8
APERTURA = np.radians(110)                      # stima: angolo schermo-base (manopola da misurare)

cerniera = np.array([0, PC_D / 2, PC_H])
alto = cerniera + SCHERMO_H * np.array([0, -np.cos(APERTURA), np.sin(APERTURA)])  # bordo alto dello schermo

PUNTI = {
    # (dispositivo, nome): (x, y, z, tipo, fonte)
    ("PC", "cassa_sx"):  (-PC_W / 2 + 1.5, -PC_D / 2 + 5, PC_H, "bocca", "HMM fig.20 + UBR: griglie ai lati tastiera, parte bassa; cm = stima"),
    ("PC", "cassa_dx"):  (+PC_W / 2 - 1.5, -PC_D / 2 + 5, PC_H, "bocca", "idem"),
    ("PC", "mic_sx"):    (-2.5, alto[1], alto[2] - 0.8, "orecchio", "HMM fig.2: microphone board sulla camera; +-2,5 cm = stima"),
    ("PC", "mic_dx"):    (+2.5, alto[1], alto[2] - 0.8, "orecchio", "idem"),
    # Samsung Galaxy A56 (SM-A566B) 16,1 x 7,75 x 0,74 cm, sdraiato a faccia in su: stereo (basso + capsula)
    ("A56", "cassa_basso"):  (0, -8.0, 0.4, "bocca", "stima: griglia sul bordo basso"),
    ("A56", "cassa_alto"):   (0, +7.8, 0.7, "bocca", "stima: capsula auricolare usata come 2a cassa stereo"),
    ("A56", "mic_basso"):    (-1.5, -8.0, 0.4, "orecchio", "stima: foro sul bordo basso"),
    # Samsung Galaxy A21s (SM-A217F) 16,4 x 7,5 x 0,9 cm: cassa mono in basso
    ("A21s", "cassa_basso"): (+1.5, -8.2, 0.45, "bocca", "stima: griglia bordo basso"),
    ("A21s", "mic_basso"):   (-0.5, -8.2, 0.45, "orecchio", "stima: foro bordo basso"),
    ("webcam", "mic"):       (0, 0, 0, "orecchio", "posizione globale da misurare"),
}


def globale(dispositivo, pos, rot_gradi=0.0):
    """Punti del dispositivo messo sul tavolo in `pos` (x, y cm) ruotato di `rot_gradi` attorno a z."""
    a = np.radians(rot_gradi); R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    return {n: R @ np.array(p[:3]) + np.array([pos[0], pos[1], 0])
            for (d, n), p in PUNTI.items() if d == dispositivo}


def tabella():
    print(f"{'dispositivo':10s} {'punto':12s} {'x':>6s} {'y':>6s} {'z':>6s}  tipo      fonte")
    for (d, n), (x, y, z, t, f) in PUNTI.items():
        print(f"{d:10s} {n:12s} {x:6.1f} {y:6.1f} {z:6.1f}  {t:8s}  {f}")
    print(f"\nPC: bocca dx -> orecchio dx = {np.linalg.norm(np.array(PUNTI['PC', 'cassa_dx'][:3]) - np.array(PUNTI['PC', 'mic_dx'][:3])):.1f} cm")


def figura():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    ax = plt.figure(figsize=(7, 6)).add_subplot(projection="3d")
    for (d, n), (x, y, z, t, _) in PUNTI.items():
        if d == "webcam":
            continue
        ax.scatter(x, y, z, c="tab:red" if t == "bocca" else "tab:blue", s=40)
        ax.text(x, y, z, f"{d}.{n}", fontsize=7)
    ax.set_xlabel("x cm"); ax.set_ylabel("y cm"); ax.set_zlabel("z cm")
    ax.set_title("coordinate LOCALI (ognuno nel suo centro) - rosso bocca, blu orecchio")
    plt.savefig(r"C:\sonno_audio\array\geometria.png", dpi=110); print("salvata C:\\sonno_audio\\array\\geometria.png")


if __name__ == "__main__":
    tabella()
    if sys.argv[1:] == ["3d"]:
        figura()
