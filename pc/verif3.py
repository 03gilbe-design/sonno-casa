import json,datetime,statistics as st,math,collections,random
random.seed(149)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
dur=sorted(n['V3'] for n in V)
q=[dur[int(len(dur)*(j+1)/3)-1] for j in range(2)]
NOMI={'A':'poco','B':'medio','C':'molto'}
def C(i):
    d=V[i]['V3']
    return 'A' if d<=q[0] else ('B' if d<=q[1] else 'C')
print(f"soglie: poco <{q[0]:.1f}h | medio {q[0]:.1f}-{q[1]:.1f}h | molto >{q[1]:.1f}h\n")
def maxrange_test(L,minn,IT=2000):
    S=[i for i in range(len(V)-L) if cons(i,L)]
    grp=collections.defaultdict(list)
    for i in S: grp[tuple(C(i+k) for k in range(L))].append(i)
    valid={k:v for k,v in grp.items() if len(v)>=minn}
    def rng(mp):
        m=[st.median([mp[i] for i in idx]) for idx in valid.values()]
        return max(m)-min(m)
    real={i:sl(i+L-1) for i in S}
    obs=rng(real); vals=list(real.values()); sims=[]
    for _ in range(IT):
        random.shuffle(vals); sims.append(rng(dict(zip(S,vals))))
    sims.sort(); p=sum(1 for x in sims if x>=obs)/IT
    return obs,sims[int(.95*IT)],p,len(valid),grp
print(" livello   combinazioni usabili   escursione   soglia del caso   p")
for L,minn in [(1,10),(2,10),(3,8)]:
    obs,soglia,p,nv,grp=maxrange_test(L,minn)
    v='REALE' if p<.05 else 'e solo rumore'
    print(f"  {L} giorn{'o' if L==1 else 'i'}        {nv:3d} su {3**L:3d}          {obs:.1f}h          {soglia:.1f}h        {p:.4f}  {v}")
# dettaglio 1 e 2 giorni
print("\n\nDETTAGLIO — 1 giorno")
S=[i for i in range(len(V)-1) if cons(i,1)]
for k in ['A','B','C']:
    v=[sl(i) for i in S if C(i)==k]
    print(f"  {NOMI[k]:6s} ({len(v):3d} casi): {st.median(v):+.2f}h")
print("\nDETTAGLIO — 2 giorni (tutte e 9)")
S2=[i for i in range(len(V)-2) if cons(i,2)]
g2=collections.defaultdict(list)
for i in S2: g2[C(i)+C(i+1)].append(sl(i+1))
for k in sorted(g2,key=lambda x:st.median(g2[x])):
    print(f"  {NOMI[k[0]]:6s} poi {NOMI[k[1]]:6s} ({len(g2[k]):3d} casi): {st.median(g2[k]):+.2f}h")
json.dump({f"{NOMI[k[0]]}+{NOMI[k[1]]}":[round(st.median(v),2),len(v)] for k,v in g2.items()},open('tre.json','w'))
