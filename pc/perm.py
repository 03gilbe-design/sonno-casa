import json,datetime,statistics as st,math,itertools,collections,random
random.seed(97)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
def circm(hs):
    S=sum(math.sin(h/24*2*math.pi) for h in hs); C=sum(math.cos(h/24*2*math.pi) for h in hs); n=len(hs)
    return (math.atan2(S/n,C/n))%(2*math.pi)/(2*math.pi)*24
# le tre dimensioni
def C1(i):  # quanto dormi
    d=V[i]['V3']
    return 'P' if d<6.5 else ('N' if d<8.5 else 'T')   # Poco/Normale/Tanto
def C2(i):  # quando vai a letto
    h=h24(i)
    return 'p' if h<26 else ('m' if h<29 else 't')      # presto(<02) / medio(02-05) / tardi(>05)
def C3(i):  # quando ti svegli
    s=V[i]['V2h']%24
    return 'a' if s<11 else ('b' if s<14 else 'c')      # presto/medio/tardi
def stato(i,dims): return ''.join(f(i) for f in dims)
def buona(i): return 22<=h24(i)<=27
S1=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
S2=[i for i in range(len(V)-2) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(2))]
S3=[i for i in range(len(V)-3) if all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(3))]
print(f"giorni utilizzabili: 1g={len(S1)}  2g={len(S2)}  3g={len(S3)}\n")
BASE=sum(1 for i in S1 if buona(i+1))/len(S1)
print(f"probabilita' di base di finire in orario il giorno dopo: {100*BASE:.0f}%\n")
def analizza(S,L,dims,nome,minn=15):
    out=[]
    grp=collections.defaultdict(list)
    for i in S:
        k=tuple(stato(i+d,dims) for d in range(L))
        grp[k].append(i)
    for k,idx in grp.items():
        if len(idx)<minn: continue
        ok=sum(1 for i in idx if buona(i+L))
        p=ok/len(idx)
        # test binomiale approssimato
        z=(p-BASE)/math.sqrt(BASE*(1-BASE)/len(idx))
        out.append((abs(z),z,''.join('·'.join(k)),len(idx),100*p,circm([V[i+L]['V1h']%24 for i in idx])))
    out.sort(reverse=True)
    print(f"\n=== {nome}  ({len(grp)} combinazioni possibili, {len([g for g in grp.values() if len(g)>=minn])} con almeno {minn} casi)")
    print(" combinazione       casi   in orario   media a letto   segnale")
    for az,z,k,n,pc,m in out[:10]:
        sig='FORTE' if abs(z)>2.6 else ('debole' if abs(z)>1.9 else '')
        print(f"  {k:16s} {n:5d}    {pc:4.0f}%       {hh(m)}        z={z:+.2f} {sig}")
    return out
print("LEGENDA  C1 quanto dormi: P=poco(<6.5h) N=normale T=tanto(8.5h+)")
print("         C2 quando a letto: p=presto(<02) m=medio(02-05) t=tardi(>05)")
print("         C3 quando sveglia: a=presto(<11) b=medio(11-14) c=tardi(>14)")
r1=analizza(S1,1,[C1],"1 GIORNO - solo C1 (durata)")
r2=analizza(S1,1,[C1,C2],"1 GIORNO - C1+C2 (durata x ora a letto)")
r3=analizza(S1,1,[C1,C2,C3],"1 GIORNO - C1+C2+C3 (tutte e tre)",minn=12)

print("\n\n" + "="*70)
print("CORREZIONE PER TEST MULTIPLI: cerco fra 20 combinazioni, una spicca per caso")
print("="*70)
def permtest(S,L,dims,minn,IT=2000):
    grp=collections.defaultdict(list)
    for i in S: grp[tuple(stato(i+d,dims) for d in range(L))].append(i)
    valid={k:v for k,v in grp.items() if len(v)>=minn}
    def maxz(mapping):
        best=0
        for k,idx in valid.items():
            ok=sum(mapping[i] for i in idx); p=ok/len(idx)
            z=abs((p-BASE)/math.sqrt(BASE*(1-BASE)/len(idx)))
            best=max(best,z)
        return best
    real={i:(1 if buona(i+L) else 0) for i in S}
    obs=maxz(real)
    vals=list(real.values())
    sims=[]
    for _ in range(IT):
        random.shuffle(vals)
        sims.append(maxz(dict(zip(S,vals))))
    sims.sort()
    p=sum(1 for x in sims if x>=obs)/IT
    return obs,sims[int(.95*IT)],p,len(valid)
for nome,dims,minn in [("solo C1",[C1],15),("C1+C2",[C1,C2],15),("C1+C2+C3",[C1,C2,C3],12)]:
    obs,soglia,p,nv=permtest(S1,1,dims,minn)
    v="REALE" if p<0.05 else "puo' essere caso"
    print(f"  {nome:10s}: max |z| osservato {obs:.2f} | soglia del caso {soglia:.2f} | p={p:.4f} -> {v}  ({nv} gruppi)")
