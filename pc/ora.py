import json,datetime,statistics as st,math,collections
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
def gap(i):
    return (datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
print("ULTIMI 12 GIORNI REGISTRATI\n")
print(" data         a letto   sveglia   dormito   ciclo")
for i in range(len(V)-12,len(V)):
    g=f"{gap(i):5.1f}h" if i<len(V)-1 else "  --"
    print(f" {V[i]['d']}   {hh(V[i]['V1h'])}     {hh(V[i]['V2h'])}     {V[i]['V3']:4.1f}h   {g}")
# stato attuale
last=len(V)-1
print(f"\nultima notte nei dati: {V[last]['d']}  (a letto {hh(V[last]['V1h'])}, dormito {V[last]['V3']:.1f}h)")
# firma degli ultimi 5 giorni
K=5
cur=[h24(i) for i in range(len(V)-K,len(V))]
print(f"\nFIRMA ULTIMI {K} GIORNI (ore a letto): {[hh(x) for x in cur]}")
# cerco periodi simili nello storico
S=[i for i in range(K,len(V)-6) if all((V[i-k]['d']-V[i-k-1]['d']).days==1 for k in range(K)) and all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(5))]
def dist(i):
    a=[h24(i-K+1+k) for k in range(K)]
    return st.mean(abs(x-y) for x,y in zip(a,cur))
sim=sorted(S,key=dist)[:12]
print(f"\nI 12 PERIODI PIU' SIMILI NELLO STORICO (su {len(S)} candidati):\n")
print(" fine periodo   scarto   poi nei 5 giorni dopo, a letto alle...")
for i in sim:
    dopo=[hh(V[i+k]['V1h']) for k in range(1,6)]
    print(f" {V[i]['d']}    {dist(i):4.1f}h   {' '.join(dopo)}")
# come vanno a finire
print("\nCOME VANNO A FINIRE (mediana sui 12 periodi simili):")
for k in range(1,6):
    v=[h24(i+k) for i in sim]
    d=[V[i+k]['V3'] for i in sim]
    print(f"  +{k} giorni: a letto ~{hh(st.median(v))}   dormito {st.median(d):.1f}h")
buona=lambda x: 22<=x<=27
fin=sum(1 for i in sim if buona(h24(i+5)))
print(f"\n  dopo 5 giorni, in finestra buona (22-03): {fin}/{len(sim)}")
