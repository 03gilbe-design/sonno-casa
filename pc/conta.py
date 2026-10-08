import json,datetime,statistics as st,math,collections,random
random.seed(139)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
print("QUANTE COMBINAZIONI ESISTONO IN TOTALE\n")
print(" categorie  1 giorno  2 giorni  3 giorni  4 giorni   e con l'orario (x3)")
for k in [2,3,4,5]:
    print(f"    {k}        {k:4d}     {k**2:5d}     {k**3:5d}     {k**4:5d}      {k*3:4d} / {(k*3)**2:5d} / {(k*3)**3:6d}")
print("\n  con 416 notti servono ~10 casi per combinazione: il tetto pratico e' ~40 combinazioni")
def prova(nc):
    """nc categorie di durata, taglio per quantili"""
    dur=sorted(n['V3'] for n in V)
    q=[dur[int(len(dur)*(j+1)/nc)-1] for j in range(nc-1)]
    def C(i):
        d=V[i]['V3']
        for j,t in enumerate(q):
            if d<=t: return chr(65+j)
        return chr(65+nc-1)
    return C,q
print("\n\n" + "="*72)
print("PROVO CON 3 CATEGORIE: molto / medio / poco")
print("="*72)
for nc in [2,3,4]:
    C,q=prova(nc)
    S=[i for i in range(len(V)-1) if cons(i,1)]
    grp=collections.defaultdict(list)
    for i in S: grp[C(i)].append(sl(i))
    S2=[i for i in range(len(V)-2) if cons(i,2)]
    g2=collections.defaultdict(list)
    for i in S2: g2[C(i)+C(i+1)].append(sl(i+1))
    S3=[i for i in range(len(V)-3) if cons(i,3)]
    g3=collections.defaultdict(list)
    for i in S3: g3[C(i)+C(i+1)+C(i+2)].append(sl(i+2))
    ok1=sum(1 for v in grp.values() if len(v)>=10)
    ok2=sum(1 for v in g2.values() if len(v)>=10)
    ok3=sum(1 for v in g3.values() if len(v)>=10)
    sp1=max(st.median(v) for v in grp.values())-min(st.median(v) for v in grp.values())
    v2=[st.median(v) for v in g2.values() if len(v)>=10]
    v3=[st.median(v) for v in g3.values() if len(v)>=10]
    print(f"\n {nc} categorie (soglie a {[round(x,1) for x in q]} ore)")
    print(f"   1 giorno: {ok1}/{nc} usabili, escursione {sp1:.1f}h")
    print(f"   2 giorni: {ok2}/{nc**2} usabili, escursione {max(v2)-min(v2) if v2 else 0:.1f}h")
    print(f"   3 giorni: {ok3}/{nc**3} usabili, escursione {max(v3)-min(v3) if v3 else 0:.1f}h")
