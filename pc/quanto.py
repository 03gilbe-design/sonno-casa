import json,statistics as st,random,math
random.seed(9)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
dur=[n['V3'] for n in V]; n=len(dur)
def mm(y,w): return [st.median(y[max(0,i-w+1):i+1]) for i in range(len(y))]
print("QUANTA PARTE DELLA NUVOLA E' RIASSUMIBILE IN UNA LINEA?\n")
print(" finestra   ampiezza linea   ampiezza se rumore   quota vera   p")
for W in [7,15,30,45,60,90]:
    real=mm(dur,W); amp=max(real[W:])-min(real[W:])
    sims=[]
    for _ in range(400):
        y=dur[:]; random.shuffle(y); m=mm(y,W); sims.append(max(m[W:])-min(m[W:]))
    sims.sort(); med=st.median(sims)
    p=sum(1 for a in sims if a>=amp)/len(sims)
    quota=100*max(0,amp-med)/amp if amp else 0
    print(f"  {W:3d} gg     {amp:.2f}h            {med:.2f}h            {quota:4.0f}%     {p:.3f}")
print("\n  'quota vera' = quanta parte dell'oscillazione NON e' creata dal lisciamento")
# quanta varianza spiega la linea
W=45; real=mm(dur,W)
res=[a-b for a,b in zip(dur[W:],real[W:])]
tot=st.pvariance(dur[W:]); resid=st.pvariance(res)
print(f"\nVARIANZA SPIEGATA dalla linea (finestra 45gg): {100*(1-resid/tot):.1f}%")
print(f"  la nuvola ha deviazione {math.sqrt(tot):.2f}h, la linea si muove di {st.pstdev(real[W:]):.2f}h")
print(f"  -> la linea cattura una frazione piccola: il resto e' variabilita' notte-per-notte")
