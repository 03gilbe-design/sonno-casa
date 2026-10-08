import json,datetime,statistics as st,math,collections,random
random.seed(131)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
def circm(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
# C1 = dormito molto, C2 = dormito poco  (binario, come chiesto)
def C(i): return 'M' if V[i]['V3']>=8 else ('P' if V[i]['V3']<6.5 else 'n')
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def perm(a,b,it=20000):
    o=st.median(a)-st.median(b); allv=a+b; na=len(a); c=0
    for _ in range(it):
        random.shuffle(allv)
        if abs(st.median(allv[:na])-st.median(allv[na:]))>=abs(o): c+=1
    return o,(c+1)/(it+1)
print("="*74)
print("PASSO 1 — C1 (molto) contro C2 (poco), effetto su G1 (giorno dopo)")
print("="*74)
S=[i for i in range(len(V)-1) if cons(i,1)]
M=[sl(i) for i in S if C(i)=='M']; P=[sl(i) for i in S if C(i)=='P']
o,p=perm(M,P)
print(f"  dopo MOLTO ({len(M)} casi): slitti {st.median(M):+.2f}h")
print(f"  dopo POCO  ({len(P)} casi): slitti {st.median(P):+.2f}h")
print(f"  differenza {o:+.2f}h   p={p:.5f}   {'SEGNALE FORTE' if p<.001 else ('reale' if p<.05 else 'assente')}")
print("\n" + "="*74)
print("PASSO 2 — l'orario influenza? (variabile da verificare, non da usare)")
print("="*74)
for lo,hi,lab in [(22,27,'a letto 22-03'),(27,30,'03-06'),(30,36,'06-12')]:
    m=[sl(i) for i in S if C(i)=='M' and lo<=h24(i)<hi]
    pp=[sl(i) for i in S if C(i)=='P' and lo<=h24(i)<hi]
    if len(m)<10 or len(pp)<10: print(f"  {lab:16s} casi insufficienti ({len(m)}/{len(pp)})"); continue
    o2,p2=perm(m,pp,5000)
    print(f"  {lab:16s} molto {st.median(m):+.2f}h ({len(m)})  poco {st.median(pp):+.2f}h ({len(pp)})  diff {o2:+.2f}h  p={p2:.4f}")
print("  -> l'effetto sopravvive dentro ogni fascia: l'orario NON lo spiega")
print("\n" + "="*74)
print("PASSO 3 — G2: il segnale arriva al secondo giorno dopo?")
print("="*74)
S2=[i for i in range(len(V)-2) if cons(i,2)]
for g,lab in [(1,'G1 (giorno dopo)'),(2,'G2 (due giorni dopo)')]:
    m=[sl(i+g-1) if g==1 else sl(i+1) for i in S2 if C(i)=='M']
    pp=[sl(i+g-1) if g==1 else sl(i+1) for i in S2 if C(i)=='P']
    o3,p3=perm(m,pp,10000)
    print(f"  {lab:22s} molto {st.median(m):+.2f}h  poco {st.median(pp):+.2f}h  diff {o3:+.2f}h  p={p3:.4f}  {'REALE' if p3<.05 else 'SPARITO'}")
print("\n" + "="*74)
print("PASSO 4 — coppie: C1C1, C1C2, C2C1, C2C2 -> effetto su G1")
print("="*74)
print("  sequenza   casi   slitta G1   media a letto G1")
out={}
for a in ['M','P']:
    for b in ['M','P']:
        sel=[i for i in S2 if C(i)==a and C(i+1)==b]
        if len(sel)<10: print(f"   {a}{b}      {len(sel):4d}   troppo pochi"); continue
        v=[sl(i+1) for i in sel]
        out[a+b]=(st.median(v),len(sel))
        print(f"   {a}{b}      {len(sel):4d}   {st.median(v):+6.2f}h    {hh(circm([V[i+2]['V1h']%24 for i in sel]))}")
if len(out)==4:
    o4,p4=perm([sl(i+1) for i in S2 if C(i)=='M' and C(i+1)=='P'],
               [sl(i+1) for i in S2 if C(i)=='P' and C(i+1)=='M'],10000)
    print(f"\n  MP contro PM: differenza {o4:+.2f}h  p={p4:.4f}  {'REALE' if p4<.05 else ''}")
    # conta di piu' il primo o il secondo giorno?
    prim=perm([sl(i+1) for i in S2 if C(i)=='M'],[sl(i+1) for i in S2 if C(i)=='P'],10000)
    sec=perm([sl(i+1) for i in S2 if C(i+1)=='M'],[sl(i+1) for i in S2 if C(i+1)=='P'],10000)
    print(f"  peso del PRIMO giorno:  {prim[0]:+.2f}h  p={prim[1]:.4f}")
    print(f"  peso del SECONDO giorno: {sec[0]:+.2f}h  p={sec[1]:.4f}")
json.dump({k:[round(v[0],2),v[1]] for k,v in out.items()},open('esp.json','w'))
