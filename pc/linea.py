import json,datetime,statistics as st,random,math
random.seed(5)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
dur=[n['V3'] for n in V]; n=len(dur); W=45
def mm(y,w): return [st.median(y[max(0,i-w+1):i+1]) for i in range(len(y))]
real=mm(dur,W)
amp_real=max(real[W:])-min(real[W:])
print("LA LINEA BLU SEGUE QUALCOSA DI VERO O E' RUMORE LISCIATO?\n")
print(f"la linea oscilla fra {min(real[W:]):.2f}h e {max(real[W:]):.2f}h  -> ampiezza {amp_real:.2f}h")
# rimescolo: se la nuvola non ha struttura temporale, la media mobile oscilla comunque?
amps=[]
for _ in range(2000):
    y=dur[:]; random.shuffle(y)
    m=mm(y,W); amps.append(max(m[W:])-min(m[W:]))
amps.sort()
p=sum(1 for a in amps if a>=amp_real)/len(amps)
print(f"\nrimescolando i tuoi stessi dati 2000 volte (stessa nuvola, ordine casuale):")
print(f"  ampiezza tipica del caso: {st.median(amps):.2f}h")
print(f"  soglia 95%: {amps[1899]:.2f}h")
print(f"  la tua: {amp_real:.2f}h   ->  p = {p:.4f}")
print(f"  VERDETTO: {'struttura REALE' if p<0.05 else 'la linea segue RUMORE: quelle onde le crea la media mobile'}")
# stessa cosa per il salto al 14 agosto sulla DURATA (non sulla regolarita)
i=[k for k,x in enumerate(V) if x['data']>='2025-08-14'][0]
d=st.median(dur[i:])-st.median(dur[:i])
sim=[]
for _ in range(3000):
    y=dur[:]; random.shuffle(y)
    sim.append(st.median(y[i:])-st.median(y[:i]))
p2=sum(1 for x in sim if abs(x)>=abs(d))/len(sim)
print(f"\nSALTO DELLA DURATA AL 14 AGOSTO:")
print(f"  prima {st.median(dur[:i]):.2f}h ({i} notti) | dopo {st.median(dur[i:]):.2f}h ({n-i} notti)")
print(f"  differenza {d:+.2f}h  p={p2:.4f}  -> {'reale' if p2<0.05 else 'NON significativa sulla durata'}")
