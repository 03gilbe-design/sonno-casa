"""
Sull'A21s, in ~/confronto: python negativi.py notte/*.wav -> per file: max YAMNet, max PANNs, secondi sopra soglia."""
import sys
import confronto as cf

for f in sys.argv[1:]:
    y, hy = cf.curva_yamnet(f)
    p, hp = cf.curva_panns(f)
    print(f"{f}: YAMNet max {y.max():.2f} ({(y > cf.SOGLIA).sum() * hy:.0f} s sopra) | "
          f"PANNs max {p.max():.2f} ({(p > cf.SOGLIA).sum() * hp:.0f} s sopra)", flush=True)
