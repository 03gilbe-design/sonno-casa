import json,datetime,statistics as st,random,math
random.seed(41)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cd(a,b):
    x=(a-b)%24; return x-24 if x>12 else x
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def gap(i):
    return (datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
# sequenze di 3 giorni consecutivi + 2 dopo
S=[i for i in range(len(V)-5) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(5))]
print(f"sequenze di 3 giorni con 2 giorni dopo: {len(S)}\n")
# firma della sequenza: i 3 cicli (quante ore fra un sonno e il successivo)
def firma(i): return (gap(i),gap(i+1),gap(i+2))
def simili(i,j,tol):
    a,b=firma(i),firma(j)
    return all(abs(x-y)<=tol for x,y in zip(a,b))
print("TRIPLETTE SIMILI: 3 cicli quasi uguali, poi cosa succede?\n")
print(" tolleranza  coppie   scarto 4o ciclo   scarto se a caso   p")
for tol in [1.5,2.0,3.0]:
    pr=[]
    for a in range(len(S)):
        for b in range(a+1,len(S)):
            i,j=S[a],S[b]
            if abs((V[i]['d']-V[j]['d']).days)<6: continue
            if simili(i,j,tol): pr.append((i,j))
    if len(pr)<15: print(f"  {tol:.1f}h       {len(pr):5d}   troppo poche"); continue
    div=[abs(gap(i+3)-gap(j+3)) for i,j in pr]
    rnd=[]
    for _ in range(4000):
        i,j=random.sample(S,2); rnd.append(abs(gap(i+3)-gap(j+3)))
    p=sum(1 for r in rnd if r<=st.median(div))/len(rnd)
    print(f"  {tol:.1f}h       {len(pr):5d}      {st.median(div):.2f}h            {st.median(rnd):.2f}h        {p:.3f}{'  <-- PATTERN' if p<.05 else ''}")
print("\n\nE SE GUARDO LA FORMA DELLA SEQUENZA (sale/scende) invece dei valori?")
def forma(i):
    return tuple('+' if gap(i+k)>24.5 else ('-' if gap(i+k)<23.5 else '=') for k in range(3))
import collections
c=collections.Counter(forma(i) for i in S)
tot=sum(c.values())
base=collections.Counter()
for i in S:
    for k in range(3):
        g=gap(i+k); base['+' if g>24.5 else ('-' if g<23.5 else '=')]+=1
T=sum(base.values())
print(" sequenza   osservate   attese se a caso   rapporto")
for pat,n in c.most_common(8):
    att=tot*math.prod(base[ch]/T for ch in pat)
    z=(n-att)/math.sqrt(max(1,att))
    print(f"  {''.join(pat)}        {n:4d}        {att:6.1f}         {n/att:.2f}x {'  SOPRA' if z>2 else ('  SOTTO' if z<-2 else '')}")
print("\n  + = ciclo lungo (slitti avanti) | - = ciclo corto (recuperi) | = neutro")
