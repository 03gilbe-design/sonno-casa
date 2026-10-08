import csv, glob, os, statistics as st
from datetime import datetime, timedelta

f = glob.glob(os.path.expanduser(r"~\Downloads\aum_2026-09-26\AUM_V4_Activity_*.csv"))[0]
ev = []
for r in csv.DictReader(open(f, encoding="utf-8-sig")):
    if not r["Time"] or r["App name"].startswith("Schermo"): continue  # piè di pagina / schermo spento non è uso
    t = datetime.strptime(r["Date"] + " " + r["Time"], "%d/%m/%y %H:%M:%S")
    h, m, s = map(int, r["Duration"].split(":"))
    ev.append((t, t + timedelta(hours=h, minutes=m, seconds=s), r["App name"]))
ev.sort()

GAP = timedelta(hours=3)  # ponytail: soglia fissa, pausa diurna lunga = falso sonno
sonni, fine = [], ev[0][1]
for i in range(1, len(ev)):
    if ev[i][0] - fine >= GAP:
        sonni.append((fine, ev[i][0], i))
    fine = max(fine, ev[i][1])

def minuti(app_sub, a, b):
    return sum((min(e, b) - max(s, a)).total_seconds() for s, e, n in ev
               if app_sub in n.lower() and e > a and s < b) / 60

print(f"{len(ev)} eventi {ev[0][0]:%d/%m} - {ev[-1][0]:%d/%m}, {len(sonni)} pause >=3h\n")
print("addorm.        risveglio      ore   TikTok 60' prima  ultima app")
tk, dur = [], []
for a, b, i in sonni:
    d = (b - a).total_seconds() / 3600
    m = minuti("tiktok", a - timedelta(hours=1), a)
    tk.append(m); dur.append(d)
    print(f"{a:%a %d/%m %H:%M}  {b:%a %d/%m %H:%M}  {d:4.1f}  {m:5.0f}            {ev[i-1][2]}")

ore = [a.hour + a.minute / 60 for a, _, _ in sonni]
print(f"\ndurata mediana {st.median(dur):.1f}h | TikTok ora prima: mediana {st.median(tk):.0f}' , "
      f">0 in {sum(m > 0 for m in tk)}/{len(tk)} notti")
print("addormentamento per fascia:", {k: sum(lo <= h < hi for h in ore) for k, (lo, hi) in
      {"21-03": (-1, -1), "03-08": (3, 8), "08-21": (8, 21)}.items()} | {"21-03": sum(h >= 21 or h < 3 for h in ore)})
if len(tk) > 3:
    print(f"r(TikTok prima, durata) = {st.correlation(tk, dur):.2f}  (n={len(tk)}, serve |r|>{2/len(tk)**.5:.2f} per p~0.05)")
