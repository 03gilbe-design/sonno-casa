import json,datetime,statistics as st,math,collections,random
random.seed(101)
V=json.load(open(r"~\.claude\jobs\988b1519\tmp\vars.json"))['notti']
for n in V: n['d']=datetime.date.fromisoformat(n['data'])
def h24(i): return V[i]['V1h'] if V[i]['V1h']>=12 else V[i]['V1h']+24
def hh(v): return f"{int(v)%24:02d}:{int((v%1)*60):02d}"
S=[i for i in range(len(V)-1) if (V[i+1]['d']-V[i]['d']).days==1]
# definizioni di stato alternative
def s_ora3(i):
    h=h24(i); return 'presto' if h<26 else ('medio' if h<29 else 'tardi')
def s_ora4(i):
    h=h24(i)
    return 'A' if h<25 else ('B' if h<27.5 else ('C' if h<30 else 'D'))
def s_dur(i):
    d=V[i]['V3']; return 'poco' if d<6.5 else ('norm' if d<8.5 else 'tanto')
def s_ciclo(i):
    if i+1>=len(V): return '?'
    g=(datetime.datetime.fromisoformat(V[i+1]['V1'])-datetime.datetime.fromisoformat(V[i]['V1'])).total_seconds()/3600
    return 'corto' if g<23.5 else ('neutro' if g<=24.5 else 'lungo')
def s_ora_dur(i): return s_ora3(i)+'/'+s_dur(i)
def s_ora_sv(i):
    s=V[i]['V2h']%24
    return s_ora3(i)+'/'+('sv-presto' if s<11 else ('sv-medio' if s<14 else 'sv-tardi'))
MODELLI=[("ora del sonno, 3 stati",s_ora3),("ora del sonno, 4 stati",s_ora4),
         ("durata, 3 stati",s_dur),("lunghezza del ciclo",s_ciclo),
         ("ora x durata, 9 stati",s_ora_dur),("ora x sveglia, 9 stati",s_ora_sv)]
def valuta(f,folds=5):
    """precisione nel prevedere lo STATO del giorno dopo, validazione cronologica"""
    n=len(S); acc=[];base=[]
    for k in range(folds):
        cut=int(n*(.4+.12*k)); end=min(n,cut+int(n*.12))
        if end-cut<10: continue
        tr=S[:cut]; te=S[cut:end]
        T=collections.defaultdict(collections.Counter)
        for i in tr:
            if i+1 in S or i+1<len(V)-1: T[f(i)][f(i+1)]+=1
        prior=collections.Counter(f(i+1) for i in tr)
        moda=prior.most_common(1)[0][0] if prior else None
        for i in te:
            vero=f(i+1)
            pred=T[f(i)].most_common(1)[0][0] if T[f(i)] else moda
            acc.append(pred==vero); base.append(moda==vero)
    return st.mean(acc),st.mean(base),len(acc)
print("CONFRONTO FRA CATENE DI MARKOV — quale prevede meglio lo stato del giorno dopo\n")
print(" modello                     stati  precisione   sempre lo stato piu comune   guadagno")
ris=[]
for nome,f in MODELLI:
    ns=len(set(f(i) for i in S))
    a,b,n=valuta(f)
    ris.append((a-b,nome,ns,a,b,n))
    print(f" {nome:27s} {ns:3d}     {100*a:5.1f}%          {100*b:5.1f}%              {100*(a-b):+5.1f}")
ris.sort(reverse=True)
print(f"\n MIGLIORE: {ris[0][1]} ({100*ris[0][3]:.1f}%, guadagno {100*ris[0][0]:+.1f} punti)")
json.dump([[r[1],r[2],round(100*r[3],1),round(100*r[4],1)] for r in ris],open('markov_cmp.json','w'))
