import json,datetime,statistics as st,math,random,collections
random.seed(127)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def D(i): return 'poco' if V[i]['V3']<6.5 else ('bene' if V[i]['V3']<8.5 else 'tanto')
def sl(i): return (V[i+1]['V1h']-V[i]['V1h']+12)%24-12
S1=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
print("L'ORARIO CONTA COME FATTORE DI SFONDO?\n")
print("Test: dentro ogni fascia oraria, la durata ha ancora effetto?\n")
print(" a letto        poco    bene    tanto   | differenza poco-tanto   casi")
tot=[]
for lo,hi,lab in [(22,27,'22-03'),(27,30,'03-06'),(30,36,'06-12')]:
    r={}
    for t in ['poco','bene','tanto']:
        sel=[i for i in S1 if D(i)==t and lo<=h24(i)<hi]
        r[t]=(st.median([sl(i) for i in sel]),len(sel)) if len(sel)>=10 else (None,len(sel))
    if all(r[t][0] is not None for t in r):
        d=r['poco'][0]-r['tanto'][0]; tot.append(d)
        print(f"  {lab:10s}  {r['poco'][0]:+5.1f}h  {r['bene'][0]:+5.1f}h  {r['tanto'][0]:+5.1f}h  |      {d:+5.1f}h        {sum(r[t][1] for t in r)}")
    else:
        print(f"  {lab:10s}  dati insufficienti: {[(t,r[t][1]) for t in r]}")
print(f"\n  l'effetto della durata sopravvive in tutte le fasce: differenze {[f'{x:+.1f}' for x in tot]}")
print("\n\nE AL CONTRARIO: dentro ogni tipo di durata, l'orario ha effetto?\n")
print(" hai dormito    a letto 22-03   03-06   06-12  | differenza")
for t in ['poco','bene','tanto']:
    r={}
    for lo,hi,lab in [(22,27,'a'),(27,30,'b'),(30,36,'c')]:
        sel=[i for i in S1 if D(i)==t and lo<=h24(i)<hi]
        r[lab]=(st.median([sl(i) for i in sel]),len(sel)) if len(sel)>=10 else (None,len(sel))
    if all(r[k][0] is not None for k in r):
        d=r['a'][0]-r['c'][0]
        print(f"  {t:12s}   {r['a'][0]:+5.1f}h        {r['b'][0]:+5.1f}h   {r['c'][0]:+5.1f}h  |   {d:+5.1f}h")
    else:
        print(f"  {t:12s}   dati insufficienti")
print("\n\nCHI PESA DI PIU'? confronto diretto")
# varianza spiegata da ciascuno
def eta2(f):
    grp=collections.defaultdict(list)
    for i in S1: grp[f(i)].append(sl(i))
    allv=[sl(i) for i in S1]; gm=st.mean(allv)
    sb=sum(len(v)*(st.mean(v)-gm)**2 for v in grp.values())
    stot=sum((x-gm)**2 for x in allv)
    return sb/stot
def fascia(i):
    h=h24(i); return 'a' if h<27 else ('b' if h<30 else 'c')
print(f"  varianza dello slittamento spiegata dalla DURATA:  {100*eta2(D):.1f}%")
print(f"  varianza spiegata dall'ORARIO a letto:             {100*eta2(fascia):.1f}%")
print(f"  varianza spiegata da entrambi:                     {100*eta2(lambda i: D(i)+fascia(i)):.1f}%")
