import json,datetime,statistics as st,math,collections,random
random.seed(137)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def cons(i,L): return all((V[i+k+1]['d']-V[i+k]['d']).days==1 for k in range(L))
def C(i): return 'M' if V[i]['V3']>=8 else ('P' if V[i]['V3']<6.5 else 'n')
def F(i):
    h=h24(i); return 'a' if h<27 else ('b' if h<30 else 'c')
def CIC(i):
    g=(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
    return 'corto' if g<23.5 else ('neutro' if g<=24.5 else 'lungo')
S=[i for i in range(len(V)-2) if cons(i,2)]
MOD=[("durata (3 stati)",       lambda i:C(i),                 1),
     ("orario (3 stati)",       lambda i:F(i),                 1),
     ("ciclo (3 stati)",        lambda i:CIC(i),               1),
     ("durata+orario (9)",      lambda i:C(i)+F(i),            1),
     ("durata x 2 giorni (9)",  lambda i:C(i-1)+C(i),          1),
     ("ciclo x 2 giorni (9)",   lambda i:CIC(i-1)+CIC(i),      1),
     ("ciclo+durata (9)",       lambda i:CIC(i)+C(i),          1)]
def valuta(f,target,folds=5):
    SS=[i for i in S if i>=1]
    n=len(SS); acc=[];base=[]
    for k in range(folds):
        cut=int(n*(.4+.12*k)); end=min(n,cut+int(n*.12))
        if end-cut<8: continue
        tr=SS[:cut]; te=SS[cut:end]
        T=collections.defaultdict(collections.Counter)
        for i in tr: T[f(i)][target(i+1)]+=1
        pri=collections.Counter(target(i+1) for i in tr)
        moda=pri.most_common(1)[0][0]
        for i in te:
            pred=T[f(i)].most_common(1)[0][0] if T[f(i)] else moda
            acc.append(pred==target(i+1)); base.append(moda==target(i+1))
    return st.mean(acc),st.mean(base),len(acc)
print("CATENE DI MARKOV — quale prevede meglio\n")
for tname,target in [("il CICLO di domani",CIC),("la DURATA di domani",C)]:
    print(f"\n### prevedere {tname}")
    print("  modello                    stati  precisione  banale   guadagno")
    r=[]
    for nome,f,_ in MOD:
        try:
            ns=len(set(f(i) for i in S if i>=1))
            a,b,n=valuta(f,target)
            r.append((a-b,nome,ns,a,b))
        except: continue
    r.sort(reverse=True)
    for g,nome,ns,a,b in r:
        flag='  <-- MIGLIORE' if (g,nome)==(r[0][0],r[0][1]) else ''
        print(f"  {nome:26s} {ns:3d}    {100*a:5.1f}%   {100*b:5.1f}%   {100*g:+5.1f}{flag}")
    json.dump([[x[1],x[2],round(100*x[3],1),round(100*x[4],1)] for x in r],open(f'mk_{"ciclo" if tname.startswith("il") else "durata"}.json','w'))
